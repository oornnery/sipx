# RFC 3261 INVITE with RFC 3264/RFC 8866 audio offer and optional RTP audio.

from __future__ import annotations

import asyncio

from sipx import SipCallError
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


async def invite_with_sdp() -> None:
    async with mizu_uac() as uac:
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
    run(invite_with_sdp())


if __name__ == "__main__":
    main()
