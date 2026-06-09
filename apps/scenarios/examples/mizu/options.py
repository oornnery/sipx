from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mizu_common import (
    add_common_args,
    default_target,
    print_json,
    response_summary,
    send_stateless_request,
)


async def options(
    *, target: str, local_host: str, local_port: int, timeout: float
) -> None:
    response = await send_stateless_request(
        method="OPTIONS",
        target=target,
        local_host=local_host,
        local_port=local_port,
        timeout=timeout,
    )
    print_json(response_summary(response))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send SIP OPTIONS to Mizu with pure Python."
    )
    parser.add_argument("target", nargs="?", default=default_target())
    add_common_args(parser)
    args = parser.parse_args(argv)
    asyncio.run(
        options(
            target=args.target,
            local_host=args.local_host,
            local_port=args.local_port,
            timeout=args.timeout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
