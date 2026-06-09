import asyncio

import pytest

from sipx import (
    NativeSipBackend,
    NativeSipCallError,
    NativeSipCallState,
    NativeSipLabHooks,
    NativeSoftphone,
    NativeSoftphoneAccount,
    NativeSoftphoneConfig,
    NativeSoftphoneError,
    RegisterClientState,
    SipRequest,
    SipUri,
    Timeline,
    create_audio_offer,
    create_response_for_request,
)


def test_native_softphone_requires_start_before_contact() -> None:
    softphone = NativeSoftphone(
        NativeSoftphoneConfig(
            account=NativeSoftphoneAccount(
                aor="sip:alice@example.com",
                registrar="sip:example.com",
            ),
            remote=("127.0.0.1", 5060),
        )
    )

    with pytest.raises(NativeSoftphoneError, match="started"):
        _ = softphone.contact


def test_native_softphone_config_passes_lab_hooks_to_backend() -> None:
    hooks = NativeSipLabHooks()
    softphone = NativeSoftphone(
        NativeSoftphoneConfig(
            account=NativeSoftphoneAccount(
                aor="sip:alice@example.com",
                registrar="sip:example.com",
            ),
            remote=("127.0.0.1", 5060),
            mode="lab",
            lab_hooks=hooks,
        )
    )

    assert softphone.backend.lab_hooks is hooks


def test_native_softphone_registers_and_unregisters_over_udp() -> None:
    asyncio.run(_register_and_unregister_over_udp())


async def _register_and_unregister_over_udp() -> None:
    registrar = NativeSipBackend(actor_id="registrar")
    timeline = Timeline(run_id="softphone-register")
    try:
        await registrar.start()
        softphone = NativeSoftphone(
            NativeSoftphoneConfig(
                account=NativeSoftphoneAccount(
                    aor="sip:alice@example.com",
                    registrar="sip:example.com",
                    contact_user="alice",
                ),
                remote=registrar.local_address,
                actor_id="alice",
                timeout=1.0,
            ),
            timeline=timeline,
        )
        await softphone.start()
        try:
            responder = asyncio.create_task(_register_unregister_responder(registrar))

            registered = await softphone.register(call_id="softphone-register-1")
            unregistered = await softphone.unregister(call_id="softphone-unregister-1")
            contacts = await responder

            assert registered is RegisterClientState.REGISTERED
            assert unregistered is RegisterClientState.UNREGISTERED
            assert contacts == [
                f"<sip:alice@127.0.0.1:{softphone.local_address[1]}>",
                f"<sip:alice@127.0.0.1:{softphone.local_address[1]}>",
            ]
        finally:
            await softphone.stop()
    finally:
        await registrar.stop()

    names = [(event.category, event.name) for event in timeline.events]
    assert ("softphone", "started") in names
    assert ("softphone", "registered") in names
    assert ("softphone", "unregistered") in names
    assert ("softphone", "stopped") in names


async def _register_unregister_responder(registrar: NativeSipBackend) -> list[str]:
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


def test_native_softphone_runs_outbound_call_and_hangup() -> None:
    asyncio.run(_run_outbound_call_and_hangup())


def test_v38_native_softphone_retries_bye_with_digest_auth() -> None:
    asyncio.run(_retry_bye_with_digest_auth())


async def _run_outbound_call_and_hangup() -> None:
    callee = NativeSipBackend(actor_id="callee")
    try:
        await callee.start()
        softphone = NativeSoftphone(
            NativeSoftphoneConfig(
                account=NativeSoftphoneAccount(
                    aor="sip:alice@example.com",
                    registrar="sip:example.com",
                ),
                remote=callee.local_address,
                actor_id="alice",
                timeout=1.0,
            )
        )
        await softphone.start()
        try:
            callee_contact = SipUri.parse(
                f"sip:bob@127.0.0.1:{callee.local_address[1]}"
            )
            accept_task = asyncio.create_task(
                callee.accept_call(
                    local_tag="callee-tag",
                    contact=callee_contact,
                    timeout=1.0,
                )
            )
            call = await softphone.call(
                "sip:bob@example.com",
                call_id="softphone-call-1",
            )
            callee_call = await accept_task

            assert call.state is NativeSipCallState.CONFIRMED
            assert callee_call.state is NativeSipCallState.CONFIRMED
            assert call.local_sdp is not None
            assert call.remote_sdp is not None
            assert call.local_sdp.has_codec("PCMU")
            assert call.remote_sdp.has_codec("PCMU")
            assert callee_call.local_sdp is not None
            assert callee_call.remote_sdp is not None

            dtmf_task = asyncio.create_task(_answer_info_dtmf(callee, count=2))
            await softphone.send_dtmf(call, "1#", duration_ms=200)
            assert await dtmf_task == ["1", "#"]

            answer_bye = asyncio.create_task(
                callee.answer_bye(callee_call, timeout=1.0)
            )
            await softphone.hangup(call)
            await answer_bye

            assert call.state is NativeSipCallState.TERMINATED
            assert callee_call.state is NativeSipCallState.TERMINATED
        finally:
            await softphone.stop()
    finally:
        await callee.stop()


