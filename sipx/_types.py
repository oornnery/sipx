"""
Type definitions and aliases for SIP protocol.

This module centralizes all type definitions used throughout the SIP library,
including transport types, FSM states, and common type aliases.
"""

from __future__ import annotations

import typing
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

if typing.TYPE_CHECKING:
    from .headers import Headers
    from ._models._message import Request, Response


# =============================================================================
# Header Types
# =============================================================================

HeaderTypes = typing.Union[
    "Headers",
    Mapping[str, str],
]


# =============================================================================
# Transport Configuration
# =============================================================================


@dataclass
class TransportConfig:
    """Configuration for SIP transports."""

    # Network settings
    local_host: str = "0.0.0.0"
    local_port: int = 5060

    # Timeouts (in seconds)
    connect_timeout: float = 5.0
    read_timeout: float = 32.0  # SIP Timer B (INVITE transaction timeout)
    write_timeout: float = 5.0

    # Buffer settings
    buffer_size: int = 65535  # Max SIP message size

    # Retry settings
    max_retries: int = 0
    retry_backoff_factor: float = 0.5

    # TLS settings (used only for TLS transport)
    verify_mode: bool = True
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    ca_certs: Optional[str] = None

    # Protocol-specific
    enable_keepalive: bool = False
    keepalive_interval: float = 30.0

    # Additional options
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransportAddress:
    """Represents a transport address (host, port, protocol)."""

    host: str
    port: int = 5060
    protocol: str = "UDP"  # UDP, TCP, or TLS

    def __str__(self) -> str:
        return f"{self.protocol.upper()}:{self.host}:{self.port}"

    @property
    def is_secure(self) -> bool:
        """Check if transport uses TLS."""
        return self.protocol.upper() == "TLS"

    @property
    def is_reliable(self) -> bool:
        """Check if transport is connection-oriented (TCP/TLS)."""
        return self.protocol.upper() in ("TCP", "TLS")

    @classmethod
    def from_uri(cls, uri: str) -> TransportAddress:
        """
        Parse transport address from SIP URI.

        Examples:
            sip:user@host:5060;transport=tcp
            sips:user@host:5061
        """
        # Simple parser - extend as needed
        protocol = "TLS" if uri.startswith("sips:") else "UDP"

        # Extract host and port
        # This is simplified - real implementation should use URI parser
        parts = uri.split("@")
        if len(parts) > 1:
            host_part = parts[1].split(";")[0]
        else:
            host_part = uri.split(":")[1].lstrip("/").split(";")[0]

        if ":" in host_part:
            host, port_str = host_part.rsplit(":", 1)
            port = int(port_str)
        else:
            host = host_part
            port = 5061 if protocol == "TLS" else 5060

        # Check for transport parameter
        if ";transport=" in uri:
            transport_param = uri.split(";transport=")[1].split(";")[0]
            protocol = transport_param.upper()

        return cls(host=host, port=port, protocol=protocol)


# =============================================================================
# Transport Exceptions
# =============================================================================


class TransportError(Exception):
    """Base exception for transport errors."""

    pass


class ConnectionError(TransportError):
    """Raised when connection fails (TCP/TLS only)."""

    pass


class WriteError(TransportError):
    """Raised when writing to transport fails."""

    pass


class ReadError(TransportError):
    """Raised when reading from transport fails."""

    pass


class TimeoutError(TransportError):
    """Raised when operation times out."""

    pass


# =============================================================================
# FSM States and Types (RFC 3261)
# =============================================================================


class TransactionState(Enum):
    """
    States for SIP client transactions (RFC 3261 Section 17.1).

    INVITE transactions (ICT) have different state machines than non-INVITE (NICT).

    ICT States: CALLING → PROCEEDING → COMPLETED → TERMINATED
                         ↓
                       CONFIRMED (on 2xx)

    NICT States: TRYING → PROCEEDING → COMPLETED → TERMINATED
    """

    # Common states
    CALLING = auto()  # Initial state, request sent (ICT)
    TRYING = auto()  # Initial state for non-INVITE (NICT)
    PROCEEDING = auto()  # 1xx response received
    COMPLETED = auto()  # Final response received
    TERMINATED = auto()  # Transaction finished

    # INVITE-specific states
    CONFIRMED = auto()  # ACK sent for 2xx response (ICT only)


class DialogState(Enum):
    """
    States for SIP dialogs (RFC 3261 Section 12).

    Dialogs represent peer-to-peer SIP relationships that persist
    across multiple transactions.
    """

    EARLY = auto()  # Dialog created by 1xx response with To tag
    CONFIRMED = auto()  # Dialog confirmed by 2xx response
    TERMINATED = auto()  # Dialog ended by BYE or error


class TransactionType(Enum):
    """
    Type of SIP transaction.

    SIP defines four FSMs:
    - ICT (Invite Client Transaction)
    - NICT (Non-Invite Client Transaction)
    - IST (Invite Server Transaction)
    - NIST (Non-Invite Server Transaction)

    Currently we model client transactions (ICT/NICT).
    """

    INVITE = auto()  # INVITE transaction (ICT)
    NON_INVITE = auto()  # All other methods: REGISTER, OPTIONS, BYE, etc. (NICT)


# =============================================================================
# Type Aliases
# =============================================================================

# Message types
RequestLike = typing.Union["Request", bytes, str]
ResponseLike = typing.Union["Response", bytes, str]

# Address types
AddressLike = typing.Union[TransportAddress, str, tuple[str, int]]

# Callback types
TransactionCallback = typing.Callable[["Transaction"], None]
DialogCallback = typing.Callable[["Dialog"], None]

# Handler types (forward references for _handlers module)
if typing.TYPE_CHECKING:
    from ._handlers import EventHandler, AsyncEventHandler

    HandlerType = typing.Union[EventHandler, AsyncEventHandler]
    SyncHandlerType = EventHandler
    AsyncHandlerType = AsyncEventHandler


# =============================================================================
# Re-exports for convenience
# =============================================================================

__all__ = [
    # Header types
    "HeaderTypes",
    # Transport types
    "TransportConfig",
    "TransportAddress",
    # Exceptions
    "TransportError",
    "ConnectionError",
    "WriteError",
    "ReadError",
    "TimeoutError",
    # FSM enums
    "TransactionState",
    "DialogState",
    "TransactionType",
    # Type aliases
    "RequestLike",
    "ResponseLike",
    "AddressLike",
    "TransactionCallback",
    "DialogCallback",
]
