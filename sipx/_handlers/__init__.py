"""
SIP Event Handlers Package.

This package provides a modular system for handling SIP messages, events,
and protocol flows. Handlers can be chained together to create complex
processing pipelines.

Base Classes:
    - EventHandler: Base class for synchronous handlers
    - AsyncEventHandler: Base class for asynchronous handlers
    - EventContext: Context passed between handlers
    - HandlerChain: Chain of handlers executed in sequence

Utility Handlers:
    - LoggingHandler: Logs SIP messages
    - RetryHandler: Implements retry logic
    - HeaderInjectionHandler: Injects custom headers
    - TimeoutHandler: Tracks request timeouts

Authentication:
    - AuthenticationHandler: Handles digest authentication with credential priority
    - LegacyAuthHandler: Backwards-compatible auth handler (deprecated)

Response Handlers:
    - ResponseCategory: Enum for response categories (1xx-6xx)
    - ProvisionalResponseHandler: Handles 1xx responses
    - FinalResponseHandler: Handles 2xx-6xx responses
    - ResponseFilterHandler: Filters responses by status code

Flow Handlers:
    - InviteFlowHandler: Manages INVITE transaction flow
    - InviteFlowState: State tracking for INVITE
    - RegisterFlowHandler: Manages REGISTER transaction flow
    - RegisterFlowState: State tracking for REGISTER

State Handlers:
    - TransactionStateHandler: Tracks transaction state
    - TransactionFlowState: State tracking for transactions
    - DialogStateHandler: Tracks dialog lifecycle

Composite Handlers:
    - SipFlowHandler: Complete handler combining all specialized handlers

Example:
    ```python
    from sipx import Client
    from sipx._handlers import (
        SipFlowHandler,
        AuthenticationHandler,
        LoggingHandler,
    )

    # Create client
    client = Client()

    # Add logging
    client.add_handler(LoggingHandler())

    # Add authentication
    from sipx._models._auth import SipAuthCredentials
    credentials = SipAuthCredentials(
        username="user",
        password="pass",
    )
    client.add_handler(AuthenticationHandler(credentials))

    # Add complete flow handling
    client.add_handler(SipFlowHandler(
        on_ringing=lambda resp, ctx: print("Ringing!"),
        on_registered=lambda resp, ctx: print("Registered!"),
    ))

    # Make requests - handlers process automatically
    response = client.invite("sip:bob@example.com", "example.com")
    ```
"""

# Base classes
from ._base import (
    EventContext,
    EventHandler,
    AsyncEventHandler,
    HandlerChain,
    AsyncHandlerChain,
)

# Utility handlers
from ._utility import (
    LoggingHandler,
    RetryHandler,
    HeaderInjectionHandler,
    TimeoutHandler,
)

# Authentication handlers
from ._auth import (
    AuthenticationHandler,
    LegacyAuthHandler,
)

# Response handlers
from ._response import (
    ResponseCategory,
    ProvisionalResponseHandler,
    FinalResponseHandler,
    ResponseFilterHandler,
)

# Flow-specific handlers
from ._invite import (
    InviteFlowHandler,
    InviteFlowState,
)

from ._register import (
    RegisterFlowHandler,
    RegisterFlowState,
)

# State handlers
from ._state import (
    TransactionStateHandler,
    TransactionFlowState,
    DialogStateHandler,
)

# Composite handler
from ._composite import (
    SipFlowHandler,
)


__all__ = [
    # Base
    "EventContext",
    "EventHandler",
    "AsyncEventHandler",
    "HandlerChain",
    "AsyncHandlerChain",
    # Utility
    "LoggingHandler",
    "RetryHandler",
    "HeaderInjectionHandler",
    "TimeoutHandler",
    # Authentication
    "AuthenticationHandler",
    "LegacyAuthHandler",
    # Response
    "ResponseCategory",
    "ProvisionalResponseHandler",
    "FinalResponseHandler",
    "ResponseFilterHandler",
    # Invite
    "InviteFlowHandler",
    "InviteFlowState",
    # Register
    "RegisterFlowHandler",
    "RegisterFlowState",
    # State
    "TransactionStateHandler",
    "TransactionFlowState",
    "DialogStateHandler",
    # Composite
    "SipFlowHandler",
]

