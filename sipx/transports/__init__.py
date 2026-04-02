"""
SIP transport layer.

This package provides transport implementations for SIP protocol:
- UDP: Connectionless, unreliable transport
- TCP: Connection-oriented, reliable transport
- TLS: Secure, connection-oriented transport
- WebSocket: WebSocket-based SIP transport (RFC 7118)

Both synchronous and asynchronous versions are provided for each transport.
"""

from ._framer import read_sip_message_sync, read_sip_message_async
from .._types import (
    SIPConnectionError,
    ReadError,
    SIPTimeoutError,
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
    "SIPConnectionError",
    "ReadError",
    "WriteError",
    "SIPTimeoutError",
    # Framing utilities
    "read_sip_message_sync",
    "read_sip_message_async",
    # Transport implementations (lazy-loaded)
    "UDPTransport",
    "AsyncUDPTransport",
    "TCPTransport",
    "AsyncTCPTransport",
    "TLSTransport",
    "AsyncTLSTransport",
    "WSTransport",
    "AsyncWSTransport",
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
    elif name == "WSTransport":
        from ._ws import WSTransport

        return WSTransport
    elif name == "AsyncWSTransport":
        from ._ws import AsyncWSTransport

        return AsyncWSTransport

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
