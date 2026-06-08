import pytest

from sipx import (
    ClientTransactionState,
    Dialog,
    DialogState,
    HeaderMap,
    InviteClientTransaction,
    InviteServerTransaction,
    ServerTransactionState,
    SipRequest,
    SipResponse,
    SipTransactionError,
    SipUri,
    create_bye_request,
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


def ack_request(*, branch: str = "z9hG4bK-1") -> SipRequest:
    headers = HeaderMap()
    headers.add("Via", f"SIP/2.0/UDP caller.example.com;branch={branch}")
    headers.add("From", "<sip:alice@example.com>;tag=from-1")
    headers.add("To", "<sip:bob@example.com>;tag=to-1")
    headers.add("Call-ID", "call-1")
    headers.add("CSeq", "1 ACK")
    return SipRequest(
        method="ACK", uri=SipUri.parse("sip:bob@example.com"), headers=headers
    )


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


def test_invite_server_transaction_tracks_success_final() -> None:
    transaction = InviteServerTransaction(invite_request())

    assert transaction.branch == "z9hG4bK-1"
    assert (
        transaction.send_response(response(180, "Ringing"))
        == ServerTransactionState.PROCEEDING
    )
    assert (
        transaction.send_response(response(200, "OK"))
        == ServerTransactionState.TERMINATED
    )
    assert transaction.final_response is not None
    assert transaction.final_response.status_code == 200
    assert [event.name for event in transaction.events] == [
        "request_received",
        "provisional_response",
        "success_response",
    ]


def test_invite_server_transaction_failure_final_accepts_matching_ack() -> None:
    transaction = InviteServerTransaction(invite_request())
    transaction.send_response(response(486, "Busy Here"))

    state = transaction.receive_ack(ack_request())

    assert state == ServerTransactionState.CONFIRMED
    transaction.terminate()
    assert transaction.state == ServerTransactionState.TERMINATED


def test_invite_server_transaction_rejects_ack_with_wrong_branch() -> None:
    transaction = InviteServerTransaction(invite_request())
    transaction.send_response(response(486, "Busy Here"))

    with pytest.raises(SipTransactionError):
        transaction.receive_ack(ack_request(branch="z9hG4bK-other"))


def test_dialog_from_uac_invite_response_extracts_tags_and_state() -> None:
    dialog = Dialog.from_uac_invite_response(invite_request(), response(200, "OK"))

    assert dialog.dialog_id.call_id == "call-1"
    assert dialog.dialog_id.local_tag == "from-1"
    assert dialog.dialog_id.remote_tag == "to-1"
    assert dialog.state == DialogState.CONFIRMED
    assert dialog.next_local_cseq("BYE") == "2 BYE"


def test_dialog_from_uas_invite_request_adds_local_tag() -> None:
    dialog = Dialog.from_uas_invite_request(invite_request(), local_tag="to-1")

    assert dialog.dialog_id.call_id == "call-1"
    assert dialog.dialog_id.local_tag == "to-1"
    assert dialog.dialog_id.remote_tag == "from-1"
    assert dialog.local_uri == "<sip:bob@example.com>;tag=to-1"
    assert dialog.remote_uri == "<sip:alice@example.com>;tag=from-1"
    assert dialog.remote_sequence == 1
    assert dialog.state == DialogState.EARLY


def test_create_bye_request_uses_dialog_identity_and_next_cseq() -> None:
    dialog = Dialog.from_uac_invite_response(invite_request(), response(200, "OK"))

    bye = create_bye_request(
        dialog=dialog,
        request_uri=SipUri.parse("sip:bob@example.com"),
        via_host="caller.example.com",
        branch="z9hG4bK-bye",
    )

    assert bye.method == "BYE"
    assert bye.headers.get("Via") == "SIP/2.0/UDP caller.example.com;branch=z9hG4bK-bye"
    assert bye.headers.get("From") == "<sip:alice@example.com>;tag=from-1"
    assert bye.headers.get("To") == "<sip:bob@example.com>;tag=to-1"
    assert bye.headers.get("Call-ID") == "call-1"
    assert bye.headers.get("CSeq") == "2 BYE"

    dialog.terminate()
    assert dialog.state == DialogState.TERMINATED


def test_header_tag_extracts_tag_parameter() -> None:
    assert header_tag("<sip:alice@example.com>;tag=abc;foo=bar") == "abc"
    assert header_tag("<sip:alice@example.com>") is None
