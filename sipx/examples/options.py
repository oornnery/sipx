# RFC 3261 OPTIONS probe for the public Mizu demo server.

from __future__ import annotations

from sipx import SipUdpError
from sipx.examples.common import (
    error_summary,
    print_json,
    response_summary,
    run,
    send_stateless_request,
)


async def options() -> None:
    try:
        response = await send_stateless_request("OPTIONS")
    except (SipUdpError, TimeoutError) as exc:
        print_json(error_summary(exc))
        return
    print_json(response_summary(response))


def main() -> None:
    run(options())


if __name__ == "__main__":
    main()
