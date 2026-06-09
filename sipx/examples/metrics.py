# RFC 3550/3551 RTP metrics snapshot for a Mizu INVITE with SDP.

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
    rtp_summary,
    run,
)


async def metrics() -> None:
    async with mizu_uac() as uac:
        try:
            call = await await_call(uac.call(call_target(), audio=audio_mode("noise")))
        except (ExampleCallTimeout, ExampleConfigError, SipCallError) as exc:
            print_json({"call": error_summary(exc), "rtp": None})
            return
        if call_duration() > 0:
            await asyncio.sleep(call_duration())
        print_json({"call": call_summary(call), "rtp": rtp_summary(uac, call)})
        await uac.hangup(call)


def main() -> None:
    run(metrics())


if __name__ == "__main__":
    main()
