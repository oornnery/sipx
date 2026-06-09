# RFC 3261 REGISTER flow for the public Mizu demo account.

from __future__ import annotations

from sipx.examples.common import mizu_uac, print_json, run


async def register() -> None:
    async with mizu_uac() as uac:
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
    run(register())


if __name__ == "__main__":
    main()
