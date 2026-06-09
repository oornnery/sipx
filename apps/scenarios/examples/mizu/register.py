from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mizu_common import add_common_args, mizu_uac, print_json


async def register(
    *, local_host: str, local_port: int, timeout: float, keepalive: float
) -> None:
    async with mizu_uac(
        local_host=local_host,
        local_port=local_port,
        timeout=timeout,
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
        if keepalive > 0:
            await asyncio.sleep(keepalive)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="REGISTER the public Mizu demo account."
    )
    add_common_args(parser)
    parser.add_argument("--keepalive", type=float, default=0.0)
    args = parser.parse_args(argv)
    asyncio.run(
        register(
            local_host=args.local_host,
            local_port=args.local_port,
            timeout=args.timeout,
            keepalive=args.keepalive,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
