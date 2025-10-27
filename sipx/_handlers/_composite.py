"""
Composite SIP flow handler.

This module provides a single handler that combines all specialized handlers
for complete SIP flow management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._base import EventHandler, EventContext
from ._response import ProvisionalResponseHandler, FinalResponseHandler
from ._invite import InviteFlowHandler
from ._register import RegisterFlowHandler
from ._state import TransactionStateHandler, DialogStateHandler

if TYPE_CHECKING:
    from .._models._message import Request, Response


class SipFlowHandler(EventHandler):
    """
    Complete SIP flow handler combining all specialized handlers.

    This handler orchestrates:
    - Transaction state tracking
    - Dialog state management
    - Provisional response handling
    - Final response handling
    - Method-specific flows (INVITE, REGISTER)

    Use this as a single handler for complete SIP flow management,
    or use individual handlers for fine-grained control.

    Example:
        ```python
        from sipx import Client
        from sipx._handlers import SipFlowHandler

        # Create flow handler with callbacks
        flow_handler = SipFlowHandler(
            enable_invite_flow=True,
            enable_register_flow=True,
        )

        # Create client with flow handler
        client = Client()
        client.add_handler(flow_handler)

        # Make calls - flow handler manages the state
        response = client.invite(...)
        ```
    """

    def __init__(
        self,
        enable_invite_flow: bool = True,
        enable_register_flow: bool = True,
        enable_transaction_tracking: bool = True,
        enable_dialog_tracking: bool = True,
        enable_provisional_handler: bool = True,
        enable_final_handler: bool = True,
        **kwargs,
    ):
        """
        Initialize complete SIP flow handler.

        Args:
            enable_invite_flow: Enable INVITE-specific flow handling
            enable_register_flow: Enable REGISTER-specific flow handling
            enable_transaction_tracking: Enable transaction state tracking
            enable_dialog_tracking: Enable dialog state tracking
            enable_provisional_handler: Enable provisional response handler
            enable_final_handler: Enable final response handler
            **kwargs: Additional arguments passed to sub-handlers
        """
        self.handlers: list[EventHandler] = []

        # Add transaction tracking (first, for transaction IDs)
        if enable_transaction_tracking:
            self.handlers.append(TransactionStateHandler())

        # Add dialog tracking
        if enable_dialog_tracking:
            dialog_handler = DialogStateHandler(
                on_dialog_established=kwargs.get("on_dialog_established"),
                on_dialog_terminated=kwargs.get("on_dialog_terminated"),
            )
            self.handlers.append(dialog_handler)

        # Add provisional response handler
        if enable_provisional_handler:
            provisional_handler = ProvisionalResponseHandler(
                on_provisional=kwargs.get("on_provisional"),
                on_trying=kwargs.get("on_trying"),
                on_ringing=kwargs.get("on_ringing"),
                on_progress=kwargs.get("on_progress"),
            )
            self.handlers.append(provisional_handler)

        # Add final response handler
        if enable_final_handler:
            final_handler = FinalResponseHandler(
                on_success=kwargs.get("on_success"),
                on_redirect=kwargs.get("on_redirect"),
                on_client_error=kwargs.get("on_client_error"),
                on_server_error=kwargs.get("on_server_error"),
                on_global_failure=kwargs.get("on_global_failure"),
            )
            self.handlers.append(final_handler)

        # Add INVITE flow handler
        if enable_invite_flow:
            invite_handler = InviteFlowHandler(
                auto_ack=kwargs.get("auto_ack", False),
                on_ringing=kwargs.get("on_invite_ringing"),
                on_progress=kwargs.get("on_invite_progress"),
                on_established=kwargs.get("on_invite_established"),
                on_failed=kwargs.get("on_invite_failed"),
            )
            self.handlers.append(invite_handler)

        # Add REGISTER flow handler
        if enable_register_flow:
            register_handler = RegisterFlowHandler(
                auto_reregister=kwargs.get("auto_reregister", False),
                reregister_margin=kwargs.get("reregister_margin", 60),
                on_registered=kwargs.get("on_registered"),
                on_unregistered=kwargs.get("on_unregistered"),
                on_registration_failed=kwargs.get("on_registration_failed"),
            )
            self.handlers.append(register_handler)

    def on_request(self, request: Request, context: EventContext) -> Request:
        """
        Process request through all enabled handlers.

        Args:
            request: SIP request
            context: Event context

        Returns:
            Modified request after all handlers
        """
        for handler in self.handlers:
            request = handler.on_request(request, context)
        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """
        Process response through all enabled handlers.

        Args:
            response: SIP response
            context: Event context

        Returns:
            Modified response after all handlers
        """
        for handler in self.handlers:
            response = handler.on_response(response, context)
        return response

    def on_error(self, error: Exception, context: EventContext) -> None:
        """
        Process error through all enabled handlers.

        Args:
            error: Exception that occurred
            context: Event context
        """
        for handler in self.handlers:
            handler.on_error(error, context)

    def get_handler(self, handler_type: type) -> Optional[EventHandler]:
        """
        Get a specific sub-handler by type.

        Args:
            handler_type: Type of handler to retrieve

        Returns:
            Handler instance or None if not found

        Example:
            ```python
            flow_handler = SipFlowHandler()
            invite_handler = flow_handler.get_handler(InviteFlowHandler)
            if invite_handler:
                state = invite_handler.get_state(call_id)
            ```
        """
        for handler in self.handlers:
            if isinstance(handler, handler_type):
                return handler
        return None
