"""
SIP transport layer.

This package provides transport implementations for SIP protocol:
- UDP: Connectionless, unreliable transport
- TCP: Connection-oriented, reliable transport
- TLS: Secure, connection-oriented transport

Both synchronous and asynchronous versions are provided for each transport.
"""

from .._types import (
    ConnectionError,
    ReadError,
    TimeoutError,
    TransportAddress,
    TransportConfig,
    TransportError,
    WriteError,
)
from ._base import AsyncBaseTransport, BaseTransport

__all__ = [
    # Base classes
    "BaseTransport",
    "AsyncBaseTransport",
    "TransportConfig",
    "TransportAddress",
    # Exceptions
    "TransportError",
    "ConnectionError",
    "ReadError",
    "WriteError",
    "TimeoutError",
]


# Transport implementations will be lazy-loaded to avoid import overhead
def __getattr__(name: str):
    """Lazy import transport implementations."""
    if name == "UDPTransport":
        from ._udp import UDPTransport

        return UDPTransport
    elif name == "AsyncUDPTransport":
        from ._udp import AsyncUDPTransport

        return AsyncUDPTransport
    elif name == "TCPTransport":
        from ._tcp import TCPTransport

        return TCPTransport
    elif name == "AsyncTCPTransport":
        from ._tcp import AsyncTCPTransport

        return AsyncTCPTransport
    elif name == "TLSTransport":
        from ._tls import TLSTransport

        return TLSTransport
    elif name == "AsyncTLSTransport":
        from ._tls import AsyncTLSTransport

        return AsyncTLSTransport

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
