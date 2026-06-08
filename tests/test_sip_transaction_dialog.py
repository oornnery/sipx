import pytest

from sipx import (
    ClientTransactionState,
    Dialog,
    DialogState,
    HeaderMap,
    InviteClientTransaction,
    SipRequest,
    SipResponse,
    SipTransactionError,
    SipUri,
    header_tag,
)


def invite_request() -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", "SIP/2.0/UDP caller.example.com;branch=z9hG4bK-1")
    headers.add("From", "<sip:alice@example.com>;tag=from-1")
    headers.add("To", "<sip:bob@example.com>")
    headers.add("Call-ID", "call-1")
    headers.add("CSeq", "1 INVITE")
    headers.add("Max-Forwards", "70")
    return SipRequest(
        method="INVITE", uri=SipUri.parse("sip:bob@example.com"), headers=headers
    )


def response(status_code: int, reason: str, *, to_tag: str = "to-1") -> SipResponse:
    headers = HeaderMap()
    headers.add("Via", "SIP/2.0/UDP caller.example.com;branch=z9hG4bK-1")
    headers.add("From", "<sip:alice@example.com>;tag=from-1")
    headers.add("To", f"<sip:bob@example.com>;tag={to_tag}")
    headers.add("Call-ID", "call-1")
    headers.add("CSeq", "1 INVITE")
    return SipResponse(status_code=status_code, reason=reason, headers=headers)


def test_invite_transaction_tracks_provisional_and_success_final() -> None:
    transaction = InviteClientTransaction(invite_request())

    assert transaction.branch == "z9hG4bK-1"
    assert (
        transaction.receive_response(response(100, "Trying"))
        == ClientTransactionState.PROCEEDING
    )
    assert (
        transaction.receive_response(response(200, "OK"))
        == ClientTransactionState.TERMINATED
    )
    assert transaction.final_response is not None
    assert transaction.final_response.status_code == 200
    assert [event.name for event in transaction.events] == [
        "request_sent",
        "provisional_response",
        "success_response",
    ]


def test_invite_transaction_failure_final_creates_ack() -> None:
    transaction = InviteClientTransaction(invite_request())
    transaction.receive_response(response(486, "Busy Here"))

    ack = transaction.create_ack()

    assert transaction.state == ClientTransactionState.TERMINATED
    assert ack.method == "ACK"
    assert ack.headers.get("CSeq") == "1 ACK"
    assert ack.headers.get("To") == "<sip:bob@example.com>;tag=to-1"


def test_invite_transaction_creates_cancel_before_final_response() -> None:
    transaction = InviteClientTransaction(invite_request())

    cancel = transaction.create_cancel()

    assert cancel.method == "CANCEL"
    assert cancel.headers.get("CSeq") == "1 CANCEL"
    assert (
        cancel.headers.get("Via") == "SIP/2.0/UDP caller.example.com;branch=z9hG4bK-1"
    )


def test_invite_transaction_rejects_cancel_after_final_response() -> None:
    transaction = InviteClientTransaction(invite_request())
    transaction.receive_response(response(200, "OK"))

    with pytest.raises(SipTransactionError):
        transaction.create_cancel()


def test_dialog_from_uac_invite_response_extracts_tags_and_state() -> None:
    dialog = Dialog.from_uac_invite_response(invite_request(), response(200, "OK"))

    assert dialog.dialog_id.call_id == "call-1"
    assert dialog.dialog_id.local_tag == "from-1"
    assert dialog.dialog_id.remote_tag == "to-1"
    assert dialog.state == DialogState.CONFIRMED
    assert dialog.next_local_cseq("BYE") == "2 BYE"


def test_header_tag_extracts_tag_parameter() -> None:
    assert header_tag("<sip:alice@example.com>;tag=abc;foo=bar") == "abc"
    assert header_tag("<sip:alice@example.com>") is None
