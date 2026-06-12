"""Transport registry and factory for SIP transports.

Provides a central registry for transport implementations and a
convenience factory function for creating transport instances.
"""

from __future__ import annotations

from sipx.transport.base import Transport, TransportConfig
from sipx.transport.tcp import TcpTransport
from sipx.transport.tls import TlsTransport
from sipx.transport.udp import UdpTransport


class TransportRegistry:
    """Registry for SIP transport implementations.

    Allows registration and creation of transport instances by type name.
    Default transports (udp, tcp, tls) are pre-registered.

    Example:
        registry = TransportRegistry()
        transport = registry.create("udp", TransportConfig(local_host="0.0.0.0", local_port=5060))
    """

    def __init__(self) -> None:
        """Initialize registry with default transports."""
        self._transports: dict[str, type[Transport]] = {
            "udp": UdpTransport,
            "tcp": TcpTransport,
            "tls": TlsTransport,
        }

    def register(self, transport_type: str, transport_class: type[Transport]) -> None:
        """Register a transport class under the given type name.

        Args:
            transport_type: Identifier for the transport (e.g., "udp", "tcp", "tls").
            transport_class: Transport class that implements the Transport interface.

        Raises:
            TypeError: If transport_class is not a subclass of Transport.
        """
        if not issubclass(transport_class, Transport):
            raise TypeError(
                f"{transport_class.__name__} must be a subclass of Transport"
            )
        self._transports[transport_type] = transport_class

    def create(self, transport_type: str, config: TransportConfig) -> Transport:
        """Create a transport instance of the given type.

        Args:
            transport_type: Identifier for the transport to create.
            config: Configuration for the transport instance.

        Returns:
            An instance of the requested transport class.

        Raises:
            ValueError: If the transport type is not registered.
        """
        if transport_type not in self._transports:
            raise ValueError(f"Unsupported transport type: {transport_type!r}")
        return self._transports[transport_type](config)

    def get_supported_types(self) -> list[str]:
        """Return a list of registered transport type identifiers.

        Returns:
            Sorted list of registered transport type names.
        """
        return sorted(self._transports.keys())


def create_transport(transport_type: str, config: TransportConfig) -> Transport:
    """Factory function to create a transport instance.

    Uses the default TransportRegistry with pre-registered transports.

    Args:
        transport_type: Identifier for the transport to create (e.g., "udp", "tcp", "tls").
        config: Configuration for the transport instance.

    Returns:
        An instance of the requested transport class.

    Raises:
        ValueError: If the transport type is not registered.

    Example:
        transport = create_transport("udp", TransportConfig(local_host="0.0.0.0", local_port=5060))
    """
    registry = TransportRegistry()
    return registry.create(transport_type, config)
