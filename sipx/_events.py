"""
Simplified event system for SIP message handling.

This module provides a declarative, decorator-based API for handling SIP events,
making it easy to define custom behavior for specific methods and status codes.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from ._utils import logger

# Import at runtime for isinstance checks
from ._models._message import Request, Response

if TYPE_CHECKING:
    pass


# ============================================================================
# Event Context
# ============================================================================


@dataclass
class EventContext:
    """
    Context information passed to event handlers.

    Contains request/response data, transport information, and metadata
    that can be shared between handlers.
    """

    # Request/Response
    request: Optional["Request"] = None
    response: Optional["Response"] = None

    # Transport info
    destination: Optional[Any] = None
    source: Optional[Any] = None

    # Transaction/Dialog identifiers
    transaction_id: Optional[str] = None
    dialog_id: Optional[str] = None

    # Transaction/Dialog objects
    transaction: Optional[Any] = None
    dialog: Optional[Any] = None

    # Flexible metadata storage
    metadata: dict = field(default_factory=dict)


# ============================================================================
# Event Handler Decorator
# ============================================================================


def event_handler(
    method: Optional[Union[str, tuple[str, ...]]] = None,
    *,
    status: Optional[Union[int, tuple[int, ...], range]] = None,
):
    """
    Decorator for SIP event handlers.

    This decorator marks methods as handlers for specific SIP methods and/or
    status codes. It can be used as a method decorator within an Events class
    or as a standalone decorator.

    Args:
        method: SIP method(s) to match ('INVITE', 'REGISTER', etc.)
                Can be a single string or tuple of strings.
                If None, matches all methods.
        status: Status code(s) to match (200, 401, etc.)
                Can be a single int, tuple of ints, or range.
                If None, matches all status codes.

    Example:
        >>> class MyEvents(Events):
        ...     @event_handler('INVITE', status=200)
        ...     def on_invite_ok(self, request, response, context):
        ...         print("Call accepted!")
        ...
        ...     @event_handler(('INVITE', 'REGISTER'), status=(401, 407))
        ...     def on_auth_required(self, request, response, context):
        ...         print("Authentication required")

    Example (standalone):
        >>> on = Events.event_handler
        >>> @on('INVITE', status=200)
        ... def my_handler(request, response, context):
        ...     print("INVITE accepted")
    """

    def decorator(func: Callable) -> Callable:
        # Normalize method to tuple
        if method is None:
            methods = None
        elif isinstance(method, str):
            methods = (method,)
        else:
            methods = tuple(method)

        # Normalize status to tuple
        if status is None:
            statuses = None
        elif isinstance(status, int):
            statuses = (status,)
        elif isinstance(status, range):
            statuses = tuple(status)
        else:
            statuses = tuple(status)

        # Store metadata on function
        func._event_handler_method = methods
        func._event_handler_status = statuses
        func._is_event_handler = True

        return func

    return decorator


class Events:
    """
    Base class for SIP event handlers with declarative API.

    Inherit from this class and define methods to handle SIP events:

    - `on_request(request, context)` - Called for all outgoing requests
    - `on_response(response, context)` - Called for all incoming responses
    - Methods decorated with `@event_handler(...)` - Called for specific events

    The decorated methods receive `(request, response, context)` parameters
    and can modify the request/response or trigger actions.

    Example:
        >>> class MyEvents(Events):
        ...     def on_request(self, request, context):
        ...         print(f"Sending {request.method}")
        ...         return request
        ...
        ...     def on_response(self, response, context):
        ...         print(f"Received {response.status_code}")
        ...         return response
        ...
        ...     @event_handler('INVITE', status=200)
        ...     def on_invite_accepted(self, request, response, context):
        ...         print("Call accepted with SDP:")
        ...         print(response.body)
        ...
        ...     @event_handler('INVITE', status=(401, 407))
        ...     def on_invite_auth(self, request, response, context):
        ...         # Modify request and return for automatic retry
        ...         request.headers['Authorization'] = 'Digest ...'
        ...         return request

    Usage with Client:
        >>> with Client() as client:
        ...     client.events = MyEvents()
        ...     client.auth = Auth.Digest('alice', 'secret')
        ...     response = client.invite('sip:bob@example.com', 'sip:alice@local')
    """

    # Class-level reference to decorator for standalone use
    event_handler = staticmethod(event_handler)

    def __init__(self):
        """Initialize Events instance and discover decorated handlers."""
        self._handlers: list[tuple[Callable, Optional[tuple], Optional[tuple]]] = []
        self._discover_handlers()

    def _discover_handlers(self):
        """Discover all methods decorated with @event_handler."""
        for name in dir(self):
            # Skip private/magic methods and class attributes
            if name.startswith("_") or name in (
                "event_handler",
                "on_request",
                "on_response",
            ):
                continue

            attr = getattr(self, name)
            if callable(attr) and getattr(attr, "_is_event_handler", False):
                methods = getattr(attr, "_event_handler_method", None)
                statuses = getattr(attr, "_event_handler_status", None)
                self._handlers.append((attr, methods, statuses))

        logger.debug(
            f"Discovered {len(self._handlers)} event handlers in {self.__class__.__name__}"
        )

    def _matches_method(
        self, request_method: str, filter_methods: Optional[tuple]
    ) -> bool:
        """Check if request method matches filter."""
        if filter_methods is None:
            return True
        return request_method in filter_methods

    def _matches_status(
        self, response_status: int, filter_statuses: Optional[tuple]
    ) -> bool:
        """Check if response status matches filter."""
        if filter_statuses is None:
            return True
        return response_status in filter_statuses

    def on_request(self, request: Request, context: EventContext) -> Request:
        """
        Called before every request is sent.

        Override this method to add custom behavior for all outgoing requests.
        You can modify headers, log, or perform validation.

        Args:
            request: The SIP request about to be sent
            context: Event context with transaction/transport info

        Returns:
            Modified request (or original if no changes)

        Example:
            >>> def on_request(self, request, context):
            ...     request.headers['User-Agent'] = 'MyApp/1.0'
            ...     print(f"Sending {request.method} to {request.uri}")
            ...     return request
        """
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Called after every response is received.

        Override this method to add custom behavior for all incoming responses.
        You can process responses, extract data, or trigger actions.

        Args:
            response: The received SIP response
            context: Event context with request/response info

        Returns:
            Modified response (or original if no changes)

        Example:
            >>> def on_response(self, response, context):
            ...     print(f"Received {response.status_code} {response.reason_phrase}")
            ...     if response.status_code >= 400:
            ...         print(f"Error: {response.reason_phrase}")
            ...     return response
        """
        return response

    def _call_request_handlers(
        self, request: Request, context: EventContext
    ) -> Request:
        """
        Call on_request followed by matching decorated handlers.

        Returns:
            Modified request
        """
        # First call the generic on_request
        request = self.on_request(request, context)

        # Then call matching decorated handlers
        for handler, methods, statuses in self._handlers:
            # Request handlers only match on method
            if self._matches_method(request.method, methods):
                try:
                    # Get handler signature to determine what to pass
                    sig = inspect.signature(handler)
                    params = list(sig.parameters.keys())

                    # Call with appropriate parameters
                    # Handler signature: (request, context) or (request, response, context)
                    if len(params) == 2:  # self, request, context
                        result = handler(request, context)
                    else:  # self, request, response, context
                        result = handler(request, None, context)

                    # If handler returns a Request, use it
                    if isinstance(result, Request):
                        request = result

                except Exception as e:
                    logger.error(f"Error in request handler {handler.__name__}: {e}")

        return request

    def _call_response_handlers(
        self, response: Response, context: EventContext
    ) -> Response:
        """
        Call on_response followed by matching decorated handlers.

        Returns:
            Modified response or modified request (for retry)
        """
        # First call the generic on_response
        response = self.on_response(response, context)

        # Then call matching decorated handlers
        request = context.request

        for handler, methods, statuses in self._handlers:
            # Response handlers match on both method and status
            request_method = request.method if request else None

            if self._matches_method(request_method, methods) and self._matches_status(
                response.status_code, statuses
            ):
                try:
                    # Call handler with request, response, context
                    result = handler(request, response, context)

                    # Handler can return:
                    # - None: no action
                    # - Request: retry with modified request
                    # - Response: use modified response
                    if isinstance(result, Request):
                        # Store modified request for retry
                        context.metadata["retry_request"] = result
                    elif isinstance(result, Response):
                        response = result

                except Exception as e:
                    logger.error(f"Error in response handler {handler.__name__}: {e}")

        return response
