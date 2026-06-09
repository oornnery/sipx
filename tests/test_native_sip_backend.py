import asyncio

import pytest

from sipx import (
    HeaderMap,
    NativeSipBackend,
    NativeSipCallState,
    NativeSipLabHooks,
    NativeSipRetransmissionPolicy,
    RegisterClientState,
    SipRequest,
    SipResponse,
    SipUdpError,
    SipUri,
    Timeline,
    create_invite_request,
    create_register_request,
    create_response_for_request,
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


def test_native_sip_backend_rejects_lab_hooks_in_strict_mode() -> None:
    with pytest.raises(ValueError, match="lab_hooks require lab mode"):
        NativeSipBackend(lab_hooks=NativeSipLabHooks())


def test_native_sip_backend_lab_hook_mutates_outbound_headers() -> None:
    asyncio.run(_lab_hook_mutates_outbound_headers())


async def _lab_hook_mutates_outbound_headers() -> None:
    def add_lab_header(message, remote):
        message.headers.add("X-Sipx-Lab", "header-hook")
        return message

    sender = NativeSipBackend(
        mode="lab",
        lab_hooks=NativeSipLabHooks(before_send_message=add_lab_header),
    )
    receiver = NativeSipBackend()
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


def test_native_sip_backend_lab_hook_mutates_sdp_body() -> None:
    asyncio.run(_lab_hook_mutates_sdp_body())


async def _lab_hook_mutates_sdp_body() -> None:
    def add_sdp_attribute(message, body: bytes) -> bytes:
        return body + b"a=sipx-lab:yes\r\n"

    sender = NativeSipBackend(
        mode="lab",
        lab_hooks=NativeSipLabHooks(before_sdp_body=add_sdp_attribute),
    )
    receiver = NativeSipBackend()
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


def test_native_sip_backend_lab_hook_can_send_malformed_bytes() -> None:
    asyncio.run(_lab_hook_can_send_malformed_bytes())


async def _lab_hook_can_send_malformed_bytes() -> None:
    def send_malformed(message, remote):
        return b"OPTIONS sip:bob@example.com SIP/2.0\r\nContent-Length: 10\r\n\r\nx"

    sender = NativeSipBackend(
        mode="lab",
        lab_hooks=NativeSipLabHooks(before_send_message=send_malformed),
    )
    receiver = NativeSipBackend()
    try:
        await sender.start()
        await receiver.start()

        await sender.send_request(register_request(), receiver.local_address)
        event = await receiver.receive_event(timeout=1.0)

        assert event.is_error
        assert event.message is None
        assert "body length" in (event.error or "")
    finally:
        await sender.stop()
        await receiver.stop()


def test_native_sip_backend_lab_hook_observes_received_events() -> None:
    asyncio.run(_lab_hook_observes_received_events())


async def _lab_hook_observes_received_events() -> None:
    seen: list[tuple[str, int, str]] = []

    def observe(event):
        method = event.message.method if isinstance(event.message, SipRequest) else ""
        seen.append((event.remote[0], event.remote[1], method))
        return event

    timeline = Timeline(run_id="receive-hook")
    sender = NativeSipBackend()
    receiver = NativeSipBackend(
        mode="lab",
        timeline=timeline,
        lab_hooks=NativeSipLabHooks(after_receive_event=observe),
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


def test_native_sip_backend_lab_hook_can_drop_received_events() -> None:
    asyncio.run(_lab_hook_can_drop_received_events())


async def _lab_hook_can_drop_received_events() -> None:
    dropped: list[str] = []

    def drop(event):
        method = event.message.method if isinstance(event.message, SipRequest) else ""
        dropped.append(method)
        return None

    sender = NativeSipBackend()
    receiver = NativeSipBackend(
        mode="lab",
        lab_hooks=NativeSipLabHooks(after_receive_event=drop),
    )
    try:
        await sender.start()
        await receiver.start()

        await sender.send_request(register_request(), receiver.local_address)
        with pytest.raises(SipUdpError, match="timed out"):
            await receiver.receive_event(timeout=0.2)

        assert dropped == ["REGISTER"]
    finally:
        await sender.stop()
        await receiver.stop()


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


def test_native_sip_backend_retries_invite_with_digest_auth() -> None:
    asyncio.run(_invite_with_digest_auth())


async def _invite_with_digest_auth() -> None:
    caller_timeline = Timeline(run_id="digest-caller")
    caller = NativeSipBackend(timeline=caller_timeline, actor_id="caller")
    proxy = NativeSipBackend(actor_id="proxy")
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

        assert call.state == NativeSipCallState.CONFIRMED
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


async def _digest_invite_responder(proxy: NativeSipBackend) -> str:
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


def test_native_sip_backend_registers_with_digest_over_udp() -> None:
    asyncio.run(_register_with_digest())


async def _register_with_digest() -> None:
    client = NativeSipBackend(actor_id="client")
    registrar = NativeSipBackend(actor_id="registrar")
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


async def _digest_register_responder(registrar: NativeSipBackend) -> str:
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


def test_native_sip_backend_unregisters_over_udp() -> None:
    asyncio.run(_unregister_over_udp())


async def _unregister_over_udp() -> None:
    client = NativeSipBackend(actor_id="client")
    registrar = NativeSipBackend(actor_id="registrar")
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


async def _unregister_responder(registrar: NativeSipBackend) -> str:
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


def test_native_sip_backend_retransmits_register_until_response() -> None:
    asyncio.run(_retransmit_register_until_response())


async def _retransmit_register_until_response() -> None:
    client_timeline = Timeline(run_id="retransmit-client")
    client = NativeSipBackend(
        actor_id="client",
        timeline=client_timeline,
        retransmission_policy=NativeSipRetransmissionPolicy(
            initial_interval=0.01,
            max_interval=0.01,
            max_attempts=2,
        ),
    )
    registrar = NativeSipBackend(actor_id="registrar")
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


def test_native_sip_backend_lab_hook_overrides_retransmission_intervals() -> None:
    asyncio.run(_lab_hook_overrides_retransmission_intervals())


async def _lab_hook_overrides_retransmission_intervals() -> None:
    defaults_seen: list[tuple[float, ...]] = []

    def fast_intervals(message, remote, default_intervals):
        defaults_seen.append(default_intervals)
        return (0.01,)

    client = NativeSipBackend(
        mode="lab",
        actor_id="client",
        lab_hooks=NativeSipLabHooks(retransmission_intervals=fast_intervals),
    )
    registrar = NativeSipBackend(actor_id="registrar")
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


async def _delayed_register_responder(registrar: NativeSipBackend) -> int:
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
