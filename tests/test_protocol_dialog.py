"""Tests for sipx.protocol.dialog state machine."""

from __future__ import annotations

import pytest

from sipx.exceptions import DialogError
from sipx.models import Request, Response
from sipx.protocol.dialog import Dialog, DialogId, DialogState


# --- Fixtures ---


def make_invite_request(
    call_id: str = "call-123",
    from_tag: str = "from-tag",
    to_tag: str | None = None,
    cseq: int = 1,
) -> Request:
    """Build a minimal INVITE request for testing."""
    to_value = f"<sip:bob@example.com>{f';tag={to_tag}' if to_tag else ''}"
    return Request(
        method="INVITE",
        uri="sip:bob@example.com",
        headers={
            "Call-ID": call_id,
            "From": f"<sip:alice@example.com>;tag={from_tag}",
            "To": to_value,
            "CSeq": f"{cseq} INVITE",
            "Contact": "<sip:alice@192.0.2.1:5060>",
        },
        body=None,
    )


def make_invite_response(
    request: Request,
    status_code: int = 200,
    reason: str = "OK",
    to_tag: str = "to-tag",
    record_route: str | list[str] | None = None,
    contact: str = "<sip:bob@192.0.2.2:5060>",
) -> Response:
    """Build a response to an INVITE request."""
    headers = dict(request.headers)
    # Add To tag if not present.
    to_value = headers.get("To", "")
    if ";tag=" not in to_value:
        headers["To"] = f"{to_value};tag={to_tag}"
    if record_route:
        headers["Record-Route"] = record_route
    if contact:
        headers["Contact"] = contact
    return Response(
        status_code=status_code,
        reason=reason,
        headers=headers,
        body=None,
        request=request,
    )


# --- Dialog Creation Tests ---


class TestDialogCreation:
    """Test dialog creation from INVITE."""

    def test_from_invite_200_creates_confirmed_dialog(self) -> None:
        """200 OK response creates a Confirmed dialog."""
        req = make_invite_request()
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.state == "Confirmed"
        assert dialog.call_id == "call-123"
        assert dialog.local_tag == "from-tag"
        assert dialog.remote_tag == "to-tag"

    def test_from_invite_180_creates_early_dialog(self) -> None:
        """180 Ringing creates an Early dialog."""
        req = make_invite_request()
        resp = make_invite_response(req, 180, "Ringing")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.state == "Early"
        assert dialog.call_id == "call-123"

    def test_from_invite_100_creates_early_dialog(self) -> None:
        """100 Trying creates an Early dialog."""
        req = make_invite_request()
        resp = make_invite_response(req, 100, "Trying")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.state == "Early"

    def test_from_invite_rejects_non_invite(self) -> None:
        """Non-INVITE request raises DialogError."""
        req = Request(
            method="OPTIONS",
            uri="sip:bob@example.com",
            headers={
                "Call-ID": "call-123",
                "From": "<sip:alice@example.com>;tag=from-tag",
                "To": "<sip:bob@example.com>",
                "CSeq": "1 OPTIONS",
            },
            body=None,
        )
        resp = make_invite_response(req, 200, "OK")

        with pytest.raises(DialogError, match="INVITE"):
            Dialog.from_invite(req, resp)

    def test_from_invite_rejects_3xx_response(self) -> None:
        """3xx response cannot create a dialog."""
        req = make_invite_request()
        resp = make_invite_response(req, 302, "Moved Temporarily")

        with pytest.raises(DialogError, match="cannot create"):
            Dialog.from_invite(req, resp)

    def test_from_invite_rejects_missing_from_tag(self) -> None:
        """Missing From tag raises DialogError."""
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={
                "Call-ID": "call-123",
                "From": "<sip:alice@example.com>",  # No tag
                "To": "<sip:bob@example.com>",
                "CSeq": "1 INVITE",
                "Contact": "<sip:alice@192.0.2.1:5060>",
            },
            body=None,
        )
        resp = make_invite_response(req, 200, "OK")

        with pytest.raises(DialogError, match="From"):
            Dialog.from_invite(req, resp)

    def test_from_invite_rejects_missing_to_tag(self) -> None:
        """Missing To tag in response raises DialogError."""
        req = make_invite_request()
        resp = Response(
            status_code=200,
            reason="OK",
            headers={
                "Call-ID": "call-123",
                "From": "<sip:alice@example.com>;tag=from-tag",
                "To": "<sip:bob@example.com>",  # No tag
                "CSeq": "1 INVITE",
                "Contact": "<sip:bob@192.0.2.2:5060>",
            },
            body=None,
            request=req,
        )

        with pytest.raises(DialogError, match="To"):
            Dialog.from_invite(req, resp)

    def test_from_request_creates_uas_dialog(self) -> None:
        """UAS creates dialog from incoming INVITE."""
        req = make_invite_request()
        dialog = Dialog.from_request(req, local_tag="uas-tag")

        assert dialog.state == "Early"
        assert dialog.call_id == "call-123"
        assert dialog.local_tag == "uas-tag"
        assert dialog.remote_tag == "from-tag"
        assert dialog.local_cseq == 0
        assert dialog.remote_cseq == 1


