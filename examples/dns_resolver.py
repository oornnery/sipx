#!/usr/bin/env python3
"""
sipx — DNS SRV Resolution (RFC 3263)

Shows how sipx resolves SIP URIs to IP:port via DNS SRV records,
with fallback to A records. The Client uses this automatically
when auto_dns=True (default).

No Asterisk required for offline demo. SRV queries need dnspython.
"""

import asyncio

from sipx._utils import console


def demo_sync():
    """Synchronous DNS resolution."""
    from sipx.dns import SipResolver

    resolver = SipResolver()

    console.print("[bold]1. Sync SipResolver[/bold]\n")

    # Resolve a domain (tries SRV, then A)
    targets = resolver.resolve("sip.example.com")
    console.print("  resolve('sip.example.com'):")
    if targets:
        for t in targets:
            console.print(f"    -> {t.host}:{t.port} ({t.transport})")
    else:
        console.print("    (no results — expected if no real DNS)")

    # Resolve with specific transport
    targets = resolver.resolve("sip.example.com", transport="TCP")
    console.print("\n  resolve('sip.example.com', transport='TCP'):")
    if targets:
        for t in targets:
            console.print(f"    -> {t.host}:{t.port} ({t.transport})")
    else:
        console.print("    (no results)")

    # Resolve a full SIP URI
    targets = resolver.resolve_uri("sip:alice@example.com")
    console.print("\n  resolve_uri('sip:alice@example.com'):")
    if targets:
        for t in targets:
            console.print(f"    -> {t.host}:{t.port} ({t.transport})")
    else:
        console.print("    (no results)")

    # URI with explicit port (skips DNS)
    targets = resolver.resolve_uri("sip:alice@10.0.0.1:5060")
    console.print("\n  resolve_uri('sip:alice@10.0.0.1:5060'):")
    for t in targets:
        console.print(f"    -> {t.host}:{t.port} ({t.transport}) [explicit, no DNS]")

    # Localhost (A record fallback)
    targets = resolver.resolve("localhost")
    console.print("\n  resolve('localhost'):")
    for t in targets:
        console.print(f"    -> {t.host}:{t.port} ({t.transport})")


async def demo_async():
    """Asynchronous DNS resolution."""
    from sipx.dns import AsyncSipResolver

    resolver = AsyncSipResolver()

    console.print("\n[bold]2. Async AsyncSipResolver[/bold]\n")

    targets = await resolver.resolve("localhost")
    console.print("  resolve('localhost'):")
    for t in targets:
        console.print(f"    -> {t.host}:{t.port} ({t.transport})")

    targets = await resolver.resolve_uri("sips:secure@example.com")
    console.print("\n  resolve_uri('sips:secure@example.com'):")
    if targets:
        for t in targets:
            console.print(f"    -> {t.host}:{t.port} ({t.transport})")
    else:
        console.print("    (no results)")


def demo_auto_dns():
    """Show how Client uses DNS automatically."""
    console.print("\n[bold]3. Auto DNS in Client[/bold]\n")
    console.print("  Client(auto_dns=True)  # default")
    console.print("  client.invite('sip:bob@company.com')  # auto-resolves via SRV")
    console.print("  client.invite('sip:bob@10.0.0.1')     # IP detected, skips DNS")
    console.print("  Client(auto_dns=False) # disable auto DNS")


def main():
    console.print("[bold]sipx — DNS SRV Resolution (RFC 3263)[/bold]\n")

    demo_sync()
    asyncio.run(demo_async())
    demo_auto_dns()

    console.print("\n[bold green]DNS demo complete.[/bold green]")


if __name__ == "__main__":
    main()
