import asyncio

from sipx import SipRequest, SipResponse, SipUac
from sipx.examples.common import account_settings, print_json


async def handlers() -> None:
    s = account_settings()
    seen: list[dict[str, object]] = []

    def log_request(request: SipRequest, remote: tuple[str, int]) -> None:
        seen.append({"request": request.method, "remote": f"{remote[0]}:{remote[1]}"})

    def log_response(response: SipResponse, remote: tuple[str, int]) -> None:
        seen.append(
            {"response": response.status_code, "remote": f"{remote[0]}:{remote[1]}"}
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
        event_hooks={
            "request": [log_request],
            "response": [log_response],
        },
    ) as uac:
        await uac.register()

    print_json(seen)


def main() -> None:
    asyncio.run(handlers())


if __name__ == "__main__":
    main()
