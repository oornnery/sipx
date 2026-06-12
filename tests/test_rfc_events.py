"""Tests for RFC 3265/6665 event notification framework."""

from __future__ import annotations

import pytest

from sipx.exceptions import ProtocolError
from sipx.models import Request, Response
from sipx.protocol.transaction import ClientTransaction
from sipx.rfc.events import SubscriptionDialog, SubscriptionState


def _subscribe_request(
    event: str = "presence",
    expires: str = "3600",
    method: str = "SUBSCRIBE",
) -> Request:
    return Request(
        method=method,
        uri="sip:bob@example.com",
        headers={
            "Event": event,
            "Expires": expires,
            "Call-ID": "call-001",
            "From": "sip:alice@example.com;tag=abc",
            "To": "sip:bob@example.com",
            "CSeq": "1 SUBSCRIBE",
        },
        body=None,
    )


def _subscribe_response(
    status_code: int = 200,
    reason: str = "OK",
    request: Request | None = None,
) -> Response:
    req = request or _subscribe_request()
    return Response(
        status_code=status_code,
        reason=reason,
        headers={
            "Expires": "3600",
            "To": "sip:bob@example.com;tag=xyz",
            "Contact": "sip:bob@192.168.1.1",
        },
        body=None,
        request=req,
    )


def _notify_request(
    state: str = "active",
    method: str = "NOTIFY",
) -> Request:
    headers: dict[str, str] = {
        "Call-ID": "call-001",
        "From": "sip:bob@example.com;tag=xyz",
        "To": "sip:alice@example.com;tag=abc",
    }
    if state:
        headers["Subscription-State"] = state
    return Request(
        method=method,
        uri="sip:alice@example.com",
        headers=headers,
        body=None,
    )


class TestSubscriptionDialogCreation:
    """SubscriptionDialog.from_subscribe factory."""

    def test_import(self):
        from sipx.rfc.events import SubscriptionDialog
        assert SubscriptionDialog is not None

    def test_create_active_from_200(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.state == "active"
        assert sub.event == "presence"

    def test_create_pending_from_202(self):
        req = _subscribe_request()
        resp = _subscribe_response(202, "Accepted", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.state == "pending"
        assert sub.event == "presence"

    def test_expires_parsed_from_request(self):
        req = _subscribe_request(expires="7200")
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.expires == 7200

    def test_dialog_identity_extracted(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.dialog_id.call_id == "call-001"
        assert sub.dialog_id.local_tag == "abc"
        assert sub.dialog_id.remote_tag == "xyz"

    def test_rejects_non_subscribe_request(self):
        req = _subscribe_request(method="INVITE")
        resp = _subscribe_response(200, "OK", request=req)
        with pytest.raises(ProtocolError, match="SUBSCRIBE"):
            SubscriptionDialog.from_subscribe(req, resp)

    def test_rejects_non_2xx_response(self):
        req = _subscribe_request()
        resp = _subscribe_response(403, "Forbidden", request=req)
        with pytest.raises(ProtocolError, match="cannot create"):
            SubscriptionDialog.from_subscribe(req, resp)

    def test_event_with_parameters(self):
        req = _subscribe_request(event="presence;param=value")
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.event == "presence"

    def test_missing_event_header_raises(self):
        req = Request(
            method="SUBSCRIBE",
            uri="sip:bob@example.com",
            headers={
                "Expires": "3600",
                "Call-ID": "call-001",
                "From": "sip:alice@example.com;tag=abc",
            },
            body=None,
        )
        resp = Response(
            status_code=200,
            reason="OK",
            headers={"To": "sip:bob@example.com;tag=xyz"},
            body=None,
            request=req,
        )
        with pytest.raises(ProtocolError):
            SubscriptionDialog.from_subscribe(req, resp)


class TestSubscriptionStateTransitions:
    """Subscription state transitions via NOTIFY."""

    def test_pending_to_active_via_notify(self):
        req = _subscribe_request()
        resp = _subscribe_response(202, "Accepted", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.state == "pending"

        notify = _notify_request(state="active")
        sub.update_from_notify(notify)
        assert sub.state == "active"

    def test_active_to_terminated_via_notify(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.state == "active"

        notify = _notify_request(state="terminated")
        sub.update_from_notify(notify)
        assert sub.state == "terminated"

    def test_pending_to_terminated_via_notify(self):
        req = _subscribe_request()
        resp = _subscribe_response(202, "Accepted", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        notify = _notify_request(state="terminated")
        sub.update_from_notify(notify)
        assert sub.state == "terminated"

    def test_invalid_transition_terminated_to_active(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        sub.terminate()
        assert sub.state == "terminated"

        notify = _notify_request(state="active")
        with pytest.raises(ProtocolError, match="invalid.*transition"):
            sub.update_from_notify(notify)

    def test_notify_without_state_header_preserves_state(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        notify = _notify_request(state="")
        notify.headers.pop("Subscription-State", None)
        sub.update_from_notify(notify)
        assert sub.state == "active"

    def test_notify_count_increments(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.notify_count == 0

        sub.update_from_notify(_notify_request(state="active"))
        assert sub.notify_count == 1

        sub.update_from_notify(_notify_request(state="terminated"))
        assert sub.notify_count == 2

    def test_rejects_non_notify_request(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        bad = _notify_request(method="INVITE")
        with pytest.raises(ProtocolError, match="NOTIFY"):
            sub.update_from_notify(bad)


class TestSubscriptionOperations:
    """Subscription refresh, termination, and request building."""

    def test_terminate(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        sub.terminate()
        assert sub.state == "terminated"
        assert sub.is_terminated

    def test_update_from_subscribe_response_refresh(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        refresh_resp = Response(
            status_code=200,
            reason="OK",
            headers={"Expires": "7200"},
            body=None,
            request=req,
        )
        sub.update_from_subscribe_response(refresh_resp)
        assert sub.expires == 7200
        assert sub.state == "active"

    def test_update_from_subscribe_response_error_terminates(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        error_resp = Response(
            status_code=403,
            reason="Forbidden",
            headers={},
            body=None,
            request=req,
        )
        sub.update_from_subscribe_response(error_resp)
        assert sub.state == "terminated"

    def test_create_subscribe_request(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        new_req = sub.create_subscribe_request()
        assert new_req.method == "SUBSCRIBE"
        assert new_req.headers["Event"] == "presence"
        assert new_req.headers["Expires"] == "3600"

    def test_create_subscribe_request_unsubscribe(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        unsub = sub.create_subscribe_request(expires=0)
        assert unsub.headers["Expires"] == "0"

    def test_create_notify_response(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)

        notify = _notify_request(state="active")
        notify_resp = sub.create_notify_response(notify)
        assert notify_resp.status_code == 200
        assert notify_resp.request is notify


class TestClientTransactionIntegration:
    """Integration with ClientTransaction."""

    def test_subscribe_with_transaction(self):
        req = _subscribe_request()
        txn = ClientTransaction(req)
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp, transaction=txn)
        assert sub.transaction is txn
        assert sub.transaction.state == "Trying"

    def test_subscribe_without_transaction(self):
        req = _subscribe_request()
        resp = _subscribe_response(200, "OK", request=req)
        sub = SubscriptionDialog.from_subscribe(req, resp)
        assert sub.transaction is None
