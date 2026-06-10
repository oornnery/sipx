import asyncio
from types import SimpleNamespace

import pytest

from sipx.uac import SipUac as ModuleSipUac
from sipx.uas import SipUas as ModuleSipUas
from sipx import (
    HeaderMap,
    RegisterClientState,
    SipCallState,
    SipProvisionalResponse,
    SipRequest,
    SipResponse,
    SipRetransmissionPolicy,
    SipUac,
    SipUacError,
    SipUacRuntime,
    SipUas,
    SipUasError,
    SipUasRuntime,
    SipUserAgent,
    SipUdpError,
    SipUri,
    SipWireDirection,
    SipWireEvent,
    SipWireRuntime,
    create_invite_request,
    create_register_request,
    create_response_for_request,
)


class EventRecorder:
    def __init__(self, run_id: str = "test") -> None:
        self.run_id = run_id
        self.events = []

    def record(self, category: str, name: str, **kwargs):
        event = SimpleNamespace(category=category, name=name, **kwargs)
        self.events.append(event)
        return event


def test_sip_uac_uas_roles_implement_runtime_abcs() -> None:
    uac = SipUac()
    uas = SipUas()
    user_agent = SipUserAgent()

    assert isinstance(user_agent, SipWireRuntime)
    assert isinstance(uac, SipUacRuntime)
    assert isinstance(uas, SipUasRuntime)


def test_sip_uac_uas_roles_live_in_split_modules() -> None:
    assert SipUac is ModuleSipUac
    assert SipUas is ModuleSipUas
    assert SipUac.__module__ == "sipx.uac"
    assert SipUas.__module__ == "sipx.uas"


def test_sip_uac_uas_high_level_contact_requires_start() -> None:
    with pytest.raises(SipUacError, match="started"):
        _ = SipUac(aor="sip:alice@example.com").contact
    with pytest.raises(SipUasError, match="started"):
        _ = SipUas(aor="sip:bob@example.com").contact


def test_sip_uac_high_level_registers_and_unregisters() -> None:
    asyncio.run(_uac_high_level_registers_and_unregisters())


async def _uac_high_level_registers_and_unregisters() -> None:
    registrar = SipUas(actor_id="registrar")
    try:
        await registrar.start()
        uac = SipUac(
            aor="sip:alice@example.com",
            registrar="sip:example.com",
            remote=registrar.local_address,
            contact_user="alice",
            timeout=1.0,
            actor_id="alice",
        )
        await uac.start()
        try:
            responder = asyncio.create_task(_register_unregister_responder(registrar))

            registered = await uac.register(call_id="uac-register-1")
            unregistered = await uac.unregister(call_id="uac-unregister-1")
            contacts = await responder

            assert registered is RegisterClientState.REGISTERED
            assert unregistered is RegisterClientState.UNREGISTERED
            assert contacts == [
                f"<sip:alice@127.0.0.1:{uac.local_address[1]}>",
                f"<sip:alice@127.0.0.1:{uac.local_address[1]}>",
            ]
        finally:
            await uac.stop()
    finally:
        await registrar.stop()


async def _register_unregister_responder(registrar: SipUas) -> list[str]:
    contacts: list[str] = []
    for _ in range(2):
        event = await registrar.receive_event(timeout=1.0)
        request = event.message
        assert isinstance(request, SipRequest)
        assert request.method == "REGISTER"
        contacts.append(request.headers.get("Contact") or "")
        response = create_response_for_request(
            request=request,
            status_code=200,
            reason="OK",
        )
        await registrar.send_response(response, event.remote)
    return contacts


def test_sip_uac_uas_high_level_call_answer_and_hangup() -> None:
    asyncio.run(_uac_uas_high_level_call_answer_and_hangup())


async def _uac_uas_high_level_call_answer_and_hangup() -> None:
    caller = SipUac(
        aor="sip:alice@example.com",
        timeout=1.0,
        actor_id="alice",
    )
    callee = SipUas(
        aor="sip:bob@example.com",
        timeout=1.0,
        actor_id="bob",
    )
    try:
        await caller.start()
        await callee.start()
        caller.remote = callee.local_address

        answer_task = asyncio.create_task(callee.answer(local_tag="bob-tag"))
        call = await caller.call("sip:bob@example.com", call_id="uac-uas-high-level-1")
        callee_call = await answer_task

        assert call.state is SipCallState.CONFIRMED
        assert callee_call.state is SipCallState.CONFIRMED
        assert call.local_sdp is not None
        assert call.remote_sdp is not None
        assert call.local_sdp.has_codec("PCMU")
        assert callee_call.local_sdp is not None
        assert callee_call.remote_sdp is not None

        wait_hangup = asyncio.create_task(callee.wait_hangup(callee_call))
        await caller.hangup(call)
        await wait_hangup

        assert call.state is SipCallState.TERMINATED
        assert callee_call.state is SipCallState.TERMINATED
    finally:
        await caller.stop()
        await callee.stop()


