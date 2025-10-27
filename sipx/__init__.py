"""
SIPX - Modern SIP (Session Initiation Protocol) library for Python.

This library provides a simplified, declarative API for SIP communication:

- **Events-based handlers**: Use the `Events` class with decorators
- **Simple authentication**: Use `Auth.Digest()` for authentication
- **Clean client API**: Simple method signatures with auto-extraction

Quick Start:
    >>> from sipx import Client, Events, Auth, event_handler, SDPBody
    >>>
    >>> class MyEvents(Events):
    ...     @event_handler('INVITE', status=200)
    ...     def on_call_accepted(self, request, response, context):
    ...         print("Call accepted!")
    ...
    >>> with Client() as client:
    ...     client.events = MyEvents()
    ...     client.auth = Auth.Digest('alice', 'secret')
    ...     response = client.invite('sip:bob@example.com', 'sip:alice@local')

Main Components:
    - Client: Synchronous SIP client
    - Events: Base class for event handlers
    - Auth: Authentication helpers (Auth.Digest)
    - event_handler: Decorator for specific events
    - SDPBody: SDP body creation and parsing

For advanced use cases, you can access:
    - Request/Response models
    - Body parsers (SDP, XML, PIDF, etc.)
    - Transport layer
    - State management (Transaction, Dialog)
"""

from __future__ import annotations

# ============================================================================
# Main API - Client and Server
# ============================================================================

from ._client import Client, AsyncClient

# ============================================================================
# Simplified Events API
# ============================================================================

from ._events import Events, EventContext, event_handler

# ============================================================================
# FSM Components (for advanced use)
# ============================================================================

from ._fsm import Dialog, StateManager, Transaction

# ============================================================================
# Message Models
# ============================================================================

from ._models import (
    # Base classes
    SIPMessage,
    Request,
    Response,
    MessageParser,
    # Headers
    Headers,
    HeaderParser,
    HeaderContainer,
    # Bodies
    MessageBody,
    SDPBody,
    BodyParser,
    # Authentication
    Auth,
    SipAuthCredentials,
    AuthMethod,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    Challenge,
    Credentials,
    AuthParser,
)

# ============================================================================
# Transport Layer
# ============================================================================

from ._transports import (
    BaseTransport,
    AsyncBaseTransport,
    TransportAddress,
    TransportConfig,
    TransportError,
)

# ============================================================================
# Types and Constants
# ============================================================================

from ._types import (
    DialogState,
    TransactionState,
    TransactionType,
    HeaderTypes,
    ConnectionError,
    ReadError,
    WriteError,
    TimeoutError,
)

from ._utils import (
    console,
    logger,
    EOL,
    SCHEME,
    VERSION,
    BRANCH,
    HEADERS,
    HEADERS_COMPACT,
    REASON_PHRASES,
)

# ============================================================================
# Version
# ============================================================================

__version__ = "0.3.0"

# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # ========================================================================
    # Main API - Start Here
    # ========================================================================
    "Client",
    "Events",
    "Auth",
    "event_handler",
    # ========================================================================
    # Core Models - Messages and Bodies
    # ========================================================================
    "Request",
    "Response",
    "SDPBody",
    "SipAuthCredentials",
    # ========================================================================
    # Advanced - Event Context
    # ========================================================================
    "EventContext",
    # ========================================================================
    # Advanced - State Management
    # ========================================================================
    "StateManager",
    "Transaction",
    "Dialog",
    "TransactionState",
    "DialogState",
    "TransactionType",
    # ========================================================================
    # Advanced - Message Models
    # ========================================================================
    "SIPMessage",
    "MessageParser",
    # Headers
    "Headers",
    "HeaderParser",
    "HeaderContainer",
    # Bodies
    "MessageBody",
    "SDPBody",
    "BodyParser",
    # ========================================================================
    # Advanced - Authentication
    # ========================================================================
    "AuthMethod",
    "DigestAuth",
    "DigestChallenge",
    "DigestCredentials",
    "Challenge",
    "Credentials",
    "AuthParser",
    # ========================================================================
    # Advanced - Transport
    # ========================================================================
    "BaseTransport",
    "AsyncBaseTransport",
    "TransportAddress",
    "TransportConfig",
    "TransportError",
    # ========================================================================
    # Advanced - Types and Errors
    # ========================================================================
    "HeaderTypes",
    "ConnectionError",
    "ReadError",
    "WriteError",
    "TimeoutError",
    # ========================================================================
    # Utilities
    # ========================================================================
    "console",
    "logger",
    # Constants
    "EOL",
    "SCHEME",
    "VERSION",
    "BRANCH",
    "HEADERS",
    "HEADERS_COMPACT",
    "REASON_PHRASES",
    # ========================================================================
    # Async (not yet implemented)
    # ========================================================================
    "AsyncClient",
]
