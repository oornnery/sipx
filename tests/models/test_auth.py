"""Tests for sipx.models._auth (Auth, DigestAuth, DigestChallenge, DigestCredentials, AuthParser)."""

from __future__ import annotations

import hashlib
import re

import pytest

from sipx.models._auth import (
    Auth,
    AuthParser,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    SipAuthCredentials,
)
from sipx.models._header import Headers


# ============================================================================
# Auth.Digest() factory
# ============================================================================


class TestAuthDigest:
    def test_returns_sip_auth_credentials(self):
        creds = Auth.Digest("alice", "secret")
        assert isinstance(creds, SipAuthCredentials)
        assert creds.username == "alice"
        assert creds.password == "secret"

    def test_with_optional_params(self):
        creds = Auth.Digest(
            "alice",
            "secret",
            realm="atlanta.com",
            display_name="Alice",
            user_agent="TestApp/1.0",
        )
        assert creds.realm == "atlanta.com"
        assert creds.display_name == "Alice"
        assert creds.user_agent == "TestApp/1.0"

    def test_defaults(self):
        creds = Auth.Digest("alice", "secret")
        assert creds.realm is None
        assert creds.display_name is None
        assert creds.user_agent is None
        assert creds.expires == 3600


# ============================================================================
# DigestChallenge.parse()
# ============================================================================


class TestDigestChallengeParse:
    def test_basic_parse(self):
        header = 'Digest realm="atlanta.com", nonce="dcd98b7102dd2f0e"'
        challenge = DigestChallenge.parse(header)
        assert challenge.realm == "atlanta.com"
        assert challenge.nonce == "dcd98b7102dd2f0e"
        assert challenge.algorithm == "MD5"  # default
        assert challenge.scheme == "Digest"

    def test_with_algorithm(self):
        header = 'Digest realm="atlanta.com", nonce="abc", algorithm=SHA-256'
        challenge = DigestChallenge.parse(header)
        assert challenge.algorithm == "SHA-256"

    def test_with_qop(self):
        header = 'Digest realm="atlanta.com", nonce="abc", qop="auth,auth-int"'
        challenge = DigestChallenge.parse(header)
        assert challenge.qop == "auth,auth-int"

    def test_with_opaque(self):
        header = 'Digest realm="atlanta.com", nonce="abc", opaque="5ccc069c403ebaf9f0171e9517f40e41"'
        challenge = DigestChallenge.parse(header)
        assert challenge.opaque == "5ccc069c403ebaf9f0171e9517f40e41"

    def test_with_stale_true(self):
        header = 'Digest realm="atlanta.com", nonce="abc", stale=true'
        challenge = DigestChallenge.parse(header)
        assert challenge.stale is True

    def test_with_stale_false(self):
        header = 'Digest realm="atlanta.com", nonce="abc", stale=false'
        challenge = DigestChallenge.parse(header)
        assert challenge.stale is False

    def test_with_domain(self):
        header = 'Digest realm="atlanta.com", nonce="abc", domain="sip:atlanta.com"'
        challenge = DigestChallenge.parse(header)
        assert challenge.domain == "sip:atlanta.com"

    def test_not_digest_raises(self):
        with pytest.raises(ValueError, match="Expected Digest"):
            DigestChallenge.parse('Basic realm="atlanta.com"')

    def test_missing_realm_raises(self):
        with pytest.raises(ValueError, match="missing required"):
            DigestChallenge.parse('Digest nonce="abc"')

    def test_missing_nonce_raises(self):
        with pytest.raises(ValueError, match="missing required"):
            DigestChallenge.parse('Digest realm="atlanta.com"')

    def test_is_proxy_default(self):
        header = 'Digest realm="atlanta.com", nonce="abc"'
        challenge = DigestChallenge.parse(header)
        assert challenge.is_proxy is False


# ============================================================================
# DigestAuth.build_authorization() -- MD5
# ============================================================================


