import asyncio

from sipx import SipUdpError, SipUserAgent, SipUri
from sipx.examples.common import account_settings, debug_wire, print_json


async def options() -> None:
    s = account_settings()
    aor = SipUri.parse(s["aor"])
    target = SipUri.parse(s["aor"])
    try:
        async with SipUserAgent(
            local_host=s["local_host"],
            local_port=s["local_port"],
            event_hooks={"wire": [debug_wire]},
        ) as ua:
            response = await ua.request(
                "OPTIONS",
                target,
                remote=(s["remote_host"], s["remote_port"]),
                caller=aor,
                contact=SipUri(
                    scheme="sip",
                    user=s["contact_user"] or aor.user or "sipx",
                    host=ua.local_address[0],
                    port=ua.local_address[1],
                ),
                timeout=s["timeout"],
                username=s["username"],
                password=s["credential"],
            )
    except (SipUdpError, TimeoutError) as exc:
        print_json(
            {
                "state": "failed",
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        return
    print_json(
        {
            "status_code": response.status_code,
            "reason": response.reason,
            "headers": dict(response.headers.items()),
        }
    )


def main() -> None:
    asyncio.run(options())


if __name__ == "__main__":
    main()
