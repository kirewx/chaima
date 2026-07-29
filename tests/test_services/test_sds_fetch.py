# tests/test_services/test_sds_fetch.py
import socket

import httpx
import pytest

from chaima.services import sds_fetch


PDF = b"%PDF-1.4\n%EOF\n"


def _fake_getaddrinfo_public(host, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def _fake_getaddrinfo_private(host, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]


@pytest.mark.parametrize("url,expected", [
    (
        "https://www.dropbox.com/scl/fi/abc/x.pdf?rlkey=k&dl=0",
        "https://www.dropbox.com/scl/fi/abc/x.pdf?rlkey=k&dl=1",
    ),
    (
        "https://www.dropbox.com/scl/fi/abc/x.pdf?rlkey=k",
        "https://www.dropbox.com/scl/fi/abc/x.pdf?rlkey=k&dl=1",
    ),
    ("https://example.com/sds.pdf", "https://example.com/sds.pdf"),
])
def test_rewrite_dropbox_url(url, expected):
    assert sds_fetch.rewrite_dropbox_url(url) == expected


async def test_fetch_rejects_non_http_scheme():
    # match= matters: without it, httpx's own UnsupportedProtocol would be
    # wrapped into an SdsFetchError and the test would pass even with the
    # scheme guard removed.
    with pytest.raises(sds_fetch.SdsFetchError, match="Only http/https"):
        await sds_fetch.fetch_sds_pdf("ftp://example.com/sds.pdf")


async def test_fetch_rejects_private_host(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_private)
    with pytest.raises(sds_fetch.SdsFetchError, match="non-public"):
        await sds_fetch.fetch_sds_pdf("https://internal.example/sds.pdf")


async def test_fetch_happy_path(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=PDF, headers={"content-type": "application/pdf"},
        )
    )
    data = await sds_fetch.fetch_sds_pdf("https://example.com/sds.pdf", transport=transport)
    assert data == PDF


async def test_fetch_accepts_pdf_magic_with_wrong_content_type(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=PDF, headers={"content-type": "application/octet-stream"},
        )
    )
    data = await sds_fetch.fetch_sds_pdf("https://example.com/sds.pdf", transport=transport)
    assert data == PDF


async def test_fetch_rejects_non_pdf(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=b"<html>hi</html>", headers={"content-type": "text/html"},
        )
    )
    with pytest.raises(sds_fetch.SdsFetchError, match="not a PDF"):
        await sds_fetch.fetch_sds_pdf("https://example.com/sds.pdf", transport=transport)


async def test_fetch_rejects_oversized(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    monkeypatch.setattr(sds_fetch, "MAX_SDS_BYTES", 10)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=PDF * 10, headers={"content-type": "application/pdf"},
        )
    )
    with pytest.raises(sds_fetch.SdsFetchError, match="too large"):
        await sds_fetch.fetch_sds_pdf("https://example.com/sds.pdf", transport=transport)


async def test_fetch_follows_redirect_and_blocks_private_target(monkeypatch):
    def selective_getaddrinfo(host, *args, **kwargs):
        if host == "public.example":
            return _fake_getaddrinfo_public(host)
        return _fake_getaddrinfo_private(host)

    monkeypatch.setattr(socket, "getaddrinfo", selective_getaddrinfo)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302, headers={"location": "https://internal.example/sds.pdf"},
        )
    )
    with pytest.raises(sds_fetch.SdsFetchError, match="non-public"):
        await sds_fetch.fetch_sds_pdf("https://public.example/sds.pdf", transport=transport)


async def test_fetch_follows_redirect_to_pdf(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)

    def handler(request):
        if request.url.path == "/sds.pdf":
            return httpx.Response(302, headers={"location": "/real/sds.pdf"})
        return httpx.Response(
            200, content=PDF, headers={"content-type": "application/pdf"},
        )

    transport = httpx.MockTransport(handler)
    data = await sds_fetch.fetch_sds_pdf(
        "https://example.com/sds.pdf", transport=transport
    )
    assert data == PDF


async def test_fetch_rejects_too_many_redirects(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": f"/hop{len(calls)}.pdf"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(sds_fetch.SdsFetchError, match="Too many redirects"):
        await sds_fetch.fetch_sds_pdf(
            "https://example.com/sds.pdf", transport=transport
        )
    assert len(calls) == sds_fetch.MAX_REDIRECTS + 1


async def test_fetch_rejects_redirect_without_location(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    transport = httpx.MockTransport(lambda request: httpx.Response(302))
    with pytest.raises(sds_fetch.SdsFetchError, match="Redirect without Location"):
        await sds_fetch.fetch_sds_pdf(
            "https://example.com/sds.pdf", transport=transport
        )


async def test_fetch_rejects_upstream_error(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    transport = httpx.MockTransport(lambda request: httpx.Response(403))
    with pytest.raises(sds_fetch.SdsFetchError, match="HTTP 403"):
        await sds_fetch.fetch_sds_pdf("https://example.com/sds.pdf", transport=transport)