class TestDigestAuthMD5:
    def _make_auth(self, qop=None, opaque=None, algorithm="MD5"):
        challenge = DigestChallenge(
            realm="atlanta.com",
            nonce="dcd98b7102dd2f0e",
            algorithm=algorithm,
            qop=qop,
            opaque=opaque,
        )
        creds = DigestCredentials(username="alice", password="secret123")
        return DigestAuth(credentials=creds, challenge=challenge)

    def test_basic_md5_no_qop(self):
        auth = self._make_auth()
        result = auth.build_authorization(method="REGISTER", uri="sip:atlanta.com")

        assert result.startswith("Digest ")
        assert 'username="alice"' in result
        assert 'realm="atlanta.com"' in result
        assert 'nonce="dcd98b7102dd2f0e"' in result
        assert 'uri="sip:atlanta.com"' in result
        assert "algorithm=MD5" in result
        assert "response=" in result

    def test_md5_response_hash_correct(self):
        auth = self._make_auth()
        result = auth.build_authorization(method="REGISTER", uri="sip:atlanta.com")

        # Manually compute expected hash
        ha1 = hashlib.md5(b"alice:atlanta.com:secret123").hexdigest()
        ha2 = hashlib.md5(b"REGISTER:sip:atlanta.com").hexdigest()
        expected = hashlib.md5(f"{ha1}:dcd98b7102dd2f0e:{ha2}".encode()).hexdigest()

        assert f'response="{expected}"' in result

    def test_md5_with_qop_auth(self):
        auth = self._make_auth(qop="auth")
        result = auth.build_authorization(method="INVITE", uri="sip:bob@biloxi.com")

        assert "qop=auth" in result
        assert "nc=00000001" in result
        assert "cnonce=" in result

        # Nonce count increments
        result2 = auth.build_authorization(method="INVITE", uri="sip:bob@biloxi.com")
        assert "nc=00000002" in result2

    def test_md5_with_opaque(self):
        auth = self._make_auth(opaque="opaque_value")
        result = auth.build_authorization(method="REGISTER", uri="sip:atlanta.com")
        assert 'opaque="opaque_value"' in result


# ============================================================================
# DigestAuth.build_authorization() -- SHA-256
# ============================================================================


class TestDigestAuthSHA256:
    def test_sha256_response_hash(self):
        challenge = DigestChallenge(
            realm="atlanta.com",
            nonce="testnonce",
            algorithm="SHA-256",
        )
        creds = DigestCredentials(username="alice", password="secret123")
        auth = DigestAuth(credentials=creds, challenge=challenge)

        result = auth.build_authorization(method="REGISTER", uri="sip:atlanta.com")
        assert "algorithm=SHA-256" in result

        # Verify hash computation
        ha1 = hashlib.sha256(b"alice:atlanta.com:secret123").hexdigest()
        ha2 = hashlib.sha256(b"REGISTER:sip:atlanta.com").hexdigest()
        expected = hashlib.sha256(f"{ha1}:testnonce:{ha2}".encode()).hexdigest()

        assert f'response="{expected}"' in result


# ============================================================================
# QoP=auth handling (nonce count, cnonce)
# ============================================================================


class TestQopAuth:
    def test_nonce_count_increments(self):
        challenge = DigestChallenge(realm="test.com", nonce="nonce1", qop="auth")
        creds = DigestCredentials(username="user", password="pass")
        auth = DigestAuth(credentials=creds, challenge=challenge)

        r1 = auth.build_authorization(method="REGISTER", uri="sip:test.com")
        assert "nc=00000001" in r1
        assert auth.nonce_count == 1

        r2 = auth.build_authorization(method="REGISTER", uri="sip:test.com")
        assert "nc=00000002" in r2
        assert auth.nonce_count == 2

    def test_cnonce_generated_and_reused(self):
        challenge = DigestChallenge(realm="test.com", nonce="nonce1", qop="auth")
        creds = DigestCredentials(username="user", password="pass")
        auth = DigestAuth(credentials=creds, challenge=challenge)

        r1 = auth.build_authorization(method="REGISTER", uri="sip:test.com")
        cnonce1_match = re.search(r'cnonce="([^"]+)"', r1)
        assert cnonce1_match is not None
        cnonce1 = cnonce1_match.group(1)

        r2 = auth.build_authorization(method="REGISTER", uri="sip:test.com")
        cnonce2_match = re.search(r'cnonce="([^"]+)"', r2)
        assert cnonce2_match is not None
        cnonce2 = cnonce2_match.group(1)

        # cnonce should be reused for same challenge
        assert cnonce1 == cnonce2

    def test_qop_auth_int_with_body(self):
        challenge = DigestChallenge(
            realm="test.com", nonce="nonce1", qop="auth,auth-int"
        )
        creds = DigestCredentials(username="user", password="pass")
        auth = DigestAuth(credentials=creds, challenge=challenge)

        result = auth.build_authorization(
            method="INVITE", uri="sip:bob@test.com", entity_body=b"v=0\r\n"
        )
        assert "qop=auth-int" in result

    def test_qop_auth_when_no_body(self):
        challenge = DigestChallenge(
            realm="test.com", nonce="nonce1", qop="auth,auth-int"
        )
        creds = DigestCredentials(username="user", password="pass")
        auth = DigestAuth(credentials=creds, challenge=challenge)

        result = auth.build_authorization(method="REGISTER", uri="sip:test.com")
        assert "qop=auth" in result

    def test_no_qop_means_no_nc_cnonce(self):
        challenge = DigestChallenge(realm="test.com", nonce="nonce1", qop=None)
        creds = DigestCredentials(username="user", password="pass")
        auth = DigestAuth(credentials=creds, challenge=challenge)

        result = auth.build_authorization(method="REGISTER", uri="sip:test.com")
        assert "nc=" not in result
        assert "cnonce=" not in result
        assert "qop=" not in result


