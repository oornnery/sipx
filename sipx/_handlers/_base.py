"""
Base classes for SIP event handlers.

This module provides the foundational abstract classes and data structures
for building custom SIP event handlers.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .._models._message import Request, Response
    from .._types import TransportAddress


@dataclass
class EventContext:
    """
    Context information passed to event handlers.

    Contains request/response data, transport information, and metadata
    that can be shared between handlers in the chain.
    """

    # Request/Response
    request: Optional[Request] = None
    response: Optional[Response] = None

    # Transport info
    destination: Optional[TransportAddress] = None
    source: Optional[TransportAddress] = None

    # Transaction/Dialog identifiers
    transaction_id: Optional[str] = None
    dialog_id: Optional[str] = None

    # Flexible metadata storage for handler communication
    metadata: dict = field(default_factory=dict)


class EventHandler(ABC):
    """
    Abstract base class for synchronous event handlers.

    Event handlers can intercept and modify SIP messages at various points
    in the request/response cycle. They can also store state in the context
    metadata for communication between handlers.

    Custom handlers should inherit from this class and override the methods
    they need to customize.
    """

    def on_request(self, request: Request, context: EventContext) -> Request:
        """
        Called before a request is sent.

        Use this to modify outgoing requests, add headers, log, etc.

        Args:
            request: The SIP request to be sent
            context: Event context with transaction/transport info

        Returns:
            Modified request (or original if no changes)
        """
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Called after a response is received.

        Use this to process responses, extract data, trigger actions, etc.
        Responses include both provisional (1xx) and final (2xx-6xx).

        Args:
            response: The received SIP response
            context: Event context with request/response info

        Returns:
            Modified response (or original if no changes)
        """
        return response

    def on_error(self, error: Exception, context: EventContext) -> None:
        """
        Called when an error occurs during request/response processing.

        Use this for error logging, cleanup, or recovery actions.

        Args:
            error: The exception that occurred
            context: Event context at the time of error
        """
        pass


class AsyncEventHandler(ABC):
    """
    Abstract base class for asynchronous event handlers.

    Similar to EventHandler but with async methods for use with AsyncClient.
    """

    async def on_request(self, request: Request, context: EventContext) -> Request:
        """
        Called before a request is sent (async).

        Args:
            request: The SIP request to be sent
            context: Event context with transaction/transport info

        Returns:
            Modified request (or original if no changes)
        """
        return request

    async def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Called after a response is received (async).

        Args:
            response: The received SIP response
            context: Event context with request/response info

        Returns:
            Modified response (or original if no changes)
        """
        return response

    async def on_error(self, error: Exception, context: EventContext) -> None:
        """
        Called when an error occurs (async).

        Args:
            error: The exception that occurred
            context: Event context at the time of error
        """
        pass


class HandlerChain:
    """
    Chain of event handlers executed in sequence.

    Handlers are called in the order they were added. Each handler
    can modify the request/response or context metadata.
    """

    def __init__(self):
        """Initialize empty handler chain."""
        self._handlers: list[EventHandler] = []

    def add_handler(self, handler: EventHandler) -> None:
        """
        Add a handler to the end of the chain.

        Args:
            handler: Event handler to add
        """
        self._handlers.append(handler)

    def remove_handler(self, handler: EventHandler) -> None:
        """
        Remove a handler from the chain.

        Args:
            handler: Event handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    def clear(self) -> None:
        """Remove all handlers from the chain."""
        self._handlers.clear()

    def on_request(self, request: Request, context: EventContext) -> Request:
        """
        Execute all handlers' on_request methods in sequence.

        Args:
            request: SIP request
            context: Event context

        Returns:
            Modified request after all handlers
        """
        for handler in self._handlers:
            try:
                request = handler.on_request(request, context)
            except Exception as e:
                # Call error handlers for this exception
                for h in self._handlers:
                    try:
                        h.on_error(e, context)
                    except Exception:
                        pass  # Ignore errors in error handlers
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Execute all handlers' on_response methods in sequence.

        Args:
            response: SIP response
            context: Event context

        Returns:
            Modified response after all handlers
        """
        for handler in self._handlers:
            try:
                response = handler.on_response(response, context)
            except Exception as e:
                # Call error handlers
                for h in self._handlers:
                    try:
                        h.on_error(e, context)
                    except Exception:
                        pass
        return response

    def on_error(self, error: Exception, context: EventContext) -> None:
        """
        Execute all handlers' on_error methods.

        Args:
            error: Exception that occurred
            context: Event context
        """
        for handler in self._handlers:
            try:
                handler.on_error(error, context)
            except Exception:
                pass  # Ignore errors in error handlers

    def __len__(self) -> int:
        """Return number of handlers in chain."""
        return len(self._handlers)


class AsyncHandlerChain:
    """
    Async version of HandlerChain for asynchronous handlers.
    """

    def __init__(self):
        """Initialize empty async handler chain."""
        self._handlers: list[AsyncEventHandler] = []

    def add_handler(self, handler: AsyncEventHandler) -> None:
        """
        Add an async handler to the chain.

        Args:
            handler: Async event handler to add
        """
        self._handlers.append(handler)

    def remove_handler(self, handler: AsyncEventHandler) -> None:
        """
        Remove an async handler from the chain.

        Args:
            handler: Async event handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    def clear(self) -> None:
        """Remove all handlers from the chain."""
        self._handlers.clear()

    async def on_request(self, request: Request, context: EventContext) -> Request:
        """
        Execute all async handlers' on_request methods.

        Args:
            request: SIP request
            context: Event context

        Returns:
            Modified request after all handlers
        """
        for handler in self._handlers:
            try:
                request = await handler.on_request(request, context)
            except Exception as e:
                for h in self._handlers:
                    try:
                        await h.on_error(e, context)
                    except Exception:
                        pass
        return request

    async def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Execute all async handlers' on_response methods.

        Args:
            response: SIP response
            context: Event context

        Returns:
            Modified response after all handlers
        """
        for handler in self._handlers:
            try:
                response = await handler.on_response(response, context)
            except Exception as e:
                for h in self._handlers:
                    try:
                        await h.on_error(e, context)
                    except Exception:
                        pass
        return response

    async def on_error(self, error: Exception, context: EventContext) -> None:
        """
        Execute all async handlers' on_error methods.

        Args:
            error: Exception that occurred
            context: Event context
        """
        for handler in self._handlers:
            try:
                await handler.on_error(error, context)
            except Exception:
                pass

    def __len__(self) -> int:
        """Return number of handlers in chain."""
        return len(self._handlers)
