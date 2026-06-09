# RFC 3261/RFC 8866 lab-mode example: add a SIP header and mark SDP body.

from __future__ import annotations

import asyncio

from sipx import SipCallError, SipHooks, SipMessage, SipRequest
from sipx.examples.common import (
    ExampleCallTimeout,
    ExampleConfigError,
    audio_mode,
    await_call,
    call_duration,
    call_summary,
    call_target,
    error_summary,
    mizu_uac,
    print_json,
    run,
)


async def manipulation() -> None:
    hooks = SipHooks()

    @hooks.before_send_message
    def add_lab_header(message: SipMessage, remote: tuple[str, int]) -> SipMessage:
        if isinstance(message, SipRequest):
            message.headers.add("X-SipX-Lab", "mizu-manipulation")
        return message

    @hooks.before_sdp_body
    def mark_sdp(message: SipMessage, body: bytes) -> bytes:
        if isinstance(message, SipRequest) and message.method == "INVITE":
            return body.replace(
                b"a=sendrecv\r\n", b"a=sendrecv\r\na=x-sipx-lab: mizu\r\n"
            )
        return body

    async with mizu_uac(mode="lab", lab_hooks=hooks) as uac:
        try:
            call = await await_call(uac.call(call_target(), audio=audio_mode()))
        except (ExampleCallTimeout, ExampleConfigError, SipCallError) as exc:
            print_json(error_summary(exc))
            return
        if call_duration() > 0:
            await asyncio.sleep(call_duration())
        print_json(call_summary(call))
        await uac.hangup(call)


def main() -> None:
    run(manipulation())


if __name__ == "__main__":
    main()