# ============================================================================
# AuthParser.parse_from_headers() with WWW-Authenticate
# ============================================================================


class TestAuthParserWWWAuthenticate:
    def test_parse_www_authenticate(self):
        headers = Headers(
            {
                "WWW-Authenticate": 'Digest realm="atlanta.com", nonce="abc123"',
            }
        )
        challenge = AuthParser.parse_from_headers(headers)
        assert challenge is not None
        assert isinstance(challenge, DigestChallenge)
        assert challenge.realm == "atlanta.com"
        assert challenge.is_proxy is False

    def test_www_authenticate_takes_priority(self):
        headers = Headers(
            {
                "WWW-Authenticate": 'Digest realm="www.com", nonce="www"',
                "Proxy-Authenticate": 'Digest realm="proxy.com", nonce="proxy"',
            }
        )
        challenge = AuthParser.parse_from_headers(headers)
        assert challenge is not None
        assert isinstance(challenge, DigestChallenge)
        assert challenge.realm == "www.com"
        assert challenge.is_proxy is False

    def test_no_auth_headers_returns_none(self):
        headers = Headers({"Via": "SIP/2.0/UDP server"})
        assert AuthParser.parse_from_headers(headers) is None


# ============================================================================
# AuthParser.parse_from_headers() with Proxy-Authenticate
# ============================================================================


class TestAuthParserProxyAuthenticate:
    def test_parse_proxy_authenticate(self):
        headers = Headers(
            {
                "Proxy-Authenticate": 'Digest realm="proxy.com", nonce="proxynonce"',
            }
        )
        challenge = AuthParser.parse_from_headers(headers)
        assert challenge is not None
        assert isinstance(challenge, DigestChallenge)
        assert challenge.realm == "proxy.com"
        assert challenge.is_proxy is True


# ============================================================================
# AuthParser.get_auth_header_name()
# ============================================================================


class TestGetAuthHeaderName:
    def test_www_authenticate_returns_authorization(self):
        challenge = DigestChallenge(realm="test.com", nonce="abc", is_proxy=False)
        assert AuthParser.get_auth_header_name(challenge) == "Authorization"

    def test_proxy_authenticate_returns_proxy_authorization(self):
        challenge = DigestChallenge(realm="test.com", nonce="abc", is_proxy=True)
        assert AuthParser.get_auth_header_name(challenge) == "Proxy-Authorization"


# ============================================================================
# AuthParser.parse_challenge() unsupported scheme
# ============================================================================


class TestAuthParserUnsupported:
    def test_unsupported_scheme_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            AuthParser.parse_challenge('Bearer token="abc"')


# ============================================================================
# AuthParser.parse_multiple_challenges()
# ============================================================================


class TestParseMultipleChallenges:
    def test_single_challenge(self):
        val = 'Digest realm="atlanta.com", nonce="abc"'
        challenges = AuthParser.parse_multiple_challenges(val)
        assert len(challenges) == 1
        assert isinstance(challenges[0], DigestChallenge)
        assert challenges[0].realm == "atlanta.com"

    def test_empty_returns_empty(self):
        challenges = AuthParser.parse_multiple_challenges("")
        assert challenges == []


# ============================================================================
# Auth.generate_challenge()
# ============================================================================


class TestAuthGenerateChallenge:
    def test_401_returns_www_authenticate(self):
        from sipx.models._message import Response

        resp = Response(
            401,
            headers={"WWW-Authenticate": 'Digest realm="test", nonce="abc"'},
        )
        val = Auth.generate_challenge(resp)
        assert "Digest" in val
        assert "test" in val

    def test_407_returns_proxy_authenticate(self):
        from sipx.models._message import Response

        resp = Response(
            407,
            headers={"Proxy-Authenticate": 'Digest realm="proxy", nonce="xyz"'},
        )
        val = Auth.generate_challenge(resp)
        assert "Digest" in val
        assert "proxy" in val

    def test_missing_header_returns_empty(self):
        from sipx.models._message import Response

        resp = Response(401)
        val = Auth.generate_challenge(resp)
        assert val == ""


# ============================================================================
# DigestCredentials
# ============================================================================


class TestDigestCredentials:
    def test_basic(self):
        creds = DigestCredentials(username="alice", password="secret")
        assert creds.username == "alice"
        assert creds.password == "secret"
        assert creds.realm is None

    def test_with_realm(self):
        creds = DigestCredentials(
            username="alice", password="secret", realm="example.com"
        )
        assert creds.realm == "example.com"
