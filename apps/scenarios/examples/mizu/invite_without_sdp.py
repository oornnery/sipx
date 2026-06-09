from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sipx import SipUri, SipUserAgent

from mizu_common import (
    account_settings,
    add_call_args,
    add_common_args,
    branch,
    call_summary,
    contact_uri,
    new_id,
    print_json,
    remote_address,
    tag,
)


async def invite_without_sdp(
    *,
    target: str,
    local_host: str,
    local_port: int,
    timeout: float,
    duration: float,
) -> None:
    settings = account_settings()
    aor = SipUri.parse(settings["aor"])
    async with SipUserAgent(local_host=local_host, local_port=local_port) as user_agent:
        call = await user_agent.initiate_call(
            remote=remote_address(),
            target=SipUri.parse(target),
            caller=aor,
            contact=contact_uri(aor, user_agent.local_address),
            call_id=new_id("invite-no-sdp"),
            branch=branch("invite"),
            from_tag=tag("from"),
            ack_branch=branch("ack"),
            timeout=timeout,
            username=settings["username"],
            password=settings["credential"],
            auth_branch=branch("invite-auth"),
        )
        if duration > 0:
            await asyncio.sleep(duration)
        print_json(call_summary(call))
        await user_agent.hangup_call(
            call,
            branch=branch("bye"),
            timeout=timeout,
            username=settings["username"],
            password=settings["credential"],
            auth_branch=branch("bye-auth"),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send INVITE without SDP to Mizu.")
    add_common_args(parser)
    add_call_args(parser)
    args = parser.parse_args(argv)
    asyncio.run(
        invite_without_sdp(
            target=args.target,
            local_host=args.local_host,
            local_port=args.local_port,
            timeout=args.timeout,
            duration=args.duration,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
