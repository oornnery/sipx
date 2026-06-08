import asyncio

import pytest

from sipx import (
    NativeSipBackend,
    NativeSipCallState,
    NativeSoftphone,
    NativeSoftphoneAccount,
    NativeSoftphoneConfig,
    NativeSoftphoneError,
    RegisterClientState,
    SipRequest,
    SipUri,
    Timeline,
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
