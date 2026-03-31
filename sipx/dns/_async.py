"""Native async SIP DNS resolver (RFC 3263)."""

from __future__ import annotations

import asyncio
import socket

from ._models import ResolvedTarget


class AsyncSipResolver:
    """Resolves SIP domains via async DNS (native asyncio)."""

    def __init__(self, nameservers: list[str] | None = None):
        self._nameservers = nameservers

    async def resolve(
        self, domain: str, transport: str | None = None
    ) -> list[ResolvedTarget]:
        """Resolve domain using asyncio.getaddrinfo (non-blocking A record)."""
        # Try SRV via dnspython if available (run in thread — dnspython is sync)
        try:
            targets = await asyncio.to_thread(self._resolve_srv, domain, transport)
            if targets:
                return sorted(targets)
        except Exception:
            pass

        # Fallback: async A record via stdlib
        return await self._resolve_a(domain, transport)

    async def resolve_uri(self, uri: str) -> list[ResolvedTarget]:
        from .._uri import SipURI

        parsed = SipURI.parse(uri)
        if parsed.port:
            t = parsed.transport or ("TLS" if parsed.is_secure else "UDP")
            return [
                ResolvedTarget(host=parsed.host, port=parsed.port, transport=t.upper())
            ]
        transport = parsed.transport
        if parsed.is_secure and not transport:
            transport = "TLS"
        return await self.resolve(parsed.host, transport)

    def _resolve_srv(self, domain: str, transport: str | None) -> list[ResolvedTarget]:
        """SRV resolution (sync — called via to_thread)."""
        try:
            import dns.resolver
        except ImportError:
            return []

        resolver = dns.resolver.Resolver()
        if self._nameservers:
            resolver.nameservers = self._nameservers

        queries = []
        if transport:
            t = transport.upper()
            if t == "UDP":
                queries.append(("_sip._udp", "UDP"))
            elif t == "TCP":
                queries.append(("_sip._tcp", "TCP"))
            elif t == "TLS":
                queries.append(("_sips._tcp", "TLS"))
        else:
            queries = [
                ("_sip._udp", "UDP"),
                ("_sip._tcp", "TCP"),
                ("_sips._tcp", "TLS"),
            ]

        targets: list[ResolvedTarget] = []
        for prefix, proto in queries:
            try:
                answers = resolver.resolve(f"{prefix}.{domain}", "SRV")
                for rdata in answers:
                    targets.append(
                        ResolvedTarget(
                            priority=rdata.priority,
                            weight=rdata.weight,
                            host=str(rdata.target).rstrip("."),
                            port=rdata.port,
                            transport=proto,
                        )
                    )
            except Exception:
                continue
        return targets

    async def _resolve_a(
        self, domain: str, transport: str | None
    ) -> list[ResolvedTarget]:
        """Async A record resolution via asyncio.getaddrinfo."""
        transport = (transport or "UDP").upper()
        port = 5061 if transport == "TLS" else 5060
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(
                domain, port, family=socket.AF_INET, type=socket.SOCK_DGRAM
            )
            if infos:
                addr = infos[0][4][0]
                return [ResolvedTarget(host=addr, port=port, transport=transport)]
        except socket.gaierror:
            pass
        return [ResolvedTarget(host=domain, port=port, transport=transport)]
