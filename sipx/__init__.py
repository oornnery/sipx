"""
sipx — Modern SIP library for Python.

Quick Start:
    >>> import sipx
    >>> r = sipx.register("sip:alice@pbx.com", auth=("alice", "secret"))
    >>> r = sipx.options("sip:pbx.com")

With Client:
    >>> from sipx import SIPClient, Events, on, SDPBody
    >>>
    >>> class MyEvents(Events):
    ...     @on('INVITE', status=200)
    ...     def on_call(self, request, response, context):
    ...         print("Call accepted!")
    ...
    >>> with SIPClient() as client:
    ...     client.auth = ("alice", "secret")
    ...     client.events = MyEvents()
    ...     r = client.invite("sip:bob@pbx.com", body=SDPBody.audio("10.0.0.1", 8000).to_string())

Server with DI:
    >>> from sipx import SIPServer, Request, Response, SDPBody, FromHeader, SDP
    >>> from typing import Annotated
    >>>
    >>> server = SIPServer(port=5060)
    >>> @server.invite()
    ... def on_invite(request: Request, caller: Annotated[str, FromHeader]) -> Response:
    ...     return request.ok()
"""

from __future__ import annotations

from typing import Optional

from ._events import Events, EventContext, event_handler, on
from ._routing import RouteSet
from ._types import (
    DialogState,
    HeaderTypes,
    ReadError,
    SIPAuthError,
    SIPConnectionError,
    SIPError,
    SIPParseError,
    SIPTimeoutError,
    TransactionState,
    TransactionType,
    WriteError,
)
from ._uri import SipURI
from ._utils import (
    BRANCH,
    EOL,
    HEADERS,
    HEADERS_COMPACT,
    REASON_PHRASES,
    SCHEME,
    VERSION,
    configure_logging,
)
from ._version import __version__
from .client import AsyncSIPClient, SIPClient
from .client._base import SIPClientBase
from ._depends import (
    AutoRTP,
    CallID,
    CSeqValue,
    Extractor,
    FromHeader,
    Header,
    SDP,
    Source,
    ToHeader,
    ViaValue,
    async_resolve_handler,
    resolve_handler,
)
from .dns import AsyncSipResolver, ResolvedTarget, SipResolver
from .fsm import AsyncTimerManager, Dialog, StateManager, TimerManager, Transaction
from .models import (
    Auth,
    AuthMethod,
    AuthParser,
    BodyParser,
    Challenge,
    Credentials,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    HeaderContainer,
    HeaderParser,
    Headers,
    MessageBody,
    MessageParser,
    RawBody,
    Request,
    Response,
    SDPBody,
    SIPMessage,
    SipAuthCredentials,
    PIFDBody,
)
from .client._base import ForkTracker
from .server import AsyncSIPServer, SIPServer, SIPServerBase
from .session import (
    AsyncSessionTimer,
    AsyncSubscription,
    ReferSubscription,
    SessionTimer,
    SessionTimerConfig,
    Subscription,
    SubscriptionState,
)
from .transports import (
    AsyncBaseTransport,
    BaseTransport,
    TransportAddress,
    TransportConfig,
    TransportError,
)

# Naming alias: SIPAuthCredentials (canonical uppercase-SIP style)
SIPAuthCredentials = SipAuthCredentials


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
    with SIPClient(transport=transport, auto_auth=bool(auth)) as client:
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
    with SIPClient(transport=transport, auto_auth=bool(auth)) as client:
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
    with SIPClient(transport=transport, auto_auth=bool(auth)) as client:
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
    with SIPClient(transport=transport, auto_auth=bool(auth)) as client:
        if auth:
            client.auth = auth
        return client.message(to_uri=uri, content=content)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # ------ Core ------
    "SIPClient",
    "AsyncSIPClient",
    "SIPClientBase",
    "ForkTracker",
    "SIPServer",
    "AsyncSIPServer",
    "SIPServerBase",
    # ------ Models ------
    "SIPMessage",
    "Request",
    "Response",
    "MessageParser",
    "Headers",
    "HeaderParser",
    "HeaderContainer",
    "MessageBody",
    "RawBody",
    "SDPBody",
    "BodyParser",
    "PIFDBody",
    # ------ Auth ------
    "Auth",
    "SipAuthCredentials",
    "SIPAuthCredentials",
    "AuthMethod",
    "DigestAuth",
    "DigestChallenge",
    "DigestCredentials",
    "Challenge",
    "Credentials",
    "AuthParser",
    # ------ Events ------
    "Events",
    "EventContext",
    "event_handler",
    "on",
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
    "resolve_handler",
    "async_resolve_handler",
    # ------ URI ------
    "SipURI",
    # ------ Session ------
    "SessionTimer",
    "AsyncSessionTimer",
    "SessionTimerConfig",
    "Subscription",
    "AsyncSubscription",
    "SubscriptionState",
    "ReferSubscription",
    # ------ Routing ------
    "RouteSet",
    # ------ DNS ------
    "SipResolver",
    "AsyncSipResolver",
    "ResolvedTarget",
    # ------ FSM ------
    "AsyncTimerManager",
    "Dialog",
    "StateManager",
    "TimerManager",
    "Transaction",
    # ------ Transport ------
    "BaseTransport",
    "AsyncBaseTransport",
    "TransportAddress",
    "TransportConfig",
    "TransportError",
    # ------ Types / Exceptions ------
    "DialogState",
    "TransactionState",
    "TransactionType",
    "HeaderTypes",
    "SIPError",
    "SIPConnectionError",
    "SIPTimeoutError",
    "SIPParseError",
    "SIPAuthError",
    "ReadError",
    "WriteError",
    # ------ One-liners ------
    "register",
    "options",
    "call",
    "send",
    # ------ Config ------
    "__version__",
    "configure_logging",
    # ------ SIP Constants ------
    "EOL",
    "SCHEME",
    "VERSION",
    "BRANCH",
    "HEADERS",
    "HEADERS_COMPACT",
    "REASON_PHRASES",
]