async def _retry_bye_with_digest_auth() -> None:
    callee = NativeSipBackend(actor_id="callee")
    try:
        await callee.start()
        softphone = NativeSoftphone(
            NativeSoftphoneConfig(
                account=NativeSoftphoneAccount(
                    aor="sip:alice@example.com",
                    registrar="sip:example.com",
                    username="alice",
                    password="secret-password",
                ),
                remote=callee.local_address,
                actor_id="alice",
                timeout=1.0,
            )
        )
        await softphone.start()
        try:
            callee_contact = SipUri.parse(
                f"sip:bob@127.0.0.1:{callee.local_address[1]}"
            )
            accept_task = asyncio.create_task(
                callee.accept_call(
                    local_tag="callee-tag",
                    contact=callee_contact,
                    timeout=1.0,
                )
            )
            call = await softphone.call(
                "sip:bob@example.com",
                call_id="softphone-bye-auth-1",
            )
            callee_call = await accept_task

            answer_bye = asyncio.create_task(_challenge_bye_digest(callee))
            await softphone.hangup(call)
            authorization = await answer_bye

            assert call.state is NativeSipCallState.TERMINATED
            assert callee_call.state is NativeSipCallState.CONFIRMED
            assert 'username="alice"' in authorization
            assert 'nonce="bye-nonce"' in authorization
            assert "secret-password" not in authorization
        finally:
            await softphone.stop()
    finally:
        await callee.stop()


async def _challenge_bye_digest(callee: NativeSipBackend) -> str:
    first = await callee.receive_event(timeout=1.0)
    first_request = first.message
    assert isinstance(first_request, SipRequest)
    assert first_request.method == "BYE"
    first_cseq = int((first_request.headers.get("CSeq") or "0").split()[0])
    challenge = create_response_for_request(
        request=first_request,
        status_code=401,
        reason="Unauthorized",
    )
    challenge.headers.add(
        "WWW-Authenticate",
        'Digest realm="example.com", nonce="bye-nonce", qop="auth"',
    )
    await callee.send_response(challenge, first.remote)

    second = await callee.receive_event(timeout=1.0)
    second_request = second.message
    assert isinstance(second_request, SipRequest)
    assert second_request.method == "BYE"
    assert int((second_request.headers.get("CSeq") or "0").split()[0]) == first_cseq + 1
    authorization = second_request.headers.get("Authorization") or ""
    response = create_response_for_request(
        request=second_request,
        status_code=200,
        reason="OK",
    )
    await callee.send_response(response, second.remote)
    return authorization


async def _answer_info_dtmf(callee: NativeSipBackend, *, count: int) -> list[str]:
    digits: list[str] = []
    for _ in range(count):
        event = await callee.receive_event(timeout=1.0)
        request = event.message
        assert isinstance(request, SipRequest)
        assert request.method == "INFO"
        assert request.headers.get("Content-Type") == "application/dtmf-relay"
        lines = request.body.decode("ascii").splitlines()
        signal = lines[0].removeprefix("Signal=")
        digits.append(signal)
        assert lines[1] == "Duration=200"
        response = create_response_for_request(
            request=request,
            status_code=200,
            reason="OK",
        )
        await callee.send_response(response, event.remote)
    return digits


def test_native_softphone_answers_inbound_call() -> None:
    asyncio.run(_answer_inbound_call())


async def _answer_inbound_call() -> None:
    caller = NativeSipBackend(actor_id="caller")
    try:
        await caller.start()
        softphone = NativeSoftphone(
            NativeSoftphoneConfig(
                account=NativeSoftphoneAccount(
                    aor="sip:bob@example.com",
                    registrar="sip:example.com",
                ),
                remote=caller.local_address,
                actor_id="bob",
                timeout=1.0,
            )
        )
        await softphone.start()
        try:
            answer_task = asyncio.create_task(
                softphone.answer_inbound(local_tag="bob-tag")
            )
            caller_call = await caller.initiate_call(
                remote=softphone.local_address,
                target=SipUri.parse("sip:bob@example.com"),
                caller=SipUri.parse("sip:alice@example.com"),
                contact=SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}"),
                call_id="softphone-inbound-1",
                branch="z9hG4bK-softphone-inbound",
                from_tag="alice-tag",
                ack_branch="z9hG4bK-softphone-inbound-ack",
                timeout=1.0,
            )
            softphone_call = await answer_task

            assert caller_call.state is NativeSipCallState.CONFIRMED
            assert softphone_call.state is NativeSipCallState.CONFIRMED
            assert softphone_call.dialog.dialog_id.local_tag == "bob-tag"
        finally:
            await softphone.stop()
    finally:
        await caller.stop()


def test_native_softphone_rejects_missing_sdp_answer() -> None:
    asyncio.run(_reject_missing_sdp_answer())


async def _reject_missing_sdp_answer() -> None:
    caller = NativeSipBackend(actor_id="caller")
    peer = NativeSipBackend(actor_id="peer")
    try:
        await caller.start()
        await peer.start()
        responder = asyncio.create_task(_ok_without_sdp(peer))
        offer = create_audio_offer(
            connection_address="127.0.0.1",
            port=40000,
        )

        with pytest.raises(NativeSipCallError, match="missing SDP answer"):
            await caller.initiate_call(
                remote=peer.local_address,
                target=SipUri.parse("sip:bob@example.com"),
                caller=SipUri.parse("sip:alice@example.com"),
                contact=SipUri.parse(f"sip:alice@127.0.0.1:{caller.local_address[1]}"),
                call_id="missing-sdp-answer-1",
                branch="z9hG4bK-missing-sdp-answer",
                from_tag="caller-tag",
                ack_branch="z9hG4bK-missing-sdp-answer-ack",
                timeout=1.0,
                body=offer.to_sdp().encode("utf-8"),
                content_type="application/sdp",
            )
        await responder
    finally:
        await caller.stop()
        await peer.stop()


async def _ok_without_sdp(peer: NativeSipBackend) -> None:
    event = await peer.receive_event(timeout=1.0)
    request = event.message
    assert isinstance(request, SipRequest)
    assert request.method == "INVITE"
    response = create_response_for_request(
        request=request,
        status_code=200,
        reason="OK",
        to_tag="peer-tag",
        contact=SipUri.parse("sip:bob@127.0.0.1:5060"),
    )
    await peer.send_response(response, event.remote)
