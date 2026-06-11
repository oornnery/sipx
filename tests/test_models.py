from dataclasses import is_dataclass

from sipx.models import Request, Response


def test_request_construction():
    req = Request(method="INVITE", uri="sip:bob@example.com", headers={"From": "alice"}, body=None)
    assert req.method == "INVITE"
    assert req.uri == "sip:bob@example.com"
    assert req.headers == {"From": "alice"}
    assert req.body is None
    assert req.transport is None


def test_request_defaults():
    req = Request(method="OPTIONS", uri="sip:alice@example.com")
    assert req.headers == {}
    assert req.body is None
    assert req.transport is None


def test_request_build_with_dict_and_kwargs():
    req = Request.build("INVITE", "sip:bob@example.com", headers={"From": "alice"}, To="bob")
    assert req.method == "INVITE"
    assert req.uri == "sip:bob@example.com"
    assert req.headers == {"From": "alice", "To": "bob"}
    assert req.body is None
    assert req.transport is None


def test_request_serialization():
    req = Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={"From": "alice"},
        body=b"test",
    )
    data = req.to_bytes()
    assert b"INVITE sip:bob@example.com SIP/2.0" in data
    assert b"From: alice" in data
    assert data.endswith(b"test")


def test_response_construction():
    resp = Response(status_code=200, reason="OK", headers={"To": "bob"}, body=None)
    assert resp.status_code == 200
    assert resp.reason == "OK"
    assert resp.headers == {"To": "bob"}
    assert resp.body is None
    assert resp.request is None


def test_response_from_request():
    req = Request(method="INVITE", uri="sip:bob@example.com", headers={}, body=None)
    resp = Response.from_request(req, 200, "OK", headers={"To": "bob"})
    assert resp.status_code == 200
    assert resp.reason == "OK"
    assert resp.headers == {"To": "bob"}
    assert resp.request is req


def test_response_serialization():
    resp = Response(status_code=200, reason="OK", headers={"To": "bob"}, body=b"answer")
    data = resp.to_bytes()
    assert b"SIP/2.0 200 OK" in data
    assert b"To: bob" in data
    assert data.endswith(b"answer")


def test_models_are_dataclasses():
    assert is_dataclass(Request)
    assert is_dataclass(Response)
