# RFC 3261 INVITE without SDP; useful to observe proxy/PSTN behavior.
# Valid SIP flow may be INVITE -> final response -> ACK with no 180/183.

from __future__ import annotations

import asyncio

from sipx import SipCallError, SipUri, SipUserAgent
from sipx.examples.common import (
    ExampleCallTimeout,
    ExampleConfigError,
    account_settings,
    await_call,
    branch,
    call_duration,
    call_summary,
    call_target,
    contact_uri,
    error_summary,
    local_host,
    local_port,
    new_id,
    print_json,
    remote_address,
    run,
    tag,
    timeout,
)


async def invite_without_sdp() -> None:
    settings = account_settings()
    aor = SipUri.parse(settings["aor"])
    try:
        request_target = SipUri.parse(call_target())
    except ExampleConfigError as exc:
        print_json(error_summary(exc))
        return
    async with SipUserAgent(local_host=local_host(), local_port=local_port()) as ua:
        try:
            call = await await_call(
                ua.initiate_call(
                    remote=remote_address(),
                    target=request_target,
                    caller=aor,
                    contact=contact_uri(aor, ua.local_address),
                    call_id=new_id("invite-no-sdp"),
                    branch=branch("invite"),
                    from_tag=tag("from"),
                    ack_branch=branch("ack"),
                    timeout=timeout(),
                    username=settings["username"],
                    password=settings["credential"],
                    auth_branch=branch("invite-auth"),
                )
            )
        except (ExampleCallTimeout, SipCallError) as exc:
            print_json(error_summary(exc))
            return
        if call_duration() > 0:
            await asyncio.sleep(call_duration())
        print_json(call_summary(call))
        await ua.hangup_call(
            call,
            branch=branch("bye"),
            timeout=timeout(),
            username=settings["username"],
            password=settings["credential"],
            auth_branch=branch("bye-auth"),
        )


def main() -> None:
    run(invite_without_sdp())


if __name__ == "__main__":
    main()
