"""sipx - Modern SIP (Session Initiation Protocol) library for Python."""

from __future__ import annotations

# Client implementations
from ._client import AsyncClient, Client

# Server implementations
from ._server import AsyncSIPServer, SIPServer

# FSM components
from ._fsm import Dialog, StateManager, Transaction

# Handler system - All handlers now in modular _handlers package
from ._handlers import (
    # Base classes
    AsyncEventHandler,
    AsyncHandlerChain,
    EventContext,
    EventHandler,
    HandlerChain,
    # Utility handlers
    HeaderInjectionHandler,
    LoggingHandler,
    RetryHandler,
    TimeoutHandler,
    # Authentication
    AuthenticationHandler,
    LegacyAuthHandler as AuthHandler,  # Backwards compatibility
    # Response handlers
    ResponseCategory,
    ProvisionalResponseHandler,
    FinalResponseHandler,
    ResponseFilterHandler,
    # Flow handlers
    InviteFlowHandler,
    InviteFlowState,
    RegisterFlowHandler,
    RegisterFlowState,
    # State handlers
    TransactionStateHandler,
    TransactionFlowState,
    DialogStateHandler,
    # Composite handler
    SipFlowHandler,
)


# Decorators (kept at module level for backwards compatibility)
def on_request(func=None, *, method=None):
    """Decorator for request handlers."""
    import functools

    def decorator(f):
        @functools.wraps(f)
        def wrapper(request, context):
            if method and request.method != method:
                return request
            return f(request, context)

        wrapper._is_request_handler = True
        wrapper._filter_method = method
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def on_response(func=None, *, status_code=None, status_range=None):
    """Decorator for response handlers."""
    import functools

    def decorator(f):
        @functools.wraps(f)
        def wrapper(response, context):
            if status_code and response.status_code != status_code:
                return response
            if status_range:
                min_code, max_code = status_range
                if not (min_code <= response.status_code <= max_code):
                    return response
            return f(response, context)

        wrapper._is_response_handler = True
        wrapper._filter_status_code = status_code
        wrapper._filter_status_range = status_range
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def on_error(func):
    """Decorator for error handlers."""
    import functools

    @functools.wraps(func)
    def wrapper(error, context):
        return func(error, context)

    wrapper._is_error_handler = True
    return wrapper


def before_send(func):
    """Alias for on_request."""
    return on_request(func)


def after_receive(func):
    """Alias for on_response."""
    return on_response(func)


# Message models
from ._models import (
    AuthMethod,
    AuthParser,
    BodyParser,
    Challenge,
    ConferenceInfoBody,
    Credentials,
    DialogInfoBody,
    DigestAuth,
    DigestChallenge,
    DigestCredentials,
    DTMFBody,
    DTMFRelayBody,
    HeaderContainer,
    HeaderParser,
    Headers,
    HTMLBody,
    ISUPBody,
    MessageBody,
    MessageParser,
    MultipartBody,
    PIDFBody,
    RawBody,
    Request,
    ResourceListsBody,
    Response,
    SDPBody,
    SimpleMsgSummaryBody,
    SipAuthCredentials,
    SIPFragBody,
    SIPMessage,
    TextBody,
    XMLBody,
)

# Transport layer
from ._transports import (
    AsyncBaseTransport,
    BaseTransport,
    TransportAddress,
    TransportConfig,
    TransportError,
)

# Types
from ._types import (
    ConnectionError,
    DialogState,
    HeaderTypes,
    ReadError,
    TimeoutError,
    TransactionState,
    TransactionType,
    WriteError,
)

# Utilities
from ._utils import (
    BRANCH,
    EOL,
    HEADERS,
    HEADERS_COMPACT,
    REASON_PHRASES,
    SCHEME,
    VERSION,
    console,
    logger,
)

__version__ = "0.2.0"

__all__ = [
    # Client - Main API
    "Client",
    "AsyncClient",
    # Server - Listener API
    "SIPServer",
    "AsyncSIPServer",
    # Utilities - Console & Logging
    "console",
    "logger",
    # FSM - State Management
    "StateManager",
    "Transaction",
    "Dialog",
    "TransactionState",
    "DialogState",
    "TransactionType",
    # Handlers - Base Classes
    "EventHandler",
    "AsyncEventHandler",
    "HandlerChain",
    "AsyncHandlerChain",
    "EventContext",
    # Handlers - Utility
    "LoggingHandler",
    "RetryHandler",
    "HeaderInjectionHandler",
    "TimeoutHandler",
    # Handlers - Authentication
    "AuthenticationHandler",
    "AuthHandler",  # Legacy
    # Handlers - Response
    "ResponseCategory",
    "ProvisionalResponseHandler",
    "FinalResponseHandler",
    "ResponseFilterHandler",
    # Handlers - Flow
    "InviteFlowHandler",
    "InviteFlowState",
    "RegisterFlowHandler",
    "RegisterFlowState",
    # Handlers - State
    "TransactionStateHandler",
    "TransactionFlowState",
    "DialogStateHandler",
    # Handlers - Composite
    "SipFlowHandler",
    # Handlers - Decorators
    "on_request",
    "on_response",
    "on_error",
    "before_send",
    "after_receive",
    # Transport - Layer
    "BaseTransport",
    "AsyncBaseTransport",
    "TransportConfig",
    "TransportAddress",
    "TransportError",
    "ConnectionError",
    "ReadError",
    "WriteError",
    "TimeoutError",
    # Headers - Base classes
    "HeaderContainer",
    # Headers - Implementations
    "Headers",
    # Headers - Parser
    "HeaderParser",
    # Messages - Base classes
    "SIPMessage",
    # Messages - Implementations
    "Request",
    "Response",
    # Messages - Parser
    "MessageParser",
    # Body - Base classes
    "MessageBody",
    # Body - Implementations
    "SDPBody",
    "TextBody",
    "HTMLBody",
    "DTMFRelayBody",
    "DTMFBody",
    "SIPFragBody",
    "XMLBody",
    "PIDFBody",
    "ConferenceInfoBody",
    "DialogInfoBody",
    "ResourceListsBody",
    "ISUPBody",
    "SimpleMsgSummaryBody",
    "RawBody",
    "MultipartBody",
    # Body - Parser
    "BodyParser",
    # Authentication - Base classes
    "AuthMethod",
    "Challenge",
    "Credentials",
    # Authentication - Digest
    "DigestAuth",
    "DigestChallenge",
    "DigestCredentials",
    # Authentication - Simplified Credentials
    "SipAuthCredentials",
    # Authentication - Parser
    "AuthParser",
    # Constants
    "EOL",
    "SCHEME",
    "VERSION",
    "BRANCH",
    "HEADERS",
    "HEADERS_COMPACT",
    "REASON_PHRASES",
    # Types
    "HeaderTypes",
    # Metadata
    "__version__",
]
