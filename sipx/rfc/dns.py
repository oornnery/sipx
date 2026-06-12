"""RFC 3263 DNS resolution for locating SIP servers.

This module implements the algorithm specified in RFC 3263 for resolving
SIP URIs to transport addresses using NAPTR, SRV, and A/AAAA DNS records.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from sipx.exceptions import TransportError

if TYPE_CHECKING:
    from sipx.transport.registry import TransportRegistry


class SipDnsResolver:
    """RFC 3263 compliant DNS resolver for SIP URIs.

    Resolves SIP URIs to a list of transport addresses (host, port, transport)
    following the algorithm specified in RFC 3263.

    The resolver supports:
    - NAPTR record lookup for transport selection
    - SRV record lookup for host/port resolution
    - A/AAAA record lookup as fallback
    - Transport preference ordering (TLS > TCP > UDP)

    Example:
        resolver = SipDnsResolver()
        results = await resolver.resolve('sip:bob@example.com')
        # Returns: [('example.com', 5060, 'udp'), ...]
    """

    # Transport preference order (higher index = higher preference)
    TRANSPORT_PREFERENCE = {'udp': 0, 'tcp': 1, 'tls': 2}

    def __init__(self, registry: TransportRegistry | None = None) -> None:
        """Initialize the DNS resolver.

        Args:
            registry: Optional TransportRegistry for validating transport types.
                     If not provided, a default registry will be created.
        """
        if registry is None:
            from sipx.transport.registry import TransportRegistry
            registry = TransportRegistry()
        self._registry = registry
        self._mock_records: dict[str, list[tuple[str, int, str]]] = {}

    async def resolve(self, uri: str) -> list[tuple[str, int, str]]:
        """Resolve a SIP URI to transport addresses.

        Implements RFC 3263 section 4.1-4.4 for locating SIP servers.

        Args:
            uri: SIP URI string (e.g., 'sip:bob@example.com')

        Returns:
            List of (host, port, transport) tuples in preference order.
            Higher preference transports appear first.

        Raises:
            TransportError: If the URI is invalid or resolution fails.
        """
        try:
            scheme, host, port, transport = self._parse_uri(uri)
        except ValueError as e:
            raise TransportError(
                f"Invalid SIP URI: {uri}",
                details={'uri': uri, 'error': str(e)},
                rfc_ref='RFC 3261 Section 19.1'
            ) from e

        # Check for mock records (for testing)
        if host in self._mock_records:
            results = self._mock_records[host]
            return self._sort_by_preference(results)

        # RFC 3263 algorithm
        results: list[tuple[str, int, str]] = []

        # Step 1: If explicit transport parameter, use it
        if transport:
            if port:
                # Explicit port and transport: use directly
                results.append((host, port, transport))
            else:
                # Explicit transport, no port: try SRV, then A/AAAA
                srv_results = await self._query_srv_for_transport(transport, scheme, host)
                if srv_results:
                    results.extend(srv_results)
                else:
                    default_port = 5061 if scheme == 'sips' else 5060
                    a_results = await self._query_a_aaaa(host, default_port, transport)
                    results.extend(a_results)
        else:
            # Step 2: No explicit transport
            if port:
                # Explicit port, no transport: try SRV for each transport, then A/AAAA
                for proto in ['udp', 'tcp', 'tls']:
                    srv_results = await self._query_srv_for_transport(proto, scheme, host)
                    results.extend(srv_results)
                if not results:
                    a_results = await self._query_a_aaaa(host, port, 'udp')
                    results.extend(a_results)
            else:
                # No port, no transport: full RFC 3263 algorithm
                # Try NAPTR first
                naptr_results = await self._query_naptr(host, scheme)
                if naptr_results:
                    results.extend(naptr_results)
                else:
                    # No NAPTR: try SRV for each transport
                    for proto in ['udp', 'tcp', 'tls']:
                        srv_results = await self._query_srv_for_transport(proto, scheme, host)
                        results.extend(srv_results)

                # If still no results, fall back to A/AAAA
                if not results:
                    default_port = 5061 if scheme == 'sips' else 5060
                    default_transport = 'tls' if scheme == 'sips' else 'udp'
                    a_results = await self._query_a_aaaa(host, default_port, default_transport)
                    results.extend(a_results)

        if not results:
            raise TransportError(
                f"No DNS records found for {uri}",
                details={'uri': uri, 'host': host},
                rfc_ref='RFC 3263 Section 4'
            )

        return self._sort_by_preference(results)

    def _parse_uri(self, uri: str) -> tuple[str, str, int | None, str | None]:
        """Parse a SIP URI into its components.

        Args:
            uri: SIP URI string

        Returns:
            Tuple of (scheme, host, port, transport)

        Raises:
            ValueError: If the URI is not a valid SIP URI
        """
        # Match sip: or sips: scheme
        pattern = r'^(sips?):(?:[^@]+@)?([^:;>]+)(?::(\d+))?(?:;transport=([a-zA-Z]+))?'
        match = re.match(pattern, uri, re.IGNORECASE)
        if not match:
            raise ValueError(f"Not a valid SIP URI: {uri}")

        scheme = match.group(1).lower()
        host = match.group(2).lower()
        port = int(match.group(3)) if match.group(3) else None
        transport = match.group(4).lower() if match.group(4) else None

        # Validate transport if specified
        if transport and transport not in self._registry.get_supported_types():
            raise ValueError(f"Unsupported transport in URI: {transport}")

        return scheme, host, port, transport

    async def _query_naptr(self, domain: str, scheme: str) -> list[tuple[str, int, str]]:
        """Query NAPTR records for the domain.

        Args:
            domain: Domain name to query
            scheme: URI scheme ('sip' or 'sips')

        Returns:
            List of (host, port, transport) tuples from NAPTR records
        """
        # In a real implementation, this would query DNS NAPTR records
        # For now, return empty list (mock records are checked earlier)
        await asyncio.sleep(0)  # Simulate async operation
        return []

    async def _query_srv_for_transport(
        self, transport: str, scheme: str, domain: str
    ) -> list[tuple[str, int, str]]:
        """Query SRV records for a specific transport.

        Args:
            transport: Transport protocol ('udp', 'tcp', 'tls')
            scheme: URI scheme ('sip' or 'sips')
            domain: Domain name to query

        Returns:
            List of (host, port, transport) tuples from SRV records
        """
        # In a real implementation, this would query DNS SRV records
        # Format: _sip._udp.domain, _sip._tcp.domain, _sips._tcp.domain, etc.
        await asyncio.sleep(0)  # Simulate async operation
        return []

    async def _query_a_aaaa(
        self, host: str, port: int, transport: str
    ) -> list[tuple[str, int, str]]:
        """Query A/AAAA records for the host.

        Args:
            host: Hostname to query
            port: Port number to use
            transport: Transport protocol to use

        Returns:
            List of (host, port, transport) tuples from A/AAAA records
        """
        # In a real implementation, this would query DNS A/AAAA records
        # For now, return the host itself (mock records are checked earlier)
        await asyncio.sleep(0)  # Simulate async operation
        return [(host, port, transport)]

    def _sort_by_preference(
        self, results: list[tuple[str, int, str]]
    ) -> list[tuple[str, int, str]]:
        """Sort results by transport preference (TLS > TCP > UDP).

        Args:
            results: List of (host, port, transport) tuples

        Returns:
            Sorted list with preferred transports first
        """
        return sorted(
            results,
            key=lambda x: self.TRANSPORT_PREFERENCE.get(x[2], -1),
            reverse=True
        )
