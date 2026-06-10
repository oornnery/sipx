import asyncio

from sipx import SipCallError, SipUac, SipUdpError, SipUserAgent, SipUri
from sipx.examples.common import account_settings, debug_wire, print_json


async def smoke_tests() -> None:
    s = account_settings()
    results: dict[str, object] = {}

    async with SipUac(
        aor=s["aor"],
        registrar=s["registrar"],
        remote=(s["remote_host"], s["remote_port"]),
        username=s["username"],
        password=s["credential"],
        contact_user=s["contact_user"],
        local_host=s["local_host"],
        local_port=s["local_port"],
        timeout=s["timeout"],
        event_hooks={"wire": [debug_wire]},
    ) as uac:
        state = await uac.register()
        results["register"] = state.value

    aor = SipUri.parse(s["aor"])
    try:
        async with SipUserAgent(
            local_host=s["local_host"],
            local_port=s["local_port"],
            event_hooks={"wire": [debug_wire]},
        ) as ua:
            response = await ua.request(
                "OPTIONS",
                aor,
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
            results["options"] = {
                "status_code": response.status_code,
                "reason": response.reason,
            }
    except (SipUdpError, TimeoutError) as exc:
        results["options"] = {
            "state": "failed",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }

    if s["run_call"] == "1":
        async with SipUac(
            aor=s["aor"],
            registrar=s["registrar"],
            remote=(s["remote_host"], s["remote_port"]),
            username=s["username"],
            password=s["credential"],
            contact_user=s["contact_user"],
            local_host=s["local_host"],
            local_port=s["local_port"],
            timeout=s["timeout"],
            event_hooks={"wire": [debug_wire]},
        ) as uac:
            try:
                call = await asyncio.wait_for(
                    uac.call(s["target"], audio="none"),
                    timeout=s["timeout"],
                )
            except (SipCallError, TimeoutError) as exc:
                results["call"] = {
                    "state": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
                print_json(results)
                return
            results["call"] = {"call_id": call.call_id, "state": call.state.value}
            await uac.hangup(call)

    print_json(results)


def main() -> None:
    asyncio.run(smoke_tests())


if __name__ == "__main__":
    main()