def test_v62_uas_answer_can_skip_invite_provisionals() -> None:
    asyncio.run(_uas_answer_can_skip_invite_provisionals())


async def _uas_answer_can_skip_invite_provisionals() -> None:
    responses: list[SipResponse] = []
    caller = SipUac(
        aor="sip:alice@example.com",
        timeout=1.0,
        event_hooks={"wire": [lambda e: _capture_invite_response(e, responses)]},
    )
    callee = SipUas(aor="sip:bob@example.com", timeout=1.0)
    try:
        await caller.start()
        await callee.start()
        caller.remote = callee.local_address

        answer_task = asyncio.create_task(
            callee.answer(local_tag="bob-tag", provisionals=())
        )
        call = await caller.call("sip:bob@example.com", call_id="direct-final-1")
        callee_call = await answer_task

        assert [response.status_code for response in responses] == [200]

        wait_hangup = asyncio.create_task(callee.wait_hangup(callee_call))
        await caller.hangup(call)
        await wait_hangup
    finally:
        await caller.stop()
        await callee.stop()


def test_v62_uas_answer_defaults_to_180_ringing() -> None:
    asyncio.run(_uas_answer_defaults_to_180_ringing())


async def _uas_answer_defaults_to_180_ringing() -> None:
    responses: list[SipResponse] = []
    caller = SipUac(
        aor="sip:alice@example.com",
        timeout=1.0,
        event_hooks={"wire": [lambda e: _capture_invite_response(e, responses)]},
    )
    callee = SipUas(aor="sip:bob@example.com", timeout=1.0)
    try:
        await caller.start()
        await callee.start()
        caller.remote = callee.local_address

        answer_task = asyncio.create_task(callee.answer(local_tag="bob-tag"))
        call = await caller.call("sip:bob@example.com", call_id="default-ringing-1")
        callee_call = await answer_task

        assert [response.status_code for response in responses] == [180, 200]

        wait_hangup = asyncio.create_task(callee.wait_hangup(callee_call))
        await caller.hangup(call)
        await wait_hangup
    finally:
        await caller.stop()
        await callee.stop()


def test_v62_v63_uas_answer_sends_configured_provisionals_with_sdp() -> None:
    asyncio.run(_uas_answer_sends_configured_provisionals_with_sdp())


async def _uas_answer_sends_configured_provisionals_with_sdp() -> None:
    responses: list[SipResponse] = []
    caller = SipUac(
        aor="sip:alice@example.com",
        timeout=1.0,
        event_hooks={"wire": [lambda e: _capture_invite_response(e, responses)]},
    )
    callee = SipUas(aor="sip:bob@example.com", timeout=1.0)
    try:
        await caller.start()
        await callee.start()
        caller.remote = callee.local_address

        answer_task = asyncio.create_task(
            callee.answer(
                local_tag="bob-tag",
                provisionals=(
                    SipProvisionalResponse.trying(),
                    SipProvisionalResponse.session_progress(include_sdp=True),
                ),
            )
        )
        call = await caller.call("sip:bob@example.com", call_id="progress-sdp-1")
        callee_call = await answer_task

        assert [response.status_code for response in responses] == [100, 183, 200]
        trying, progress, final = responses
        assert "tag=" not in (trying.headers.get("To") or "")
        assert trying.headers.get("Contact") is None
        assert trying.headers.get("Content-Type") is None
        assert trying.body == b""
        assert "tag=bob-tag" in (progress.headers.get("To") or "")
        assert progress.headers.get("Contact") is not None
        assert progress.headers.get("Content-Type") == "application/sdp"
        assert b"m=audio" in progress.body
        assert final.headers.get("Content-Type") == "application/sdp"

        wait_hangup = asyncio.create_task(callee.wait_hangup(callee_call))
        await caller.hangup(call)
        await wait_hangup
    finally:
        await caller.stop()
        await callee.stop()


