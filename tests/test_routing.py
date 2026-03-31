"""Tests for sipx._routing (RouteSet)."""

from __future__ import annotations

from sipx._routing import RouteSet
from sipx._models._message import Request, Response


class TestRouteSetFromResponse:
    def test_from_response_with_record_route(self):
        resp = Response(
            status_code=200,
            headers={
                "Record-Route": "<sip:p1.example.com;lr>, <sip:p2.example.com;lr>",
            },
        )
        rs = RouteSet.from_response(resp)
        # UAC reverses the order
        assert rs.routes == ["sip:p2.example.com;lr", "sip:p1.example.com;lr"]

    def test_from_response_reverses_order(self):
        resp = Response(
            status_code=200,
            headers={
                "Record-Route": "<sip:a.com;lr>, <sip:b.com;lr>, <sip:c.com;lr>",
            },
        )
        rs = RouteSet.from_response(resp)
        assert rs.routes[0] == "sip:c.com;lr"
        assert rs.routes[-1] == "sip:a.com;lr"

    def test_from_response_empty_header(self):
        resp = Response(status_code=200, headers={})
        rs = RouteSet.from_response(resp)
        assert rs.is_empty
        assert len(rs) == 0

    def test_from_response_no_record_route(self):
        resp = Response(status_code=200)
        rs = RouteSet.from_response(resp)
        assert rs.is_empty


class TestRouteSetFromRequest:
    def test_from_request_with_route(self):
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={
                "Route": "<sip:p1.example.com;lr>, <sip:p2.example.com;lr>",
            },
        )
        rs = RouteSet.from_request(req)
        assert rs.routes == ["sip:p1.example.com;lr", "sip:p2.example.com;lr"]

    def test_from_request_no_route(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        rs = RouteSet.from_request(req)
        assert rs.is_empty


class TestRouteSetApply:
    def test_apply_loose_routing(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        rs = RouteSet(routes=["sip:p1.example.com;lr", "sip:p2.example.com;lr"])
        rs.apply(req)
        # URI unchanged with loose routing
        assert req.uri == "sip:bob@example.com"
        assert "Route" in req.headers
        route = req.headers["Route"]
        assert "<sip:p1.example.com;lr>" in route
        assert "<sip:p2.example.com;lr>" in route

    def test_apply_strict_routing(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        rs = RouteSet(routes=["sip:p1.example.com", "sip:p2.example.com"])
        rs.apply(req)
        # First route becomes URI with strict routing
        assert req.uri == "sip:p1.example.com"
        route = req.headers["Route"]
        assert "<sip:p2.example.com>" in route
        assert "<sip:bob@example.com>" in route

    def test_apply_empty_route_set(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        rs = RouteSet()
        rs.apply(req)
        assert req.uri == "sip:bob@example.com"
        assert req.headers.get("Route") is None


class TestRouteSetProperties:
    def test_is_empty_true(self):
        rs = RouteSet()
        assert rs.is_empty is True

    def test_is_empty_false(self):
        rs = RouteSet(routes=["sip:proxy.com;lr"])
        assert rs.is_empty is False

    def test_is_loose_true(self):
        rs = RouteSet(routes=["sip:proxy.com;lr"])
        assert rs.is_loose is True

    def test_is_loose_false_no_lr(self):
        rs = RouteSet(routes=["sip:proxy.com"])
        assert rs.is_loose is False

    def test_is_loose_false_empty(self):
        rs = RouteSet()
        assert rs.is_loose is False

    def test_len(self):
        rs = RouteSet(routes=["sip:a.com;lr", "sip:b.com;lr"])
        assert len(rs) == 2

    def test_repr(self):
        rs = RouteSet(routes=["sip:a.com;lr"])
        assert "RouteSet" in repr(rs)
