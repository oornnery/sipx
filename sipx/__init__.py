"""
sipx — Modern SIP library for Python.

Quick Start:
    >>> import sipx
    >>> r = sipx.register("sip:alice@pbx.com", auth=("alice", "secret"))
    >>> r = sipx.options("sip:pbx.com")

With Client:
    >>> from sipx import Client, Events, on, SDPBody
    >>>
    >>> class MyEvents(Events):
    ...     @on('INVITE', status=200)
    ...     def on_call(self, request, response, context):
    ...         print("Call accepted!")
    ...
    >>> with Client() as client:
    ...     client.auth = ("alice", "secret")
    ...     client.events = MyEvents()
    ...     r = client.invite("sip:bob@pbx.com", body=SDPBody.audio("10.0.0.1", 8000).to_string())

Server with DI:
    >>> from sipx import SIPServer, Request, Response, SDPBody, FromHeader, SDP
    >>> from typing import Annotated
    >>>
    >>> server = SIPServer(port=5060)
    >>> @server.invite
    ... def on_invite(request: Request, caller: Annotated[str, FromHeader]) -> Response:
    ...     return Response(200)
"""

from __future__ import annotations

from typing import Optional

# ============================================================================
# Client / Server
# ============================================================================

from ._client import Client, AsyncClient
from ._server import SIPServer

# ============================================================================
# Events
# ============================================================================

from ._events import Events, EventContext, event_handler, on

# ============================================================================
# Models
# ============================================================================

from ._models import (
    SIPMessage,
    Request,
    Response,
    MessageParser,
    Headers,
    HeaderParser,
    HeaderContainer,
    MessageBody,
    RawBody,
    SDPBody,
    BodyParser,
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
# DI Extractors
# ============================================================================

from ._depends import (
    Extractor,
    FromHeader,
    ToHeader,
    CallID,
    CSeqValue,
    ViaValue,
    SDP,
    Source,
    Header,
    AutoRTP,
    resolve_handler,
)

# ============================================================================
# URI
# ============================================================================

from ._uri import SipURI
from ._session_timer import SessionTimer, SessionTimerConfig
from ._routing import RouteSet

# ============================================================================
# FSM
# ============================================================================

from ._fsm import Dialog, StateManager, TimerManager, Transaction

# ============================================================================
# Transport
# ============================================================================

from ._transports import (
    BaseTransport,
    AsyncBaseTransport,
    TransportAddress,
    TransportConfig,
    TransportError,
)

# ============================================================================
# Types
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

# ============================================================================
# Version
# ============================================================================

__version__ = "0.3.0"


# ============================================================================
# One-liner functions (httpx-style)
# ============================================================================


def register(
    aor: str,
    *,
    auth: Optional[tuple[str, str]] = None,
    transport: str = "UDP",
    expires: int = 3600,
) -> Response:
    """Register with a SIP server.

    >>> r = sipx.register("sip:alice@pbx.com", auth=("alice", "secret"))
    """
    with Client(transport=transport, auto_auth=bool(auth)) as client:
        if auth:
            client.auth = auth
        return client.register(aor, expires=expires)


def options(
    uri: str,
    *,
    auth: Optional[tuple[str, str]] = None,
    transport: str = "UDP",
) -> Response:
    """Query server capabilities.

    >>> r = sipx.options("sip:pbx.com")
    """
    with Client(transport=transport, auto_auth=bool(auth)) as client:
        if auth:
            client.auth = auth
        return client.options(uri)


def call(
    uri: str,
    *,
    auth: Optional[tuple[str, str]] = None,
    transport: str = "UDP",
    body: Optional[str] = None,
) -> Response:
    """Make a SIP call (INVITE).

    >>> r = sipx.call("sip:100@pbx.com", auth=("alice", "secret"))
    """
    with Client(transport=transport, auto_auth=bool(auth)) as client:
        if auth:
            client.auth = auth
        return client.invite(to_uri=uri, body=body)


def send(
    uri: str,
    content: str = "",
    *,
    auth: Optional[tuple[str, str]] = None,
    transport: str = "UDP",
) -> Response:
    """Send a SIP MESSAGE.

    >>> r = sipx.send("sip:bob@pbx.com", "Hello!", auth=("alice", "secret"))
    """
    with Client(transport=transport, auto_auth=bool(auth)) as client:
        if auth:
            client.auth = auth
        return client.message(to_uri=uri, content=content)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # ------ Main API ------
    "Client",
    "AsyncClient",
    "SIPServer",
    "SipURI",
    "SessionTimer",
    "SessionTimerConfig",
    "RouteSet",
    "Events",
    "EventContext",
    "event_handler",
    "on",
    # ------ One-liners ------
    "register",
    "options",
    "call",
    "send",
    # ------ Auth ------
    "Auth",
    "SipAuthCredentials",
    # ------ Models ------
    "Request",
    "Response",
    "SDPBody",
    "Headers",
    # ------ DI Extractors ------
    "Extractor",
    "FromHeader",
    "ToHeader",
    "CallID",
    "CSeqValue",
    "ViaValue",
    "SDP",
    "Source",
    "Header",
    "AutoRTP",
    # ------ Transport ------
    "BaseTransport",
    "TransportAddress",
    "TransportConfig",
    "TransportError",
    # ------ Advanced ------
    "SIPMessage",
    "MessageParser",
    "HeaderParser",
    "HeaderContainer",
    "MessageBody",
    "RawBody",
    "BodyParser",
    "AuthMethod",
    "DigestAuth",
    "DigestChallenge",
    "DigestCredentials",
    "Challenge",
    "Credentials",
    "AuthParser",
    "AsyncBaseTransport",
    "StateManager",
    "TimerManager",
    "Transaction",
    "Dialog",
    "TransactionState",
    "DialogState",
    "TransactionType",
    "HeaderTypes",
    "ConnectionError",
    "ReadError",
    "WriteError",
    "TimeoutError",
    "resolve_handler",
]
