"""Tests for dependency injection extractors and handler resolver."""

from __future__ import annotations

from typing import Annotated

from sipx._depends import (
    AutoRTP,
    CallID,
    FromHeader,
    Header,
    SDP,
    Source,
    ToHeader,
    resolve_handler,
)
from sipx._models._message import Request
from sipx._types import TransportAddress


def _make_request() -> Request:
    return Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={
            "From": "<sip:alice@example.com>",
            "To": "<sip:bob@example.com>",
            "Call-ID": "abc123@host",
            "X-Custom": "custom-value",
        },
    )


def _make_source() -> TransportAddress:
    return TransportAddress(host="10.0.0.1", port=5060, protocol="UDP")


class TestExtractors:
    def test_from_header(self):
        req = _make_request()
        src = _make_source()
        assert FromHeader().extract(req, src) == "<sip:alice@example.com>"

    def test_to_header(self):
        req = _make_request()
        src = _make_source()
        assert ToHeader().extract(req, src) == "<sip:bob@example.com>"

    def test_call_id(self):
        req = _make_request()
        src = _make_source()
        assert CallID().extract(req, src) == "abc123@host"

    def test_header_custom(self):
        req = _make_request()
        src = _make_source()
        assert Header("X-Custom").extract(req, src) == "custom-value"

    def test_source(self):
        req = _make_request()
        src = _make_source()
        result = Source().extract(req, src)
        assert result is src

    def test_sdp_returns_body(self):
        req = _make_request()
        src = _make_source()
        assert SDP().extract(req, src) == req.body

    def test_auto_rtp_without_sdp_returns_none(self):
        req = _make_request()
        src = _make_source()
        assert AutoRTP(port=8000).extract(req, src) is None


class TestResolveHandler:
    def test_annotated_from_header(self):
        results = {}

        def handler(
            request: Request,
            caller: Annotated[str, FromHeader()],
        ) -> None:
            results["caller"] = caller

        resolve_handler(handler, _make_request(), _make_source())
        assert results["caller"] == "<sip:alice@example.com>"

    def test_annotated_class_not_instance(self):
        results = {}

        def handler(
            request: Request,
            caller: Annotated[str, FromHeader],
        ) -> None:
            results["caller"] = caller

        resolve_handler(handler, _make_request(), _make_source())
        assert results["caller"] == "<sip:alice@example.com>"

    def test_fallback_no_hints(self):
        results = {}

        def handler(request, source):
            results["req"] = request
            results["src"] = source

        req = _make_request()
        src = _make_source()
        resolve_handler(handler, req, src)
        assert results["req"] is req
        assert results["src"] is src

    def test_fills_unresolved_positional(self):
        results = {}

        def handler(
            request: Request,
            source,
            caller: Annotated[str, FromHeader()],
        ) -> None:
            results["request"] = request
            results["source"] = source
            results["caller"] = caller

        req = _make_request()
        src = _make_source()
        resolve_handler(handler, req, src)
        assert results["request"] is req
        assert results["source"] is src
        assert results["caller"] == "<sip:alice@example.com>"

    def test_multiple_extractors(self):
        results = {}

        def handler(
            request: Request,
            caller: Annotated[str, FromHeader()],
            callee: Annotated[str, ToHeader()],
            call_id: Annotated[str, CallID()],
        ) -> None:
            results["caller"] = caller
            results["callee"] = callee
            results["call_id"] = call_id

        resolve_handler(handler, _make_request(), _make_source())
        assert results["caller"] == "<sip:alice@example.com>"
        assert results["callee"] == "<sip:bob@example.com>"
        assert results["call_id"] == "abc123@host"
