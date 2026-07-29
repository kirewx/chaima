# src/chaima/services/sds_fetch.py
"""Download a safety data sheet (PDF) from a user-supplied URL.

The download core (``fetch_sds_pdf``) is a pure helper: no models, no
session, no storage. The single-chemical endpoint calls it directly and
hands the returned bytes to ``files_service.save_upload`` itself. The one
exception is ``fetch_group_sds`` below, which does take a session — it
drives a group-wide batch fetch and persists progress as it goes.

Guards applied here: http(s) only, publicly routable hosts only (re-checked
on every redirect hop), a hard size cap enforced while streaming, and a
PDF sniff on the payload.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from chaima.models.user import User

logger = logging.getLogger(__name__)

MAX_SDS_BYTES = 20 * 1024 * 1024  # 20 MB
FETCH_TIMEOUT = 15.0
MAX_REDIRECTS = 5

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class SdsFetchError(Exception):
    """Fetch failed; the message is safe to surface to the user."""


def rewrite_dropbox_url(url: str) -> str:
    """Force direct download (``dl=1``) on Dropbox share links.

    Other hosts pass through untouched. Only applied at fetch time — the
    stored ``sds_url`` keeps whatever the user entered.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host != "dropbox.com" and not host.endswith(".dropbox.com"):
        return url
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k != "dl"
    ]
    query.append(("dl", "1"))
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _assert_public_http_url(url: str) -> None:
    """Reject anything that is not http(s) to a publicly routable host.

    Best-effort SSRF guard: the hostname is resolved here and rejected when
    any answer is non-global (loopback, RFC1918, link-local, reserved). The
    actual request re-resolves — a DNS-rebinding TOCTOU we accept because
    only group admins can trigger fetches.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise SdsFetchError("Only http/https URLs are allowed")
    host = parts.hostname
    if not host:
        raise SdsFetchError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SdsFetchError(f"Cannot resolve host '{host}'") from e
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError as e:
            # Fail closed: an address we cannot classify is not proven public.
            raise SdsFetchError("URL resolves to a non-public address") from e
        if not ip.is_global:
            raise SdsFetchError("URL resolves to a non-public address")


async def _read_capped(response: httpx.Response) -> bytes:
    """Buffer the body, aborting as soon as the cap is exceeded."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_SDS_BYTES:
            raise SdsFetchError(
                f"File too large (over {MAX_SDS_BYTES // (1024 * 1024)} MB)"
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def fetch_sds_pdf(
    url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> bytes:
    """Download the PDF behind ``url`` with SSRF/size/type guards.

    Redirects are followed manually (max ``MAX_REDIRECTS``) so every hop is
    re-validated against :func:`_assert_public_http_url`. The body is accepted
    when the Content-Type is ``application/pdf`` or the payload carries the
    ``%PDF-`` magic. ``transport`` exists solely for tests; production callers
    omit it.

    Raises:
        SdsFetchError: on any guard violation or transport failure. The
            message is safe to show to the user.
    """
    current = rewrite_dropbox_url(url)
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT, follow_redirects=False, transport=transport
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_public_http_url(current)
            next_url: str | None = None
            content_type = ""
            data = b""
            try:
                async with client.stream("GET", current) as resp:
                    if resp.status_code in _REDIRECT_STATUSES:
                        location = resp.headers.get("location")
                        if not location:
                            raise SdsFetchError("Redirect without Location header")
                        next_url = str(httpx.URL(current).join(location))
                    elif resp.status_code != 200:
                        raise SdsFetchError(
                            f"Upstream returned HTTP {resp.status_code}"
                        )
                    else:
                        content_type = resp.headers.get("content-type", "").lower()
                        data = await _read_capped(resp)
            except httpx.HTTPError as e:
                safe_url = httpx.URL(current).copy_with(userinfo=b"", query=None)
                logger.warning("SDS fetch failed for %s: %s", safe_url, e)
                raise SdsFetchError(f"Download failed: {e.__class__.__name__}") from e

            # The response is closed by now; only the values copied out of it
            # above are used, so nothing leaks from a redirect hop.
            if next_url is not None:
                current = next_url
                continue

            if not content_type.startswith("application/pdf") and not data.startswith(
                b"%PDF-"
            ):
                raise SdsFetchError("The link is not a PDF")
            return data

    raise SdsFetchError("Too many redirects")


async def fetch_group_sds(
    session: AsyncSession, group_id: UUID, user: User
) -> AsyncGenerator[dict, None]:
    """Yield SSE-style events while archiving SDS PDFs for every chemical in
    the group that has an ``sds_url`` but no stored ``sds_path`` (fill-only).
    Failures never abort the run. Commits after each chemical so partial
    progress survives a dropped connection.

    Secret chemicals the caller didn't create are excluded, same as every
    other listing — ``apply_secret_filter`` mirrors ``can_view_chemical``.
    """
    import asyncio

    from sqlmodel import select

    from chaima.models.chemical import Chemical
    from chaima.services import chemicals as chemical_service
    from chaima.services import files as files_service

    stmt = select(Chemical).where(
        Chemical.group_id == group_id,
        Chemical.sds_url.is_not(None),
        Chemical.sds_path.is_(None),
    )
    stmt = chemical_service.apply_secret_filter(stmt, user)
    chemicals = list((await session.exec(stmt)).all())

    counts = {"fetched": 0, "failed": 0}
    for chem in chemicals:
        try:
            data = await fetch_sds_pdf(chem.sds_url)
            if not data:
                raise SdsFetchError("The link returned an empty file")
        except SdsFetchError as e:
            counts["failed"] += 1
            logger.warning("SDS batch fetch failed for chemical %s: %s", chem.id, e)
            yield {
                "id": str(chem.id),
                "name": chem.name,
                "status": "failed",
                "reason": str(e),
            }
            continue
        chem.sds_path = files_service.save_upload(group_id, "sds.pdf", data)
        session.add(chem)
        await session.commit()
        counts["fetched"] += 1
        yield {"id": str(chem.id), "name": chem.name, "status": "fetched"}
        await asyncio.sleep(0.1)

    yield {"summary": counts}
