"""
Script principal para demonstração e testes da stack SIP.
"""

import asyncio

from stack import AsyncSIPStack
from uri import URI


async def main():
    local = URI.parse("sip:alice@localhost")
    dest = URI.parse("sip:bob@127.0.0.1")
    stack = AsyncSIPStack(local)
    await stack.invite(dest)


if __name__ == "__main__":
    asyncio.run(main())
