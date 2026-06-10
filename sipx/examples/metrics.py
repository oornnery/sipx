import asyncio
import os

from sipx import SipCallError, SipUac
from sipx.examples.common import account_settings, print_json


async def metrics() -> None:
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
    audio = os.getenv("SIPX_AUDIO", "noise")
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
                uac.call(target_value, audio=audio),
                timeout=s["timeout"],
            )
        except (SipCallError, TimeoutError) as exc:
            print_json(
                {
                    "call": {
                        "state": "failed",
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                    },
                    "rtp": None,
                }
            )
            return
        session = uac.rtp_session(call)
        rtp_snapshot = session.snapshot() if session else None
        print_json(
            {
                "call": {
                    "call_id": call.call_id,
                    "state": call.state.value,
                },
                "rtp": rtp_snapshot,
            }
        )
        await uac.hangup(call)


def main() -> None:
    asyncio.run(metrics())


if __name__ == "__main__":
    main()
