"""Synchronous SIP DNS resolver (RFC 3263)."""

from __future__ import annotations

import socket

from ._models import ResolvedTarget


class SipResolver:
    """Resolves SIP domains via SRV + A record fallback (sync)."""

    def __init__(self, nameservers: list[str] | None = None):
        self._nameservers = nameservers
        self._dns_resolver = None

    def _get_resolver(self):
        if self._dns_resolver is not None:
            return self._dns_resolver
        try:
            import dns.resolver

            self._dns_resolver = dns.resolver.Resolver()
            if self._nameservers:
                self._dns_resolver.nameservers = self._nameservers
            return self._dns_resolver
        except ImportError:
            return None

    def resolve(
        self, domain: str, transport: str | None = None
    ) -> list[ResolvedTarget]:
        resolver = self._get_resolver()
        if resolver is not None:
            targets = self._resolve_srv(resolver, domain, transport)
            if targets:
                return sorted(targets)
        return self._resolve_a(domain, transport)

    def resolve_uri(self, uri: str) -> list[ResolvedTarget]:
        from .._uri import SipURI

        parsed = SipURI.parse(uri)
        if parsed.port:
            transport = parsed.transport or ("TLS" if parsed.is_secure else "UDP")
            return [
                ResolvedTarget(
                    host=parsed.host, port=parsed.port, transport=transport.upper()
                )
            ]
        transport = parsed.transport
        if parsed.is_secure and not transport:
            transport = "TLS"
        return self.resolve(parsed.host, transport)

    def _resolve_srv(
        self, resolver, domain: str, transport: str | None
    ) -> list[ResolvedTarget]:
        import dns.resolver

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
            except (
                dns.resolver.NXDOMAIN,
                dns.resolver.NoAnswer,
                dns.resolver.NoNameservers,
            ):
                continue
            except Exception:
                continue
        return targets

    def _resolve_a(self, domain: str, transport: str | None) -> list[ResolvedTarget]:
        transport = (transport or "UDP").upper()
        port = 5061 if transport == "TLS" else 5060
        try:
            addr = socket.gethostbyname(domain)
            return [ResolvedTarget(host=addr, port=port, transport=transport)]
        except socket.gaierror:
            return [ResolvedTarget(host=domain, port=port, transport=transport)]