def test_v63_sip_provisional_response_validates_trying_shape() -> None:
    with pytest.raises(ValueError, match="100 Trying"):
        SipProvisionalResponse(
            status_code=100,
            reason="Trying",
            body=b"early",
            content_type="text/plain",
        )
    with pytest.raises(ValueError, match="between 100 and 199"):
        SipProvisionalResponse(status_code=200, reason="OK")
    with pytest.raises(ValueError, match="body requires content_type"):
        SipProvisionalResponse(status_code=183, reason="Session Progress", body=b"x")


def _capture_invite_response(
    event: SipWireEvent,
    responses: list[SipResponse],
) -> None:
    if event.direction != SipWireDirection.RX:
        return
    message = event.message
    if not isinstance(message, SipResponse):
        return
    if (message.headers.get("CSeq") or "").endswith(" INVITE"):
        responses.append(message)


def test_sip_uac_uas_high_level_call_sends_synthetic_rtp() -> None:
    asyncio.run(_uac_uas_high_level_call_sends_synthetic_rtp())


async def _uac_uas_high_level_call_sends_synthetic_rtp() -> None:
    caller = SipUac(
        aor="sip:alice@example.com",
        timeout=1.0,
        actor_id="alice",
    )
    callee = SipUas(
        aor="sip:bob@example.com",
        timeout=1.0,
        actor_id="bob",
    )
    try:
        await caller.start()
        await callee.start()
        caller.remote = callee.local_address

        answer_task = asyncio.create_task(
            callee.answer(local_tag="bob-tag", audio="silence")
        )
        call = await caller.call(
            "sip:bob@example.com",
            call_id="uac-uas-synthetic-rtp-1",
            audio="noise",
        )
        callee_call = await answer_task
        await asyncio.sleep(0.05)

        caller_rtp = caller.rtp_session(call)
        callee_rtp = callee.rtp_session(callee_call)
        assert caller_rtp is not None
        assert callee_rtp is not None
        assert caller_rtp.metrics.tx_packets > 0
        assert callee_rtp.metrics.tx_packets > 0

        wait_hangup = asyncio.create_task(callee.wait_hangup(callee_call))
        await caller.hangup(call)
        await wait_hangup

        assert caller.rtp_session(call) is None
        assert callee.rtp_session(callee_call) is None
    finally:
        await caller.stop()
        await callee.stop()


def test_v59_sip_uac_uas_separate_rtp_bind_and_advertise_hosts() -> None:
    asyncio.run(_uac_uas_separate_rtp_bind_and_advertise_hosts())


async def _uac_uas_separate_rtp_bind_and_advertise_hosts() -> None:
    caller = SipUac(
        aor="sip:alice@example.com",
        timeout=1.0,
        rtp_bind_host="127.0.0.1",
        rtp_advertise_host="203.0.113.10",
    )
    callee = SipUas(
        aor="sip:bob@example.com",
        timeout=1.0,
        rtp_bind_host="127.0.0.1",
        rtp_advertise_host="203.0.113.20",
    )
    try:
        await caller.start()
        await callee.start()
        caller.remote = callee.local_address

        answer_task = asyncio.create_task(callee.answer(local_tag="bob-tag"))
        call = await caller.call(
            "sip:bob@example.com",
            call_id="uac-uas-rtp-advertise-1",
        )
        callee_call = await answer_task

        assert callee_call.remote_sdp is not None
        assert call.remote_sdp is not None
        assert callee_call.remote_sdp.connection_address == "203.0.113.10"
        assert call.remote_sdp.connection_address == "203.0.113.20"

        wait_hangup = asyncio.create_task(callee.wait_hangup(callee_call))
        await caller.hangup(call)
        await wait_hangup
    finally:
        await caller.stop()
        await callee.stop()


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


def test_sip_user_agent_exchanges_request_and_response_over_udp() -> None:
    asyncio.run(_exchange_request_and_response())


async def _exchange_request_and_response() -> None:
    caller_timeline = EventRecorder(run_id="caller")
    callee_timeline = EventRecorder(run_id="callee")
    caller = SipUac(timeline=caller_timeline, actor_id="caller")
    callee = SipUas(timeline=callee_timeline, actor_id="callee")
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


