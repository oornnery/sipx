"""
State handlers for SIP transactions and dialogs.

This module provides handlers that track transaction state (request/response
correlation) and dialog state (session lifecycle) according to RFC 3261.
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
class TransactionFlowState:
    """
    State tracking for a SIP transaction.

    A transaction consists of:
    - One request
    - Zero or more provisional responses (1xx)
    - One final response (2xx-6xx)
    """

    request: Optional[Request] = None
    provisional_responses: list[Response] = field(default_factory=list)
    final_response: Optional[Response] = None
    completed: bool = False


class TransactionStateHandler(EventHandler):
    """
    Tracks transaction state for all SIP methods.

    A transaction is identified by:
    - branch parameter in top Via header
    - CSeq header (method + sequence number)
    - Call-ID header

    According to RFC 3261 Section 17, a transaction consists of a request
    and all responses to that request (provisional and final).

    Key features:
    - Generates unique transaction keys
    - Tracks request and all responses
    - Marks transaction as completed when final response received
    - Stores transaction state in context metadata
    """

    def __init__(self):
        """Initialize transaction state handler."""
        self._transactions: dict[str, TransactionFlowState] = {}

    def _get_transaction_key(self, message) -> Optional[str]:
        """
        Generate unique transaction key from message.

        The key is composed of: Call-ID + branch + CSeq

        Args:
            message: Request or Response

        Returns:
            Transaction key or None if unable to generate
        """
        via = message.via
        cseq = message.cseq
        call_id = message.call_id

        if not all([via, cseq, call_id]):
            return None

        # Extract branch parameter from Via header
        branch = None
        if "branch=" in via:
            branch = via.split("branch=")[1].split(";")[0].split(">")[0]

        # Use branch if available (RFC 3261 compliant)
        if branch:
            return f"{call_id}:{branch}:{cseq}"
        else:
            # Fallback for non-RFC 3261 compliant implementations
            return f"{call_id}:{cseq}"

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Track outgoing request in transaction."""
        key = self._get_transaction_key(request)
        if key:
            # Create new transaction state
            if key not in self._transactions:
                self._transactions[key] = TransactionFlowState()

            state = self._transactions[key]
            state.request = request

            # Store in context
            context.metadata["transaction_key"] = key
            context.metadata["transaction_state"] = state
            context.transaction_id = key

            logger.debug(f"Transaction started: {key[:50]}...")

        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Track response in transaction."""
        key = self._get_transaction_key(response)
        if key and key in self._transactions:
            state = self._transactions[key]
            category = ResponseCategory.from_status_code(response.status_code)

            if category == ResponseCategory.PROVISIONAL:
                # Add provisional response to list
                state.provisional_responses.append(response)
                logger.debug(
                    f"Transaction {key[:50]}...: provisional {response.status_code}"
                )
            else:
                # Set final response and mark completed
                state.final_response = response
                state.completed = True
                logger.debug(
                    f"Transaction {key[:50]}...: "
                    f"final {response.status_code} (completed)"
                )

            # Update context
            context.metadata["transaction_key"] = key
            context.metadata["transaction_state"] = state
            context.transaction_id = key

        return response

    def get_state(self, transaction_key: str) -> Optional[TransactionFlowState]:
        """
        Get transaction state by key.

        Args:
            transaction_key: Transaction key

        Returns:
            TransactionFlowState or None
        """
        return self._transactions.get(transaction_key)

    def cleanup(self, transaction_key: str) -> None:
        """
        Clean up completed transaction.

        Args:
            transaction_key: Transaction key to clean up
        """
        if transaction_key in self._transactions:
            del self._transactions[transaction_key]
            logger.debug(f"Cleaned up transaction: {transaction_key[:50]}...")


class DialogStateHandler(EventHandler):
    """
    Tracks dialog state for session-based SIP methods.

    A dialog represents a peer-to-peer SIP relationship between two UAs,
    established by INVITE and terminated by BYE.

    Dialog is identified by (RFC 3261 Section 12):
    - Call-ID
    - Local tag (From tag for UAC, To tag for UAS)
    - Remote tag (To tag for UAC, From tag for UAS)

    Dialog states:
    - Early: After INVITE with provisional response containing To tag
    - Confirmed: After 200 OK to INVITE and ACK sent
    - Terminated: After BYE or error

    Key features:
    - Generates unique dialog IDs
    - Tracks dialog lifecycle (early -> confirmed -> terminated)
    - Detects dialog establishment from responses
    - Handles dialog termination
    - Optional callbacks for dialog events
    """

    def __init__(
        self,
        on_dialog_established: Optional[Callable[[str, EventContext], None]] = None,
        on_dialog_terminated: Optional[Callable[[str, EventContext], None]] = None,
    ):
        """
        Initialize dialog state handler.

        Args:
            on_dialog_established: Callback when dialog is confirmed
            on_dialog_terminated: Callback when dialog is terminated
        """
        self.on_dialog_established = on_dialog_established
        self.on_dialog_terminated = on_dialog_terminated
        self._dialogs: dict[str, dict] = {}  # dialog_id -> dialog_info

    def _get_dialog_id(self, message, is_uac: bool = True) -> Optional[str]:
        """
        Generate dialog ID from message.

        Args:
            message: Request or Response
            is_uac: True if we are UAC (caller), False if UAS (callee)

        Returns:
            Dialog ID or None if unable to generate
        """
        call_id = message.call_id
        from_tag = None
        to_tag = None

        # Extract tags from headers
        if message.from_header and "tag=" in message.from_header:
            from_tag = message.from_header.split("tag=")[1].split(";")[0].split(">")[0]

        if message.to_header and "tag=" in message.to_header:
            to_tag = message.to_header.split("tag=")[1].split(";")[0].split(">")[0]

        # Dialog requires Call-ID and both tags
        if not call_id or not from_tag or not to_tag:
            return None

        # Dialog ID format: call-id:local-tag:remote-tag
        if is_uac:
            return f"{call_id}:{from_tag}:{to_tag}"
        else:
            return f"{call_id}:{to_tag}:{from_tag}"

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Track dialog state from responses."""
        if not response.request:
            return response

        method = response.request.method
        category = ResponseCategory.from_status_code(response.status_code)

        # INVITE creates dialogs
        if method == "INVITE":
            dialog_id = self._get_dialog_id(response, is_uac=True)

            if dialog_id:
                # Early dialog (provisional with To tag)
                if category == ResponseCategory.PROVISIONAL:
                    if dialog_id not in self._dialogs:
                        self._dialogs[dialog_id] = {
                            "state": "early",
                            "method": method,
                            "call_id": response.call_id,
                        }
                        logger.info(f"📱 Early dialog established: {dialog_id[:40]}...")

                # Confirmed dialog (2xx response)
                elif category == ResponseCategory.SUCCESS:
                    if dialog_id not in self._dialogs:
                        self._dialogs[dialog_id] = {
                            "state": "confirmed",
                            "method": method,
                            "call_id": response.call_id,
                        }
                    else:
                        self._dialogs[dialog_id]["state"] = "confirmed"

                    logger.info(f"✅ Confirmed dialog: {dialog_id[:40]}...")

                    if self.on_dialog_established:
                        self.on_dialog_established(dialog_id, context)

                # Store dialog info in context
                context.metadata["dialog_id"] = dialog_id
                context.metadata["dialog_state"] = self._dialogs.get(dialog_id)
                context.dialog_id = dialog_id

        # BYE terminates dialogs
        elif method == "BYE":
            if category == ResponseCategory.SUCCESS:
                # Find and terminate dialog by Call-ID
                call_id = response.call_id
                terminated_dialogs = []

                for dialog_id, dialog_info in self._dialogs.items():
                    if dialog_info["call_id"] == call_id:
                        dialog_info["state"] = "terminated"
                        terminated_dialogs.append(dialog_id)
                        logger.info(f"📴 Dialog terminated: {dialog_id[:40]}...")

                        if self.on_dialog_terminated:
                            self.on_dialog_terminated(dialog_id, context)

                # Clean up terminated dialogs
                for dialog_id in terminated_dialogs:
                    del self._dialogs[dialog_id]

        return response

    def get_dialog(self, dialog_id: str) -> Optional[dict]:
        """
        Get dialog information by ID.

        Args:
            dialog_id: Dialog ID

        Returns:
            Dialog info dict or None
        """
        return self._dialogs.get(dialog_id)

    def get_dialogs_by_call_id(self, call_id: str) -> list[dict]:
        """
        Get all dialogs for a specific Call-ID.

        Args:
            call_id: Call-ID to search for

        Returns:
            List of dialog info dicts
        """
        return [
            {"id": did, **dinfo}
            for did, dinfo in self._dialogs.items()
            if dinfo.get("call_id") == call_id
        ]

    def cleanup(self, dialog_id: str) -> None:
        """
        Clean up terminated dialog.

        Args:
            dialog_id: Dialog ID to clean up
        """
        if dialog_id in self._dialogs:
            del self._dialogs[dialog_id]
            logger.debug(f"Cleaned up dialog: {dialog_id[:40]}...")

