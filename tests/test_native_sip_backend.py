import asyncio

import pytest

from sipx import (
    HeaderMap,
    NativeSipBackend,
    NativeSipCallState,
    SipRequest,
    SipResponse,
    SipUdpError,
    SipUri,
    Timeline,
    create_register_request,
)


def register_request(branch: str = "z9hG4bK-register") -> SipRequest:
    return create_register_request(
        registrar=SipUri.parse("sip:example.com"),
        aor=SipUri.parse("sip:alice@example.com"),
        contact=SipUri.parse("sip:alice@127.0.0.1:5060"),
        call_id="register-1",
        branch=branch,
        from_tag="from-1",
        expires=3600,
    )


def ok_response() -> SipResponse:
    headers = HeaderMap()
    headers.add("Via", "SIP/2.0/UDP 127.0.0.1;branch=z9hG4bK-register")
    headers.add("From", "<sip:alice@example.com>;tag=from-1")
    headers.add("To", "<sip:alice@example.com>;tag=to-1")
    headers.add("Call-ID", "register-1")
    headers.add("CSeq", "1 REGISTER")
    return SipResponse(status_code=200, reason="OK", headers=headers)


def test_native_sip_backend_exchanges_request_and_response_over_udp() -> None:
    asyncio.run(_exchange_request_and_response())


async def _exchange_request_and_response() -> None:
    caller_timeline = Timeline(run_id="caller")
    callee_timeline = Timeline(run_id="callee")
    caller = NativeSipBackend(timeline=caller_timeline, actor_id="caller")
    callee = NativeSipBackend(timeline=callee_timeline, actor_id="callee")
    try:
        await caller.start()
        await callee.start()

        await caller.send_request(register_request(), callee.local_address)
        request_event = await callee.receive_event(timeout=1.0)

        assert request_event.remote == caller.local_address
        assert isinstance(request_event.message, SipRequest)
        assert request_event.message.method == "REGISTER"
        assert request_event.message.headers.get("Call-ID") == "register-1"

        await callee.send_response(ok_response(), request_event.remote)
        response_event = await caller.receive_event(timeout=1.0)

        assert response_event.remote == callee.local_address
        assert isinstance(response_event.message, SipResponse)
        assert response_event.message.status_code == 200
        assert response_event.message.headers.get("CSeq") == "1 REGISTER"
    finally:
        await caller.stop()
        await callee.stop()

    caller_names = [event.name for event in caller_timeline.events]
    callee_names = [event.name for event in callee_timeline.events]
    assert "transport_started" in caller_names
    assert "request_sent" in caller_names
    assert "response_received" in caller_names
    assert "request_received" in callee_names
    assert "response_sent" in callee_names


def test_native_sip_backend_reports_malformed_datagram_without_crashing() -> None:
    asyncio.run(_send_malformed_datagram())


async def _send_malformed_datagram() -> None:
    sender = NativeSipBackend(mode="lab")
    receiver = NativeSipBackend()
    try:
        await sender.start()
        await receiver.start()

        await sender.send_raw(b"not sip\r\n\r\n", receiver.local_address)
        event = await receiver.receive_event(timeout=1.0)

        assert event.is_error
        assert event.message is None
        assert "invalid SIP request line" in (event.error or "")
    finally:
        await sender.stop()
        await receiver.stop()


def test_native_sip_backend_rejects_raw_send_in_strict_mode() -> None:
    asyncio.run(_reject_raw_send_in_strict_mode())


async def _reject_raw_send_in_strict_mode() -> None:
    backend = NativeSipBackend()
    try:
        await backend.start()
        with pytest.raises(SipUdpError):
            await backend.send_raw(b"not sip\r\n\r\n", backend.local_address)
    finally:
        await backend.stop()


def test_native_sip_backend_receive_timeout_raises_typed_error() -> None:
    asyncio.run(_receive_timeout())


async def _receive_timeout() -> None:
    backend = NativeSipBackend()
    try:
        await backend.start()
        with pytest.raises(SipUdpError, match="timed out"):
            await backend.receive_event(timeout=0.01)
    finally:
        await backend.stop()


def test_native_sip_backend_runs_strict_invite_ack_bye_call_flow() -> None:
    asyncio.run(_strict_call_flow())


