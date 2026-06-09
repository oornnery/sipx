from __future__ import annotations

import argparse
import asyncio
import os

from sipx_softphone import (
    NativeSoftphone,
    NativeSoftphoneAccount,
    NativeSoftphoneConfig,
)


def config_from_env() -> NativeSoftphoneConfig:
    aor = _required_env("SIPX_AOR")
    registrar = _required_env("SIPX_REGISTRAR")
    remote_host = (
        os.getenv("SIPX_REMOTE_HOST") or registrar.removeprefix("sip:").split(":", 1)[0]
    )
    remote_port = int(os.getenv("SIPX_REMOTE_PORT", "5060"))
    return NativeSoftphoneConfig(
        account=NativeSoftphoneAccount(
            aor=aor,
            registrar=registrar,
            username=os.getenv("SIPX_USERNAME"),
            password=os.getenv("SIPX_PASSWORD"),
            contact_user=os.getenv("SIPX_CONTACT_USER"),
        ),
        remote=(remote_host, remote_port),
        local_host=os.getenv("SIPX_LOCAL_HOST", "127.0.0.1"),
        local_port=int(os.getenv("SIPX_LOCAL_PORT", "0")),
        media_host=os.getenv("SIPX_MEDIA_HOST"),
        media_port=int(os.getenv("SIPX_MEDIA_PORT", "0")),
        codecs=tuple(os.getenv("SIPX_CODECS", "PCMU,PCMA").split(",")),
        timeout=float(os.getenv("SIPX_TIMEOUT", "5")),
    )


async def call_with_dtmf(target: str, *, digits: str = "123#") -> str:
    async with NativeSoftphone(config_from_env()) as phone:
        call = await phone.call(target)
        await phone.send_dtmf(call, digits)
        await phone.hangup(call)
        return call.call_id


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Place a native SIP call and send SIP INFO DTMF."
    )
    parser.add_argument(
        "target", help="Target SIP URI, for example sip:ivr@example.com"
    )
    parser.add_argument("--digits", default="123#", help="DTMF digits to send")
    args = parser.parse_args(argv)

    call_id = asyncio.run(call_with_dtmf(args.target, digits=args.digits))
    print(f"call completed: {call_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
