import asyncio
import os

from sipx import SipCallError, SipUri, SipUserAgent
from sipx.examples.common import account_settings, print_json


async def invite_without_sdp() -> None:
    s = account_settings()
    target_value = os.getenv("SIPX_TARGET")
    if not target_value:
        print_json(
            {
                "state": "failed",
                "error": {
                    "type": "ExampleConfigError",
                    "message": "SIPX_TARGET must be set for call examples",
                },
            }
        )
        return
    aor = SipUri.parse(s["aor"])
    target = SipUri.parse(target_value)
    async with SipUserAgent(
        local_host=s["local_host"],
        local_port=s["local_port"],
    ) as ua:
        try:
            call = await asyncio.wait_for(
                ua.initiate_call(
                    remote=(s["remote_host"], s["remote_port"]),
                    target=target,
                    caller=aor,
                    contact=SipUri(
                        scheme="sip",
                        user=s["contact_user"] or aor.user or "sipx",
                        host=ua.local_address[0],
                        port=ua.local_address[1],
                    ),
                    call_id=f"invite-no-sdp-{id(ua):x}",
                    branch=f"z9hG4bK-invite-{id(ua):x}",
                    from_tag=f"from-{id(ua):x}",
                    ack_branch=f"z9hG4bK-ack-{id(ua):x}",
                    timeout=s["timeout"],
                    username=s["username"],
                    password=s["credential"],
                    auth_branch=f"z9hG4bK-invite-auth-{id(ua):x}",
                ),
                timeout=s["timeout"],
            )
        except (SipCallError, TimeoutError) as exc:
            print_json(
                {
                    "state": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            )
            return
        print_json(
            {
                "call_id": call.call_id,
                "state": call.state.value,
            }
        )
        await ua.hangup_call(
            call,
            branch=f"z9hG4bK-bye-{id(ua):x}",
            timeout=s["timeout"],
            username=s["username"],
            password=s["credential"],
            auth_branch=f"z9hG4bK-bye-auth-{id(ua):x}",
        )


def main() -> None:
    asyncio.run(invite_without_sdp())


if __name__ == "__main__":
    main()
