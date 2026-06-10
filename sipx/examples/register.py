import asyncio

from sipx import SipUac
from sipx.examples.common import account_settings, print_json


async def register() -> None:
    s = account_settings()
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
        print_json(
            {
                "state": state.value,
                "contact": str(uac.contact),
                "local_address": {
                    "host": uac.local_address[0],
                    "port": uac.local_address[1],
                },
            }
        )


def main() -> None:
    asyncio.run(register())


if __name__ == "__main__":
    main()