def test_sip_user_agent_reports_malformed_datagram_without_crashing() -> None:
    asyncio.run(_send_malformed_datagram())


async def _send_malformed_datagram() -> None:
    sender = SipUserAgent(mode="lab")
    receiver = SipUserAgent()
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


def test_sip_user_agent_rejects_raw_send_in_strict_mode() -> None:
    asyncio.run(_reject_raw_send_in_strict_mode())


async def _reject_raw_send_in_strict_mode() -> None:
    user_agent = SipUserAgent()
    try:
        await user_agent.start()
        with pytest.raises(SipUdpError):
            await user_agent.send_raw(b"not sip\r\n\r\n", user_agent.local_address)
    finally:
        await user_agent.stop()


def test_sip_user_agent_rejects_lab_event_hooks_in_strict_mode() -> None:
    with pytest.raises(ValueError, match="requires lab mode"):
        SipUserAgent(event_hooks={"sdp": [lambda m, b: None]})


def test_sip_user_agent_event_hook_mutates_outbound_headers() -> None:
    asyncio.run(_event_hook_mutates_outbound_headers())


async def _event_hook_mutates_outbound_headers() -> None:
    def add_lab_header(request: SipRequest, remote: tuple[str, int]) -> None:
        request.headers.add("X-Sipx-Lab", "header-hook")

    sender = SipUserAgent(
        mode="lab",
        event_hooks={"request": [add_lab_header]},
    )
    receiver = SipUserAgent()
    try:
        await sender.start()
        await receiver.start()

        await sender.send_request(register_request(), receiver.local_address)
        event = await receiver.receive_event(timeout=1.0)

        request = event.message
        assert isinstance(request, SipRequest)
        assert request.headers.get("X-Sipx-Lab") == "header-hook"
    finally:
        await sender.stop()
        await receiver.stop()


def test_sip_user_agent_event_hook_mutates_sdp_body() -> None:
    asyncio.run(_event_hook_mutates_sdp_body())


async def _event_hook_mutates_sdp_body() -> None:
    def add_sdp_attribute(message: object, body: bytes) -> None:
        if isinstance(message, SipRequest):
            message.body = body + b"a=sipx-lab:yes\r\n"

    sender = SipUserAgent(
        mode="lab",
        event_hooks={"sdp": [add_sdp_attribute]},
    )
    receiver = SipUserAgent()
    try:
        await sender.start()
        await receiver.start()
        request = create_invite_request(
            target=SipUri.parse("sip:bob@example.com"),
            caller=SipUri.parse("sip:alice@example.com"),
            contact=SipUri.parse(f"sip:alice@127.0.0.1:{sender.local_address[1]}"),
            call_id="sdp-hook-1",
            branch="z9hG4bK-sdp-hook",
            from_tag="alice-tag",
            body=b"v=0\r\ns=sipx\r\n",
            content_type="application/sdp",
        )

        await sender.send_request(request, receiver.local_address)
        event = await receiver.receive_event(timeout=1.0)

        received = event.message
        assert isinstance(received, SipRequest)
        assert received.body.endswith(b"a=sipx-lab:yes\r\n")
        assert received.headers.get_int("Content-Length") == len(received.body)
    finally:
        await sender.stop()
        await receiver.stop()


def test_sip_user_agent_event_hook_observes_received_events() -> None:
    asyncio.run(_event_hook_observes_received_events())


async def _event_hook_observes_received_events() -> None:
    seen: list[tuple[str, int, str]] = []

    def observe_request(request: SipRequest, remote: tuple[str, int]) -> None:
        seen.append((remote[0], remote[1], request.method))

    timeline = EventRecorder(run_id="receive-hook")
    sender = SipUserAgent()
    receiver = SipUserAgent(
        timeline=timeline,
        event_hooks={"request": [observe_request]},
    )
    try:
        await sender.start()
        await receiver.start()

        await sender.send_request(register_request(), receiver.local_address)
        event = await receiver.receive_event(timeout=1.0)

        assert isinstance(event.message, SipRequest)
        assert seen == [(sender.local_address[0], sender.local_address[1], "REGISTER")]
    finally:
        await sender.stop()
        await receiver.stop()

    assert any(event.name == "request_received" for event in timeline.events)


def test_sip_user_agent_receive_timeout_raises_typed_error() -> None:
    asyncio.run(_receive_timeout())


