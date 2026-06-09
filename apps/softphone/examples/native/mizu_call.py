from __future__ import annotations

import argparse
import asyncio

from sipx_softphone import (
    NativeSoftphone,
    NativeSoftphoneAccount,
    NativeSoftphoneConfig,
)


def mizu_demo_config(*, local_host: str, local_port: int = 0) -> NativeSoftphoneConfig:
    return NativeSoftphoneConfig(
        account=NativeSoftphoneAccount(
            aor="sip:1111@demo.mizu-voip.com:37075",
            registrar="sip:demo.mizu-voip.com:37075",
            username="1111",
            password="1111xxx",
            contact_user="1111",
        ),
        remote=("demo.mizu-voip.com", 37075),
        local_host=local_host,
        local_port=local_port,
        codecs=("PCMU", "PCMA"),
        timeout=10.0,
    )


async def register_mizu_demo(*, local_host: str) -> str:
    async with NativeSoftphone(mizu_demo_config(local_host=local_host)) as phone:
        state = await phone.register()
        return state.value


async def call_mizu_demo(
    target: str,
    *,
    local_host: str,
    digits: str | None = None,
) -> str:
    async with NativeSoftphone(mizu_demo_config(local_host=local_host)) as phone:
        call = await phone.call(target)
        if digits:
            await phone.send_dtmf(call, digits)
        await phone.hangup(call)
        return call.call_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run public Mizu demo SIP flows.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    register_parser = subcommands.add_parser("register")
    register_parser.add_argument("--local-host", required=True)

    call_parser = subcommands.add_parser("call")
    call_parser.add_argument("target")
    call_parser.add_argument("--local-host", required=True)
    call_parser.add_argument("--digits")

    args = parser.parse_args(argv)
    if args.command == "register":
        state = asyncio.run(register_mizu_demo(local_host=args.local_host))
        print(f"registered: {state}")
        return 0

    call_id = asyncio.run(
        call_mizu_demo(
            args.target,
            local_host=args.local_host,
            digits=args.digits,
        )
    )
    print(f"call completed: {call_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