async def _strict_call_flow() -> None:
    caller_timeline = Timeline(run_id="strict-caller")
    callee_timeline = Timeline(run_id="strict-callee")
    caller = NativeSipBackend(timeline=caller_timeline, actor_id="caller")
    callee = NativeSipBackend(timeline=callee_timeline, actor_id="callee")
    try:
        await caller.start()
        await callee.start()
        caller_contact = SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}")
        callee_contact = SipUri.parse(f"sip:bob@127.0.0.1:{callee.local_address[1]}")

        accept_task = asyncio.create_task(
            callee.accept_call(
                local_tag="callee-tag",
                contact=callee_contact,
                timeout=1.0,
            )
        )
        caller_call = await caller.initiate_call(
            remote=callee.local_address,
            target=SipUri.parse("sip:bob@example.com"),
            caller=SipUri.parse("sip:alice@example.com"),
            contact=caller_contact,
            call_id="call-1",
            branch="z9hG4bK-invite",
            from_tag="caller-tag",
            ack_branch="z9hG4bK-ack",
            timeout=1.0,
        )
        callee_call = await accept_task

        assert caller_call.state == NativeSipCallState.CONFIRMED
        assert callee_call.state == NativeSipCallState.CONFIRMED
        assert caller_call.dialog.dialog_id.local_tag == "caller-tag"
        assert caller_call.dialog.dialog_id.remote_tag == "callee-tag"
        assert callee_call.dialog.dialog_id.local_tag == "callee-tag"
        assert callee_call.dialog.dialog_id.remote_tag == "caller-tag"

        answer_bye_task = asyncio.create_task(
            callee.answer_bye(callee_call, timeout=1.0)
        )
        bye_response = await caller.hangup_call(
            caller_call,
            branch="z9hG4bK-bye",
            timeout=1.0,
        )
        await answer_bye_task

        assert bye_response.status_code == 200
        assert caller_call.state == NativeSipCallState.TERMINATED
        assert callee_call.state == NativeSipCallState.TERMINATED
    finally:
        await caller.stop()
        await callee.stop()

    caller_call_events = [
        event.name for event in caller_timeline.events if event.category == "call"
    ]
    callee_call_events = [
        event.name for event in callee_timeline.events if event.category == "call"
    ]
    assert caller_call_events == ["invite_sent", "confirmed", "terminated"]
    assert callee_call_events == ["invite_received", "confirmed", "terminated"]


def test_native_sip_backend_cancels_pending_invite_over_udp() -> None:
    asyncio.run(_cancel_pending_invite())


async def _cancel_pending_invite() -> None:
    caller_timeline = Timeline(run_id="cancel-caller")
    callee_timeline = Timeline(run_id="cancel-callee")
    caller = NativeSipBackend(timeline=caller_timeline, actor_id="caller")
    callee = NativeSipBackend(timeline=callee_timeline, actor_id="callee")
    try:
        await caller.start()
        await callee.start()
        caller_contact = SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}")

        receive_task = asyncio.create_task(callee.receive_invite(timeout=1.0))
        invite = await caller.start_invite(
            remote=callee.local_address,
            target=SipUri.parse("sip:bob@example.com"),
            caller=SipUri.parse("sip:alice@example.com"),
            contact=caller_contact,
            call_id="cancel-call-1",
            branch="z9hG4bK-cancel-invite",
            from_tag="caller-tag",
        )
        incoming = await receive_task

        answer_cancel_task = asyncio.create_task(
            callee.answer_cancel(
                incoming,
                local_tag="callee-tag",
                timeout=1.0,
            )
        )
        invite_final = await caller.cancel_invite(invite, timeout=1.0)
        uas_final = await answer_cancel_task

        assert invite_final.status_code == 487
        assert invite_final.reason == "Request Terminated"
        assert uas_final.status_code == 487
    finally:
        await caller.stop()
        await callee.stop()

    caller_call_events = [
        event.name for event in caller_timeline.events if event.category == "call"
    ]
    callee_call_events = [
        event.name for event in callee_timeline.events if event.category == "call"
    ]
    assert caller_call_events == ["invite_sent", "cancelled"]
    assert callee_call_events == ["invite_received", "cancelled"]