async def _receive_timeout() -> None:
    user_agent = SipUserAgent()
    try:
        await user_agent.start()
        with pytest.raises(SipUdpError, match="timed out"):
            await user_agent.receive_event(timeout=0.01)
    finally:
        await user_agent.stop()


def test_sip_uac_waits_after_invite_provisional_response() -> None:
    asyncio.run(_wait_after_invite_provisional_response())


async def _wait_after_invite_provisional_response() -> None:
    caller = SipUac(actor_id="caller")
    callee = SipUas(actor_id="callee")
    try:
        await caller.start()
        await callee.start()
        responder = asyncio.create_task(_send_invite_session_progress(callee))
        call_task = asyncio.create_task(
            caller.initiate_call(
                remote=callee.local_address,
                target=SipUri.parse("sip:bob@example.com"),
                caller=SipUri.parse("sip:alice@example.com"),
                contact=SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}"),
                call_id="provisional-call-1",
                branch="z9hG4bK-provisional-invite",
                from_tag="caller-tag",
                ack_branch="z9hG4bK-provisional-ack",
                timeout=0.05,
            )
        )

        await responder
        await asyncio.sleep(0.15)

        assert not call_task.done()
        call_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call_task
    finally:
        await caller.stop()
        await callee.stop()


async def _send_invite_session_progress(callee: SipUas) -> None:
    event = await callee.receive_event(timeout=1.0)
    request = event.message
    assert isinstance(request, SipRequest)
    assert request.method == "INVITE"
    response = create_response_for_request(
        request=request,
        status_code=183,
        reason="Session Progress",
        to_tag="callee-tag",
    )
    await callee.send_response(response, event.remote)


def test_sip_user_agent_runs_strict_invite_ack_bye_call_flow() -> None:
    asyncio.run(_strict_call_flow())


async def _strict_call_flow() -> None:
    caller_timeline = EventRecorder(run_id="strict-caller")
    callee_timeline = EventRecorder(run_id="strict-callee")
    caller = SipUac(timeline=caller_timeline, actor_id="caller")
    callee = SipUas(timeline=callee_timeline, actor_id="callee")
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

        assert caller_call.state == SipCallState.CONFIRMED
        assert callee_call.state == SipCallState.CONFIRMED
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
        assert caller_call.state == SipCallState.TERMINATED
        assert callee_call.state == SipCallState.TERMINATED
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


def test_sip_user_agent_retries_invite_with_digest_auth() -> None:
    asyncio.run(_invite_with_digest_auth())


async def _invite_with_digest_auth() -> None:
    caller_timeline = EventRecorder(run_id="digest-caller")
    caller = SipUac(timeline=caller_timeline, actor_id="caller")
    proxy = SipUas(actor_id="proxy")
    try:
        await caller.start()
        await proxy.start()
        proxy_task = asyncio.create_task(_digest_invite_responder(proxy))

        call = await caller.initiate_call(
            remote=proxy.local_address,
            target=SipUri.parse("sip:bob@example.com"),
            caller=SipUri.parse("sip:alice@example.com"),
            contact=SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}"),
            call_id="digest-call-1",
            branch="z9hG4bK-digest-invite",
            from_tag="caller-tag",
            ack_branch="z9hG4bK-digest-ack",
            username="alice",
            password="secret-password",
            auth_branch="z9hG4bK-digest-invite-auth",
            cnonce="cnonce-1",
            timeout=1.0,
        )
        authorization = await proxy_task

        assert call.state == SipCallState.CONFIRMED
        assert 'username="alice"' in authorization
        assert 'nonce="nonce-1"' in authorization
        assert "secret-password" not in authorization
    finally:
        await caller.stop()
        await proxy.stop()

    caller_call_events = [
        event.name for event in caller_timeline.events if event.category == "call"
    ]
    assert caller_call_events == ["invite_sent", "auth_challenged", "confirmed"]


