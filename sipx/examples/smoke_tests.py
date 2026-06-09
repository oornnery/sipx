# Public Mizu smoke checks: REGISTER + OPTIONS, and optional INVITE via env.

from __future__ import annotations

import asyncio
import os

from sipx import SipCallError, SipUdpError
from sipx.examples.common import (
    ExampleCallTimeout,
    ExampleConfigError,
    audio_mode,
    await_call,
    call_duration,
    call_target,
    error_summary,
    mizu_uac,
    print_json,
    response_summary,
    run,
    send_stateless_request,
)


async def smoke_tests() -> None:
    results: dict[str, object] = {}
    async with mizu_uac() as uac:
        results["register"] = (await uac.register()).value
    try:
        results["options"] = response_summary(await send_stateless_request("OPTIONS"))
    except (SipUdpError, TimeoutError) as exc:
        results["options"] = error_summary(exc)
    if os.getenv("SIPX_RUN_CALL", "0") == "1":
        async with mizu_uac() as uac:
            try:
                call = await await_call(uac.call(call_target(), audio=audio_mode()))
            except (ExampleCallTimeout, ExampleConfigError, SipCallError) as exc:
                results["call"] = error_summary(exc)
                print_json(results)
                return
            if call_duration() > 0:
                await asyncio.sleep(call_duration())
            results["call"] = {"call_id": call.call_id, "state": call.state.value}
            await uac.hangup(call)
    print_json(results)


def main() -> None:
    run(smoke_tests())


if __name__ == "__main__":
    main()
