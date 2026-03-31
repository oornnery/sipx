"""
SIP DNS resolution (RFC 3263).

Resolves SIP URIs to transport addresses using DNS:
  1. NAPTR records (service selection: SIP+D2U, SIP+D2T, SIPS+D2T)
  2. SRV records (_sip._udp, _sip._tcp, _sips._tcp)
  3. A/AAAA records (fallback)

Usage::

    from sipx import SipResolver

    resolver = SipResolver()
    targets = resolver.resolve("example.com")
    # [ResolvedTarget(host="sip1.example.com", port=5060, transport="UDP", priority=10, weight=60)]

    # Or resolve a full SIP URI:
    targets = resolver.resolve_uri("sip:alice@example.com;transport=tcp")
    # Uses transport param hint, falls back to SRV/NAPTR
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field


@dataclass(order=True)
class ResolvedTarget:
    """A resolved SIP target with priority/weight for load balancing."""

    priority: int = 0
    weight: int = 0
    host: str = field(default="", compare=False)
    port: int = field(default=5060, compare=False)
    transport: str = field(default="UDP", compare=False)

    def __repr__(self) -> str:
        return f"{self.transport}:{self.host}:{self.port} (pri={self.priority} w={self.weight})"


class SipResolver:
    """Resolves SIP domains to transport addresses per RFC 3263.

    Tries in order:
      1. SRV lookup (_sip._udp.domain, _sip._tcp.domain, _sips._tcp.domain)
      2. A record fallback with default port

    Note: NAPTR is not commonly deployed. Most SIP infrastructure
    uses SRV directly. This resolver skips NAPTR for simplicity.
    """

    def __init__(self, nameservers: list[str] | None = None):
        self._nameservers = nameservers
        self._dns_resolver = None

    def _get_resolver(self):
        """Lazy-init dns.resolver (optional dependency)."""
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
        self,
        domain: str,
        transport: str | None = None,
    ) -> list[ResolvedTarget]:
        """Resolve a SIP domain to ordered list of targets.

        Args:
            domain: Domain name (e.g. "example.com").
            transport: Force transport ("UDP", "TCP", "TLS"). If None, tries all.

        Returns:
            List of ResolvedTarget sorted by priority then weight.
        """
        resolver = self._get_resolver()

        # If dnspython is available, use SRV
        if resolver is not None:
            targets = self._resolve_srv(resolver, domain, transport)
            if targets:
                return sorted(targets)

        # Fallback: A record with default port
        return self._resolve_a(domain, transport)

    def resolve_uri(self, uri: str) -> list[ResolvedTarget]:
        """Resolve a SIP URI to transport targets.

        Extracts domain and transport hint from URI, then resolves.

        Args:
            uri: SIP URI (e.g. "sip:alice@example.com;transport=tcp").

        Returns:
            List of ResolvedTarget.
        """
        from ._uri import SipURI

        parsed = SipURI.parse(uri)

        # If port is explicit, no DNS needed
        if parsed.port:
            transport = parsed.transport or ("TLS" if parsed.is_secure else "UDP")
            return [
                ResolvedTarget(
                    host=parsed.host,
                    port=parsed.port,
                    transport=transport.upper(),
                )
            ]

        transport = parsed.transport
        if parsed.is_secure and not transport:
            transport = "TLS"

        return self.resolve(parsed.host, transport)

    def _resolve_srv(
        self,
        resolver,
        domain: str,
        transport: str | None,
    ) -> list[ResolvedTarget]:
        """Try SRV records for SIP services."""
        import dns.resolver

        srv_queries = []
        if transport:
            t = transport.upper()
            if t == "UDP":
                srv_queries.append(("_sip._udp", "UDP"))
            elif t == "TCP":
                srv_queries.append(("_sip._tcp", "TCP"))
            elif t == "TLS":
                srv_queries.append(("_sips._tcp", "TLS"))
        else:
            # Try all in preference order
            srv_queries = [
                ("_sip._udp", "UDP"),
                ("_sip._tcp", "TCP"),
                ("_sips._tcp", "TLS"),
            ]

        targets: list[ResolvedTarget] = []

        for prefix, proto in srv_queries:
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

    def _resolve_a(
        self,
        domain: str,
        transport: str | None,
    ) -> list[ResolvedTarget]:
        """Fallback: resolve domain via A record with default port."""
        transport = (transport or "UDP").upper()
        port = 5061 if transport == "TLS" else 5060

        try:
            # Use stdlib socket for A record
            addr = socket.gethostbyname(domain)
            return [
                ResolvedTarget(
                    host=addr,
                    port=port,
                    transport=transport,
                )
            ]
        except socket.gaierror:
            # Domain doesn't resolve — return as-is (might be an IP)
            return [
                ResolvedTarget(
                    host=domain,
                    port=port,
                    transport=transport,
                )
            ]


__all__ = ["SipResolver", "ResolvedTarget"]