# --- State Transition Tests ---


class TestDialogStateTransitions:
    """Test dialog state transitions."""

    def test_early_to_confirmed_on_200(self) -> None:
        """Early dialog transitions to Confirmed on 200 OK."""
        req = make_invite_request()
        resp_180 = make_invite_response(req, 180, "Ringing")
        dialog = Dialog.from_invite(req, resp_180)

        assert dialog.state == "Early"

        resp_200 = make_invite_response(req, 200, "OK")
        dialog.update(resp_200)

        assert dialog.state == "Confirmed"

    def test_early_to_terminated_on_4xx(self) -> None:
        """Early dialog transitions to Terminated on 4xx."""
        req = make_invite_request()
        resp_180 = make_invite_response(req, 180, "Ringing")
        dialog = Dialog.from_invite(req, resp_180)

        resp_487 = make_invite_response(req, 487, "Request Terminated")
        dialog.update(resp_487)

        assert dialog.state == "Terminated"

    def test_confirmed_to_terminated_on_bye(self) -> None:
        """Confirmed dialog transitions to Terminated on terminate()."""
        req = make_invite_request()
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.state == "Confirmed"

        dialog.terminate()

        assert dialog.state == "Terminated"

    def test_terminated_dialog_rejects_further_transitions(self) -> None:
        """Terminated dialog cannot transition to other states."""
        req = make_invite_request()
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)
        dialog.terminate()

        with pytest.raises(DialogError, match="transition"):
            dialog.terminate()  # Already terminated

    def test_confirmed_dialog_ignores_1xx(self) -> None:
        """Confirmed dialog ignores further 1xx responses (forked dialogs)."""
        req = make_invite_request()
        resp_200 = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp_200)

        assert dialog.state == "Confirmed"

        # Late 180 from forked dialog should be ignored.
        resp_180 = make_invite_response(req, 180, "Ringing")
        dialog.update(resp_180)

        assert dialog.state == "Confirmed"  # Still confirmed

    def test_early_dialog_ignores_duplicate_1xx(self) -> None:
        """Early dialog ignores duplicate 1xx responses."""
        req = make_invite_request()
        resp_180 = make_invite_response(req, 180, "Ringing")
        dialog = Dialog.from_invite(req, resp_180)

        # Another 180 should be a no-op.
        dialog.update(resp_180)

        assert dialog.state == "Early"


# --- Dialog Matching Tests ---


class TestDialogMatching:
    """Test dialog matching per RFC 3261 §12.2."""

    def test_matches_correct_identifiers(self) -> None:
        """Dialog matches when Call-ID, local tag, and remote tag match."""
        req = make_invite_request(call_id="call-123", from_tag="from-tag")
        resp = make_invite_response(req, 200, "OK", to_tag="to-tag")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.matches("call-123", "from-tag", "to-tag") is True

    def test_rejects_wrong_call_id(self) -> None:
        """Dialog rejects mismatched Call-ID."""
        req = make_invite_request(call_id="call-123")
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.matches("wrong-call-id", "from-tag", "to-tag") is False

    def test_rejects_wrong_local_tag(self) -> None:
        """Dialog rejects mismatched local tag."""
        req = make_invite_request(from_tag="from-tag")
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.matches("call-123", "wrong-tag", "to-tag") is False

    def test_rejects_wrong_remote_tag(self) -> None:
        """Dialog rejects mismatched remote tag."""
        req = make_invite_request()
        resp = make_invite_response(req, 200, "OK", to_tag="to-tag")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.matches("call-123", "from-tag", "wrong-tag") is False

    def test_update_rejects_call_id_mismatch(self) -> None:
        """update() raises DialogError on Call-ID mismatch."""
        req = make_invite_request(call_id="call-123")
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        # Response with different Call-ID.
        bad_resp = Response(
            status_code=200,
            reason="OK",
            headers={
                "Call-ID": "different-call",
                "From": "<sip:alice@example.com>;tag=from-tag",
                "To": "<sip:bob@example.com>;tag=to-tag",
                "CSeq": "1 INVITE",
                "Contact": "<sip:bob@192.0.2.2:5060>",
            },
            body=None,
            request=req,
        )

        with pytest.raises(DialogError, match="Call-ID"):
            dialog.update(bad_resp)