async def _digest_invite_responder(proxy: SipUas) -> str:
    first = await proxy.receive_event(timeout=1.0)
    first_request = first.message
    assert isinstance(first_request, SipRequest)
    assert first_request.method == "INVITE"

    challenge = create_response_for_request(
        request=first_request,
        status_code=407,
        reason="Proxy Authentication Required",
    )
    challenge.headers.add(
        "Proxy-Authenticate",
        'Digest realm="example.com", nonce="nonce-1", qop="auth"',
    )
    await proxy.send_response(challenge, first.remote)

    challenge_ack = await proxy.receive_event(timeout=1.0)
    challenge_ack_request = challenge_ack.message
    assert isinstance(challenge_ack_request, SipRequest)
    assert challenge_ack_request.method == "ACK"

    second = await proxy.receive_event(timeout=1.0)
    second_request = second.message
    assert isinstance(second_request, SipRequest)
    assert second_request.method == "INVITE"
    assert second_request.headers.get("CSeq") == "2 INVITE"
    authorization = second_request.headers.get("Proxy-Authorization") or ""

    await proxy.send_response(challenge, second.remote)

    ok = create_response_for_request(
        request=second_request,
        status_code=200,
        reason="OK",
        to_tag="proxy-tag",
        contact=SipUri.parse("sip:bob@127.0.0.1:5060"),
    )
    await proxy.send_response(ok, second.remote)

    final_ack = await proxy.receive_event(timeout=1.0)
    final_ack_request = final_ack.message
    assert isinstance(final_ack_request, SipRequest)
    assert final_ack_request.method == "ACK"
    return authorization


def test_sip_user_agent_cancels_pending_invite_over_udp() -> None:
    asyncio.run(_cancel_pending_invite())


async def _cancel_pending_invite() -> None:
    caller_timeline = EventRecorder(run_id="cancel-caller")
    callee_timeline = EventRecorder(run_id="cancel-callee")
    caller = SipUac(timeline=caller_timeline, actor_id="caller")
    callee = SipUas(timeline=callee_timeline, actor_id="callee")
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


def test_sip_user_agent_registers_with_digest_over_udp() -> None:
    asyncio.run(_register_with_digest())


async def _register_with_digest() -> None:
    client = SipUac(actor_id="client")
    registrar = SipUas(actor_id="registrar")
    try:
        await client.start()
        await registrar.start()
        registrar_task = asyncio.create_task(_digest_register_responder(registrar))

        state = await client.register_account(
            remote=registrar.local_address,
            registrar=SipUri.parse("sip:example.com"),
            aor=SipUri.parse("sip:alice@example.com"),
            contact=SipUri.parse(f"sip:alice@127.0.0.1:{client.local_address[1]}"),
            call_id="register-call-1",
            branch="z9hG4bK-register",
            from_tag="from-tag",
            username="alice",
            password="secret-password",
            auth_branch="z9hG4bK-register-auth",
            cnonce="cnonce-1",
            timeout=1.0,
        )
        authorization = await registrar_task

        assert state == RegisterClientState.REGISTERED
        assert 'username="alice"' in authorization
        assert 'nonce="nonce-1"' in authorization
        assert "secret-password" not in authorization
    finally:
        await client.stop()
        await registrar.stop()


async def _digest_register_responder(registrar: SipUas) -> str:
    first = await registrar.receive_event(timeout=1.0)
    first_request = first.message
    assert isinstance(first_request, SipRequest)
    assert first_request.method == "REGISTER"
    trying = create_response_for_request(
        request=first_request,
        status_code=100,
        reason="Trying",
    )
    await registrar.send_response(trying, first.remote)
    challenge = create_response_for_request(
        request=first_request,
        status_code=401,
        reason="Unauthorized",
    )
    challenge.headers.add(
        "WWW-Authenticate",
        'Digest realm="example.com", nonce="nonce-1", qop="auth"',
    )
    await registrar.send_response(challenge, first.remote)

    second = await registrar.receive_event(timeout=1.0)
    second_request = second.message
    assert isinstance(second_request, SipRequest)
    assert second_request.headers.get("CSeq") == "2 REGISTER"
    authorization = second_request.headers.get("Authorization") or ""
    trying = create_response_for_request(
        request=second_request,
        status_code=100,
        reason="Trying",
    )
    await registrar.send_response(trying, second.remote)
    with pytest.raises(SipUdpError, match="timed out"):
        await registrar.receive_event(timeout=0.05)
    ok = create_response_for_request(
        request=second_request,
        status_code=200,
        reason="OK",
    )
    await registrar.send_response(ok, second.remote)
    return authorization


def test_sip_user_agent_unregisters_over_udp() -> None:
    asyncio.run(_unregister_over_udp())


