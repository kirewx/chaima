# src/chaima/services/sds_fetch.py
"""Download a safety data sheet (PDF) from a user-supplied URL.

Pure download helper: no models, no session, no storage. Callers (the
single-chemical endpoint and, later, the batch generator) hand the returned
bytes to ``files_service.save_upload`` themselves.

Guards applied here: http(s) only, publicly routable hosts only (re-checked
on every redirect hop), a hard size cap enforced while streaming, and a
PDF sniff on the payload.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

MAX_SDS_BYTES = 20 * 1024 * 1024
FETCH_TIMEOUT = 15.0
MAX_REDIRECTS = 5

_REDIRECT_STATUS = (301, 302, 303, 307, 308)


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
                    if resp.status_code in _REDIRECT_STATUS:
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