# --- Route Set Management Tests ---


class TestRouteSetManagement:
    """Test route set management per RFC 3261 §12.1.2."""

    def test_route_set_from_record_route(self) -> None:
        """Dialog extracts route set from Record-Route headers."""
        req = make_invite_request()
        resp = make_invite_response(
            req,
            200,
            "OK",
            record_route=[
                "<sip:proxy1.example.com;lr>",
                "<sip:proxy2.example.com;lr>",
            ],
        )
        dialog = Dialog.from_invite(req, resp)

        # Route set is reversed per RFC 3261 §12.1.2.
        assert dialog.route_set == [
            "<sip:proxy2.example.com;lr>",
            "<sip:proxy1.example.com;lr>",
        ]

    def test_route_set_empty_without_record_route(self) -> None:
        """Dialog has empty route set when no Record-Route present."""
        req = make_invite_request()
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.route_set == []

    def test_route_set_refresh_on_2xx(self) -> None:
        """Route set is refreshed on 2xx response within dialog."""
        req = make_invite_request()
        resp_200 = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp_200)

        assert dialog.route_set == []

        # In-dialog request with new Record-Route.
        reinvite_resp = make_invite_response(
            req,
            200,
            "OK",
            record_route="<sip:new-proxy.example.com;lr>",
        )
        dialog.update(reinvite_resp)

        assert dialog.route_set == ["<sip:new-proxy.example.com;lr>"]


# --- CSeq Management Tests ---


class TestCSeqManagement:
    """Test CSeq number management per RFC 3261 §12.2.1.1."""

    def test_next_cseq_increments(self) -> None:
        """next_cseq() increments CSeq for non-ACK methods."""
        req = make_invite_request(cseq=1)
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        assert dialog.local_cseq == 1

        cseq = dialog.next_cseq("BYE")
        assert cseq == 2
        assert dialog.local_cseq == 2

    def test_ack_reuses_invite_cseq(self) -> None:
        """ACK reuses the INVITE CSeq number."""
        req = make_invite_request(cseq=1)
        resp = make_invite_response(req, 200, "OK")
        dialog = Dialog.from_invite(req, resp)

        cseq = dialog.next_cseq("ACK")
        assert cseq == 1  # Same as INVITE
        assert dialog.local_cseq == 1  # Not incremented


# --- Target Refresh Tests ---


class TestTargetRefresh:
    """Test remote target refresh per RFC 3261 §12.2.2."""

    def test_target_refresh_on_2xx(self) -> None:
        """Remote target is refreshed on 2xx response."""
        req = make_invite_request()
        resp = make_invite_response(
            req, 200, "OK", contact="<sip:bob@192.0.2.2:5060>"
        )
        dialog = Dialog.from_invite(req, resp)

        assert dialog.remote_target == "<sip:bob@192.0.2.2:5060>"

        # In-dialog response with new Contact.
        reinvite_resp = make_invite_response(
            req,
            200,
            "OK",
            contact="<sip:bob@192.0.2.3:5060>",
        )
        dialog.update(reinvite_resp)

        assert dialog.remote_target == "<sip:bob@192.0.2.3:5060>"


# --- DialogId Tests ---


class TestDialogId:
    """Test DialogId dataclass."""

    def test_dialog_id_equality(self) -> None:
        """DialogId equality works correctly."""
        id1 = DialogId("call-123", "local-tag", "remote-tag")
        id2 = DialogId("call-123", "local-tag", "remote-tag")
        id3 = DialogId("call-456", "local-tag", "remote-tag")

        assert id1 == id2
        assert id1 != id3

    def test_dialog_id_immutable(self) -> None:
        """DialogId is frozen (immutable)."""
        dialog_id = DialogId("call-123", "local-tag", "remote-tag")

        with pytest.raises(AttributeError):
            dialog_id.call_id = "new-call"  # type: ignore[misc]


# --- DialogState Tests ---


class TestDialogState:
    """Test DialogState enum."""

    def test_state_values(self) -> None:
        """DialogState has correct string values."""
        assert DialogState.EARLY.value == "Early"
        assert DialogState.CONFIRMED.value == "Confirmed"
        assert DialogState.TERMINATED.value == "Terminated"

    def test_state_string_comparison(self) -> None:
        """DialogState can be compared as strings."""
        assert DialogState.EARLY == "Early"
        assert DialogState.CONFIRMED == "Confirmed"
        assert DialogState.TERMINATED == "Terminated"
