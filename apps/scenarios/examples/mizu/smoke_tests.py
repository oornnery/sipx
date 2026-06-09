from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mizu_common import (
    add_call_args,
    add_common_args,
    audio_mode,
    mizu_uac,
    print_json,
    response_summary,
    send_stateless_request,
)


async def smoke_tests(
    *,
    target: str,
    local_host: str,
    local_port: int,
    timeout: float,
    duration: float,
    audio: str,
    rtp_bind: str | None,
    rtp_advertise: str | None,
    jitter_buffer_ms: int,
    skip_call: bool,
) -> None:
    results: dict[str, object] = {}
    async with mizu_uac(
        local_host=local_host, local_port=local_port, timeout=timeout
    ) as uac:
        results["register"] = (await uac.register()).value
    options_response = await send_stateless_request(
        method="OPTIONS",
        target=target,
        local_host=local_host,
        local_port=local_port,
        timeout=timeout,
    )
    results["options"] = response_summary(options_response)
    if not skip_call:
        async with mizu_uac(
            local_host=local_host,
            local_port=local_port,
            timeout=timeout,
            rtp_bind_host=rtp_bind,
            rtp_advertise_host=rtp_advertise,
            jitter_buffer_ms=jitter_buffer_ms,
        ) as uac:
            call = await uac.call(target, audio=audio_mode(audio))
            if duration > 0:
                await asyncio.sleep(duration)
            results["call"] = {"call_id": call.call_id, "state": call.state.value}
            await uac.hangup(call)
    print_json(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a small pure-Python Mizu smoke test suite."
    )
    add_common_args(parser)
    add_call_args(parser)
    parser.add_argument("--skip-call", action="store_true")
    args = parser.parse_args(argv)
    asyncio.run(
        smoke_tests(
            target=args.target,
            local_host=args.local_host,
            local_port=args.local_port,
            timeout=args.timeout,
            duration=args.duration,
            audio=args.audio,
            rtp_bind=args.rtp_bind,
            rtp_advertise=args.rtp_advertise,
            jitter_buffer_ms=args.jitter_buffer_ms,
            skip_call=args.skip_call,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
