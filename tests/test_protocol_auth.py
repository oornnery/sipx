"""Tests for generator-based authentication flow."""

from __future__ import annotations

import pytest

from sipx.exceptions import AuthError
from sipx.models import Request, Response
from sipx.protocol.auth import AuthFlow


def make_request(
    method: str = "REGISTER",
    uri: str = "sip:example.com",
) -> Request:
    """Create a test request."""
    return Request(method=method, uri=uri, headers={}, body=None)


def make_response(
    status_code: int,
    reason: str = "",
    headers: dict[str, str] | None = None,
    request: Request | None = None,
) -> Response:
    """Create a test response."""
    return Response(
        status_code=status_code,
        reason=reason,
        headers=headers or {},
        body=None,
        request=request,
    )


class TestAuthFlowBasic:
    """Basic auth flow tests."""

    def test_auth_flow_yields_initial_request_without_auth(self) -> None:
        """Auth flow should yield the original request first."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        first_req = next(flow)

        assert first_req == req
        assert "Authorization" not in first_req.headers

    def test_auth_flow_completes_when_no_auth_required(self) -> None:
        """Auth flow should complete when response doesn't require auth."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)  # Get initial request
        resp = make_response(200, "OK", request=req)

        with pytest.raises(StopIteration):
            flow.send(resp)

    def test_auth_flow_handles_non_auth_error(self) -> None:
        """Auth flow should complete on non-401/407 errors."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(403, "Forbidden", request=req)

        with pytest.raises(StopIteration):
            flow.send(resp)


class TestDigestAuthentication:
    """Digest authentication tests."""

    def test_auth_flow_handles_401_challenge(self) -> None:
        """Auth flow should handle 401 WWW-Authenticate challenge."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="abc123"'},
            request=req,
        )

        auth_req = flow.send(resp)

        assert "Authorization" in auth_req.headers
        assert "Digest" in auth_req.headers["Authorization"]
        assert 'username="alice"' in auth_req.headers["Authorization"]
        assert 'realm="example.com"' in auth_req.headers["Authorization"]
        assert 'nonce="abc123"' in auth_req.headers["Authorization"]

    def test_auth_flow_handles_407_proxy_challenge(self) -> None:
        """Auth flow should handle 407 Proxy-Authenticate challenge."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            407,
            "Proxy Authentication Required",
            headers={"Proxy-Authenticate": 'Digest realm="proxy.com", nonce="xyz789"'},
            request=req,
        )

        auth_req = flow.send(resp)

        assert "Proxy-Authorization" in auth_req.headers
        assert "Digest" in auth_req.headers["Proxy-Authorization"]
        assert 'username="alice"' in auth_req.headers["Proxy-Authorization"]

    def test_digest_auth_includes_qop_when_present(self) -> None:
        """Digest auth should include qop when challenge specifies it."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={
                "WWW-Authenticate": 'Digest realm="example.com", nonce="abc123", qop="auth"'
            },
            request=req,
        )

        auth_req = flow.send(resp)
        auth_header = auth_req.headers["Authorization"]

        assert "qop=auth" in auth_header
        assert "nc=00000001" in auth_header
        assert "cnonce=" in auth_header

    def test_digest_auth_includes_opaque_when_present(self) -> None:
        """Digest auth should include opaque when challenge specifies it."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={
                "WWW-Authenticate": 'Digest realm="example.com", nonce="abc123", opaque="xyz"'
            },
            request=req,
        )

        auth_req = flow.send(resp)
        auth_header = auth_req.headers["Authorization"]

        assert 'opaque="xyz"' in auth_header

    def test_digest_auth_calculates_response_hash(self) -> None:
        """Digest auth should calculate correct response hash."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="abc123"'},
            request=req,
        )

        auth_req = flow.send(resp)
        auth_header = auth_req.headers["Authorization"]
        assert isinstance(auth_header, str)

        # Response hash should be present
        assert 'response="' in auth_header
        # Should be a 32-character hex string (MD5)
        import re

        match = re.search(r'response="([a-f0-9]{32})"', auth_header)
        assert match is not None


class TestAuthFlowErrors:
    """Error handling tests."""

    def test_auth_flow_raises_on_malformed_challenge(self) -> None:
        """Auth flow should raise AuthError on malformed challenge."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={"WWW-Authenticate": "Digest invalid"},
            request=req,
        )

        with pytest.raises(AuthError, match="Failed to parse auth challenge"):
            flow.send(resp)

    def test_auth_flow_raises_on_missing_realm(self) -> None:
        """Auth flow should raise AuthError when realm is missing."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={"WWW-Authenticate": 'Digest nonce="abc123"'},
            request=req,
        )

        with pytest.raises(AuthError, match="Failed to parse auth challenge"):
            flow.send(resp)

    def test_auth_flow_raises_on_unsupported_algorithm(self) -> None:
        """Auth flow should raise AuthError on unsupported algorithm."""
        auth = AuthFlow(username="alice", password="secret")
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp = make_response(
            401,
            "Unauthorized",
            headers={
                "WWW-Authenticate": 'Digest realm="example.com", nonce="abc123", algorithm=SHA-256'
            },
            request=req,
        )

        with pytest.raises(AuthError, match="Unsupported Digest algorithm"):
            flow.send(resp)

    def test_auth_flow_raises_on_max_retries_exceeded(self) -> None:
        """Auth flow should raise AuthError when max retries exceeded."""
        auth = AuthFlow(username="alice", password="secret", max_retries=1)
        req = make_request()
        flow = auth.auth_flow(req)

        next(flow)
        resp1 = make_response(
            401,
            "Unauthorized",
            headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="abc123"'},
            request=req,
        )

        auth_req = flow.send(resp1)

        # Send another 401 to trigger max retries
        resp2 = make_response(
            401,
            "Unauthorized",
            headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="def456"'},
            request=auth_req,
        )

        with pytest.raises(AuthError, match="Authentication failed after 1 retries"):
            flow.send(resp2)


class TestDigestChallengeParsing:
    """Digest challenge parsing tests."""

    def test_parse_digest_challenge_basic(self) -> None:
        """Should parse basic Digest challenge."""
        auth = AuthFlow(username="alice", password="secret")
        challenge = auth._parse_digest_challenge(
            'Digest realm="example.com", nonce="abc123"'
        )

        assert challenge.realm == "example.com"
        assert challenge.nonce == "abc123"
        assert challenge.algorithm == "MD5"
        assert challenge.qop is None
        assert challenge.opaque is None

    def test_parse_digest_challenge_with_all_fields(self) -> None:
        """Should parse Digest challenge with all fields."""
        auth = AuthFlow(username="alice", password="secret")
        challenge = auth._parse_digest_challenge(
            'Digest realm="example.com", nonce="abc123", algorithm=MD5, '
            'qop="auth", opaque="xyz789"'
        )

        assert challenge.realm == "example.com"
        assert challenge.nonce == "abc123"
        assert challenge.algorithm == "MD5"
        assert challenge.qop == "auth"
        assert challenge.opaque == "xyz789"

    def test_parse_digest_challenge_without_prefix(self) -> None:
        """Should parse challenge without 'Digest' prefix."""
        auth = AuthFlow(username="alice", password="secret")
        challenge = auth._parse_digest_challenge('realm="example.com", nonce="abc123"')

        assert challenge.realm == "example.com"
        assert challenge.nonce == "abc123"
