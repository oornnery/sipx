from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sipx import SipHooks, SipMessage, SipRequest

from mizu_common import (
    add_call_args,
    add_common_args,
    audio_mode,
    call_summary,
    mizu_uac,
    print_json,
)


async def manipulation(
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
) -> None:
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

    async with mizu_uac(
        local_host=local_host,
        local_port=local_port,
        timeout=timeout,
        mode="lab",
        lab_hooks=hooks,
        rtp_bind_host=rtp_bind,
        rtp_advertise_host=rtp_advertise,
        jitter_buffer_ms=jitter_buffer_ms,
    ) as uac:
        call = await uac.call(target, audio=audio_mode(audio))
        if duration > 0:
            await asyncio.sleep(duration)
        print_json(call_summary(call))
        await uac.hangup(call)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Call Mizu with SIP header/SDP lab manipulation."
    )
    add_common_args(parser)
    add_call_args(parser)
    args = parser.parse_args(argv)
    asyncio.run(
        manipulation(
            target=args.target,
            local_host=args.local_host,
            local_port=args.local_port,
            timeout=args.timeout,
            duration=args.duration,
            audio=args.audio,
            rtp_bind=args.rtp_bind,
            rtp_advertise=args.rtp_advertise,
            jitter_buffer_ms=args.jitter_buffer_ms,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
