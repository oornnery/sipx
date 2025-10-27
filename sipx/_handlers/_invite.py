"""
INVITE flow handler for managing SIP call establishment.

This module handles the INVITE transaction flow including provisional responses,
final responses, early dialogs, confirmed dialogs, and ACK handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Callable

from ._base import EventHandler, EventContext
from ._response import ResponseCategory
from .._utils import logger

if TYPE_CHECKING:
    from .._models._message import Request, Response


@dataclass
class InviteFlowState:
    """
    State tracking for INVITE transaction flow.

    Tracks provisional responses, final response, dialog establishment,
    and ACK status for an INVITE transaction.
    """

    provisional_responses: list[Response] = field(default_factory=list)
    final_response: Optional[Response] = None
    ack_sent: bool = False
    ack_required: bool = False
    early_dialog_established: bool = False  # 180/183 with To tag
    confirmed_dialog_established: bool = False  # 200 OK received


class InviteFlowHandler(EventHandler):
    """
    Handles INVITE transaction flows according to RFC 3261 Section 13.

    INVITE flow:
    1. Client sends INVITE
    2. Server responds with 100 Trying (optional)
    3. Server responds with 180 Ringing (optional, can repeat)
    4. Server responds with 183 Session Progress (optional, with early media)
    5. Server responds with 200 OK (final success) or error (4xx-6xx)
    6. Client must send ACK for final response
    7. For 2xx: ACK establishes dialog
    8. For non-2xx: ACK completes transaction only

    Key features:
    - Tracks provisional and final responses
    - Detects early dialog establishment (provisional with To tag)
    - Detects confirmed dialog establishment (2xx response)
    - Signals when ACK is required
    - Optional callbacks for different stages
    """

    def __init__(
        self,
        auto_ack: bool = False,
        on_ringing: Optional[Callable[[Response, EventContext], None]] = None,
        on_progress: Optional[Callable[[Response, EventContext], None]] = None,
        on_established: Optional[Callable[[Response, EventContext], None]] = None,
        on_failed: Optional[Callable[[Response, EventContext], None]] = None,
    ):
        """
        Initialize INVITE flow handler.

        Args:
            auto_ack: If True, automatically send ACK (not implemented here, client handles)
            on_ringing: Callback when 180 Ringing received
            on_progress: Callback when 183 Session Progress received
            on_established: Callback when 200 OK received (call established)
            on_failed: Callback when error response received (call failed)
        """
        self.auto_ack = auto_ack
        self.on_ringing = on_ringing
        self.on_progress = on_progress
        self.on_established = on_established
        self.on_failed = on_failed
        self._invite_states: dict[str, InviteFlowState] = {}

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Track INVITE requests and initialize state."""
        if request.method == "INVITE":
            call_id = request.call_id
            if call_id:
                # Initialize state for this INVITE transaction
                self._invite_states[call_id] = InviteFlowState()
                context.metadata["invite_flow_state"] = self._invite_states[call_id]
                logger.debug(f"INVITE flow started for Call-ID: {call_id}")

        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Handle responses to INVITE requests."""
        # Only process responses to INVITE
        if not response.request or response.request.method != "INVITE":
            return response

        call_id = response.call_id
        if not call_id or call_id not in self._invite_states:
            return response

        state = self._invite_states[call_id]
        category = ResponseCategory.from_status_code(response.status_code)

        # Handle provisional responses (1xx)
        if category == ResponseCategory.PROVISIONAL:
            state.provisional_responses.append(response)

            if response.status_code == 180:
                # 180 Ringing
                logger.info("📞 Call ringing")
                if self.on_ringing:
                    self.on_ringing(response, context)

                # Check if early dialog established (To tag present)
                if response.to_header and "tag=" in response.to_header:
                    state.early_dialog_established = True
                    logger.debug("Early dialog established (180 with To tag)")

            elif response.status_code == 183:
                # 183 Session Progress with possible early media
                logger.info("📡 Session progress (early media available)")
                if self.on_progress:
                    self.on_progress(response, context)

                # Check for early dialog
                if response.to_header and "tag=" in response.to_header:
                    state.early_dialog_established = True
                    logger.debug("Early dialog established (183 with To tag)")

        # Handle final responses (2xx-6xx)
        else:
            state.final_response = response

            if category == ResponseCategory.SUCCESS:
                # 2xx Success - call established
                logger.info(f"✅ Call established: {response.status_code}")
                state.confirmed_dialog_established = True
                state.ack_required = True

                if self.on_established:
                    self.on_established(response, context)

                # Mark that ACK is needed for 2xx
                context.metadata["ack_required"] = True
                context.metadata["ack_for_success"] = True

            else:
                # 3xx-6xx Error - call failed
                logger.warning(
                    f"❌ Call failed: {response.status_code} {response.reason_phrase}"
                )
                state.ack_required = True

                if self.on_failed:
                    self.on_failed(response, context)

                # Mark that ACK is needed for non-2xx final response
                context.metadata["ack_required"] = True
                context.metadata["ack_for_success"] = False

        # Update context with current state
        context.metadata["invite_flow_state"] = state

        return response

    def mark_ack_sent(self, call_id: str) -> None:
        """
        Mark that ACK has been sent for this INVITE.

        Args:
            call_id: Call-ID of the INVITE transaction
        """
        if call_id in self._invite_states:
            self._invite_states[call_id].ack_sent = True
            logger.debug(f"ACK marked as sent for Call-ID: {call_id}")

    def get_state(self, call_id: str) -> Optional[InviteFlowState]:
        """
        Get the flow state for a specific INVITE.

        Args:
            call_id: Call-ID of the INVITE transaction

        Returns:
            InviteFlowState or None if not found
        """
        return self._invite_states.get(call_id)

    def cleanup(self, call_id: str) -> None:
        """
        Clean up state for completed INVITE transaction.

        Args:
            call_id: Call-ID of the INVITE transaction
        """
        if call_id in self._invite_states:
            del self._invite_states[call_id]
            logger.debug(f"Cleaned up INVITE state for Call-ID: {call_id}")