async def _unregister_over_udp() -> None:
    client = SipUac(actor_id="client")
    registrar = SipUas(actor_id="registrar")
    try:
        await client.start()
        await registrar.start()
        registrar_task = asyncio.create_task(_unregister_responder(registrar))

        state = await client.unregister_account(
            remote=registrar.local_address,
            registrar=SipUri.parse("sip:example.com"),
            aor=SipUri.parse("sip:alice@example.com"),
            contact=SipUri.parse(f"sip:alice@127.0.0.1:{client.local_address[1]}"),
            call_id="unregister-call-1",
            branch="z9hG4bK-unregister",
            from_tag="from-tag",
            timeout=1.0,
        )
        expires = await registrar_task

        assert state == RegisterClientState.UNREGISTERED
        assert expires == "0"
    finally:
        await client.stop()
        await registrar.stop()


async def _unregister_responder(registrar: SipUas) -> str:
    event = await registrar.receive_event(timeout=1.0)
    request = event.message
    assert isinstance(request, SipRequest)
    assert request.method == "REGISTER"
    response = create_response_for_request(
        request=request,
        status_code=200,
        reason="OK",
    )
    await registrar.send_response(response, event.remote)
    return request.headers.get("Expires") or ""


def test_sip_user_agent_retransmits_register_until_response() -> None:
    asyncio.run(_retransmit_register_until_response())


async def _retransmit_register_until_response() -> None:
    client_timeline = EventRecorder(run_id="retransmit-client")
    client = SipUac(
        actor_id="client",
        timeline=client_timeline,
        retransmission_policy=SipRetransmissionPolicy(
            initial_interval=0.01,
            max_interval=0.01,
            max_attempts=2,
        ),
    )
    registrar = SipUas(actor_id="registrar")
    try:
        await client.start()
        await registrar.start()
        registrar_task = asyncio.create_task(_delayed_register_responder(registrar))

        state = await client.register_account(
            remote=registrar.local_address,
            registrar=SipUri.parse("sip:example.com"),
            aor=SipUri.parse("sip:alice@example.com"),
            contact=SipUri.parse(f"sip:alice@127.0.0.1:{client.local_address[1]}"),
            call_id="retransmit-register-1",
            branch="z9hG4bK-register-retransmit",
            from_tag="from-tag",
            timeout=1.0,
        )
        received_count = await registrar_task

        assert state == RegisterClientState.REGISTERED
        assert received_count == 2
        assert any(event.name == "retransmitted" for event in client_timeline.events)
    finally:
        await client.stop()
        await registrar.stop()


def test_sip_user_agent_event_hook_overrides_retransmission_intervals() -> None:
    asyncio.run(_event_hook_overrides_retransmission_intervals())


async def _event_hook_overrides_retransmission_intervals() -> None:
    defaults_seen: list[tuple[float, ...]] = []

    def fast_intervals(
        message: object, remote: tuple[str, int], intervals: list[float]
    ) -> None:
        defaults_seen.append(tuple(intervals))
        intervals.clear()
        intervals.append(0.01)

    client = SipUserAgent(
        mode="lab",
        actor_id="client",
        event_hooks={"retransmission": [fast_intervals]},
    )
    registrar = SipUas(actor_id="registrar")
    try:
        await client.start()
        await registrar.start()
        registrar_task = asyncio.create_task(_delayed_register_responder(registrar))

        state = await client.register_account(
            remote=registrar.local_address,
            registrar=SipUri.parse("sip:example.com"),
            aor=SipUri.parse("sip:alice@example.com"),
            contact=SipUri.parse(f"sip:alice@127.0.0.1:{client.local_address[1]}"),
            call_id="lab-timer-register-1",
            branch="z9hG4bK-lab-timer-register",
            from_tag="from-tag",
            timeout=1.0,
        )
        received_count = await registrar_task

        assert state == RegisterClientState.REGISTERED
        assert received_count == 2
        assert defaults_seen
    finally:
        await client.stop()
        await registrar.stop()


async def _delayed_register_responder(registrar: SipUas) -> int:
    first = await registrar.receive_event(timeout=1.0)
    first_request = first.message
    assert isinstance(first_request, SipRequest)
    second = await registrar.receive_event(timeout=1.0)
    second_request = second.message
    assert isinstance(second_request, SipRequest)
    response = create_response_for_request(
        request=second_request,
        status_code=200,
        reason="OK",
    )
    await registrar.send_response(response, second.remote)
    return 2
