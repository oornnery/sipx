import asyncio
import os

from sipx import SipCallError, SipRequest, SipUac
from sipx.examples.common import account_settings, print_json


async def manipulation() -> None:
    s = account_settings()
    target_value = os.getenv("SIPX_TARGET") or s["aor"]

    def add_lab_header(request: SipRequest, remote: tuple[str, int]) -> None:
        request.headers.add("X-SipX-Lab", "manipulation")

    def mark_sdp(message: object, body: bytes) -> None:
        if isinstance(message, SipRequest) and message.method == "INVITE":
            message.body = body.replace(
                b"a=sendrecv\r\n", b"a=sendrecv\r\na=x-sipx-lab: yes\r\n"
            )

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
        mode="lab",
        event_hooks={
            "request": [add_lab_header],
            "sdp": [mark_sdp],
        },
    ) as uac:
        try:
            call = await asyncio.wait_for(
                uac.call(target_value, audio="none"),
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
        await uac.hangup(call)


def main() -> None:
    asyncio.run(manipulation())


if __name__ == "__main__":
    main()
