import asyncio
import os

from sipx import SipCallError, SipUac, SipUdpError, SipUserAgent, SipUri
from sipx.examples.common import account_settings, print_json


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
    ) as uac:
        state = await uac.register()
        results["register"] = state.value

    aor = SipUri.parse(s["aor"])
    try:
        async with SipUserAgent(
            local_host=s["local_host"],
            local_port=s["local_port"],
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

    if os.getenv("SIPX_RUN_CALL", "0") == "1":
        target_value = os.getenv("SIPX_TARGET")
        if not target_value:
            results["call"] = {
                "state": "failed",
                "error": {
                    "type": "ExampleConfigError",
                    "message": "SIPX_TARGET must be set for call examples",
                },
            }
            print_json(results)
            return
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
        ) as uac:
            try:
                call = await asyncio.wait_for(
                    uac.call(target_value, audio="none"),
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
