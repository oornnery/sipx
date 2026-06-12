"""Tests for RFC 3262 PRACK handling in sipx.rfc.prack."""

from __future__ import annotations

import pytest

from sipx.exceptions import ProtocolError
from sipx.models import Request, Response
from sipx.rfc.prack import PrackHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invite_request(cseq: int = 1) -> Request:
    """Build a minimal INVITE request."""
    return Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={"CSeq": f"{cseq} INVITE"},
        body=None,
    )


def _reliable_provisional(
    status_code: int,
    rseq: int,
    request: Request | None = None,
) -> Response:
    """Build a reliable provisional response with Require: 100rel."""
    return Response(
        status_code=status_code,
        reason="Ringing",
        headers={"Require": "100rel", "RSeq": str(rseq)},
        body=None,
        request=request or _invite_request(),
    )


# ===========================================================================
# PrackHandler — Import
# ===========================================================================


class TestPrackHandlerImport:
    """Basic import and instantiation tests."""

    def test_import_prack_handler(self):
        """PrackHandler can be imported from sipx.rfc.prack."""
        from sipx.rfc.prack import PrackHandler as PH

        assert PH is not None

    def test_instantiate_handler(self):
        """PrackHandler can be instantiated without arguments."""
        handler = PrackHandler()
        assert handler is not None
        assert handler.seen_rseq_numbers == frozenset()


# ===========================================================================
# PrackHandler — PRACK Generation
# ===========================================================================


class TestPrackGeneration:
    """Tests for PRACK request generation."""

    def test_generate_prack_for_reliable_1xx(self):
        """generate_prack returns a Request for a reliable 1xx response."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional = _reliable_provisional(180, 1, invite)

        prack = handler.generate_prack(provisional)

        assert isinstance(prack, Request)

    def test_prack_method_is_prack(self):
        """Generated PRACK request has method 'PRACK'."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional = _reliable_provisional(180, 1, invite)

        prack = handler.generate_prack(provisional)

        assert prack.method == "PRACK"

    def test_prack_has_rack_header(self):
        """Generated PRACK request contains a RAck header."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional = _reliable_provisional(180, 1, invite)

        prack = handler.generate_prack(provisional)

        assert "RAck" in prack.headers

    def test_rack_header_format(self):
        """RAck header follows RFC 3262 format: <rseq> <cseq> <method>."""
        handler = PrackHandler()
        invite = _invite_request(cseq=42)
        provisional = _reliable_provisional(183, 7, invite)

        prack = handler.generate_prack(provisional)

        assert prack.headers["RAck"] == "7 42 INVITE"

    def test_prack_uri_matches_invite(self):
        """PRACK request URI matches the original INVITE URI."""
        handler = PrackHandler()
        invite = Request(
            method="INVITE",
            uri="sip:alice@proxy.example.com",
            headers={"CSeq": "1 INVITE"},
            body=None,
        )
        provisional = _reliable_provisional(180, 1, invite)

        prack = handler.generate_prack(provisional)

        assert prack.uri == "sip:alice@proxy.example.com"

    def test_prack_has_own_cseq(self):
        """PRACK request has its own CSeq header with method PRACK."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional = _reliable_provisional(180, 1, invite)

        prack = handler.generate_prack(provisional)

        assert "CSeq" in prack.headers
        assert "PRACK" in prack.headers["CSeq"]


# ===========================================================================
# PrackHandler — RSeq Tracking
# ===========================================================================


class TestRSeqTracking:
    """Tests for RSeq duplicate detection and tracking."""

    def test_duplicate_rseq_raises_error(self):
        """Duplicate RSeq number raises ProtocolError."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional1 = _reliable_provisional(180, 1, invite)
        provisional2 = _reliable_provisional(180, 1, invite)

        handler.generate_prack(provisional1)

        with pytest.raises(ProtocolError, match="[Dd]uplicate|[Aa]lready"):
            handler.generate_prack(provisional2)

    def test_different_rseq_generates_prack(self):
        """Different RSeq numbers each generate a valid PRACK."""
        handler = PrackHandler()
        invite = _invite_request()

        prack1 = handler.generate_prack(_reliable_provisional(180, 1, invite))
        prack2 = handler.generate_prack(_reliable_provisional(180, 2, invite))

        assert prack1.headers["RAck"] == "1 1 INVITE"
        assert prack2.headers["RAck"] == "2 1 INVITE"

    def test_seen_rseq_numbers_tracked(self):
        """Handler tracks all acknowledged RSeq numbers."""
        handler = PrackHandler()
        invite = _invite_request()

        handler.generate_prack(_reliable_provisional(180, 10, invite))
        handler.generate_prack(_reliable_provisional(180, 20, invite))

        assert handler.seen_rseq_numbers == frozenset({10, 20})

    def test_prack_cseq_increments(self):
        """Each generated PRACK gets an incrementing CSeq number."""
        handler = PrackHandler()
        invite = _invite_request()

        prack1 = handler.generate_prack(_reliable_provisional(180, 1, invite))
        prack2 = handler.generate_prack(_reliable_provisional(180, 2, invite))

        cseq1 = int(prack1.headers["CSeq"].split()[0])
        cseq2 = int(prack2.headers["CSeq"].split()[0])
        assert cseq2 == cseq1 + 1


# ===========================================================================
# PrackHandler — Error Handling
# ===========================================================================


class TestPrackErrorHandling:
    """Tests for error conditions and validation."""

    def test_non_reliable_provisional_raises_error(self):
        """Provisional without Require: 100rel raises ProtocolError."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional = Response(
            status_code=180,
            reason="Ringing",
            headers={},
            body=None,
            request=invite,
        )

        with pytest.raises(ProtocolError):
            handler.generate_prack(provisional)

    def test_is_reliable_returns_true_for_100rel(self):
        """is_reliable returns True for 1xx with Require: 100rel."""
        handler = PrackHandler()
        response = _reliable_provisional(180, 1)

        assert handler.is_reliable(response) is True

    def test_is_reliable_returns_false_without_100rel(self):
        """is_reliable returns False for 1xx without Require: 100rel."""
        handler = PrackHandler()
        response = Response(
            status_code=180,
            reason="Ringing",
            headers={},
            body=None,
        )

        assert handler.is_reliable(response) is False

    def test_is_reliable_returns_false_for_final_response(self):
        """is_reliable returns False for 2xx+ responses even with 100rel."""
        handler = PrackHandler()
        response = Response(
            status_code=200,
            reason="OK",
            headers={"Require": "100rel", "RSeq": "1"},
            body=None,
        )

        assert handler.is_reliable(response) is False

    def test_missing_rseq_raises_error(self):
        """Reliable provisional without RSeq header raises ProtocolError."""
        handler = PrackHandler()
        invite = _invite_request()
        provisional = Response(
            status_code=180,
            reason="Ringing",
            headers={"Require": "100rel"},
            body=None,
            request=invite,
        )

        with pytest.raises(ProtocolError, match="RSeq"):
            handler.generate_prack(provisional)

    def test_unlinked_response_raises_error(self):
        """Provisional without linked request raises ProtocolError."""
        handler = PrackHandler()
        provisional = Response(
            status_code=180,
            reason="Ringing",
            headers={"Require": "100rel", "RSeq": "1"},
            body=None,
            request=None,
        )

        with pytest.raises(ProtocolError):
            handler.generate_prack(provisional)
