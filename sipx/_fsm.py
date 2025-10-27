"""
Finite State Machines (FSM) for SIP transactions and dialogs.

This module implements the four SIP FSMs defined in RFC 3261:
- ICT (Invite Client Transaction)
- NICT (Non-Invite Client Transaction)
- IST (Invite Server Transaction) - future
- NIST (Non-Invite Server Transaction) - future

FSM Overview:
=============

ICT (INVITE Client):
  CALLING → PROCEEDING → COMPLETED → TERMINATED
           ↓
         CONFIRMED (on 2xx)

NICT (Non-INVITE Client):
  TRYING → PROCEEDING → COMPLETED → TERMINATED

Transactions provide reliability through retransmissions and state tracking.
Dialogs represent persistent peer-to-peer SIP relationships across transactions.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

# Import types from centralized _types module
from ._types import (
    DialogState,
    TransactionState,
    TransactionType,
)

if TYPE_CHECKING:
    from ._models._message import Request, Response


@dataclass
class Transaction:
    """
    Represents a SIP transaction.

    A transaction is a request sent by a client and the responses received.
    Transactions provide reliability and ordering for SIP messages.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    branch: str = ""  # Via branch parameter (transaction ID)

    # Type and state
    transaction_type: TransactionType = TransactionType.NON_INVITE
    state: TransactionState = TransactionState.CALLING

    # Messages
    request: Optional[Request] = None
    responses: List[Response] = field(default_factory=list)

    # Timing
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Timers (in seconds)
    timer_a: Optional[float] = None  # Retransmit timer (INVITE)
    timer_b: Optional[float] = None  # Transaction timeout (INVITE)
    timer_d: Optional[float] = None  # Wait time for response retransmissions
    timer_e: Optional[float] = None  # Retransmit timer (non-INVITE)
    timer_f: Optional[float] = None  # Transaction timeout (non-INVITE)
    timer_k: Optional[float] = (
        None  # Wait time for response retransmissions (non-INVITE)
    )

    # Metadata
    dialog_id: Optional[str] = None  # Associated dialog
    metadata: Dict[str, any] = field(default_factory=dict)

    def transition_to(self, new_state: TransactionState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The new state
        """
        old_state = self.state
        self.state = new_state
        self.updated_at = time.time()

        # Trigger state-specific actions
        self._on_state_change(old_state, new_state)

    def _on_state_change(
        self, old_state: TransactionState, new_state: TransactionState
    ) -> None:
        """
        Handle state change side effects.

        Args:
            old_state: Previous state
            new_state: New state
        """
        # Set timers based on transaction type and state
        if self.transaction_type == TransactionType.INVITE:
            if new_state == TransactionState.CALLING:
                self.timer_a = 0.5  # T1 (500ms)
                self.timer_b = 32.0  # 64*T1
            elif new_state == TransactionState.COMPLETED:
                self.timer_d = 32.0  # > 32s for UDP
        else:  # NON_INVITE
            if new_state == TransactionState.TRYING:
                self.timer_e = 0.5  # T1
                self.timer_f = 32.0  # 64*T1
            elif new_state == TransactionState.COMPLETED:
                self.timer_k = 5.0  # T4

    def add_response(self, response: Response) -> None:
        """
        Add a response to this transaction.

        Args:
            response: The SIP response
        """
        self.responses.append(response)
        self.updated_at = time.time()

        # Update state based on response
        if response.is_provisional:
            if self.transaction_type == TransactionType.INVITE:
                if self.state == TransactionState.CALLING:
                    self.transition_to(TransactionState.TRYING)
                elif self.state == TransactionState.TRYING:
                    self.transition_to(TransactionState.PROCEEDING)
        elif response.is_final:
            self.transition_to(TransactionState.COMPLETED)

    def is_complete(self) -> bool:
        """Check if transaction is complete."""
        return self.state in (
            TransactionState.COMPLETED,
            TransactionState.CONFIRMED,
            TransactionState.TERMINATED,
        )

    def is_terminated(self) -> bool:
        """Check if transaction is terminated."""
        return self.state == TransactionState.TERMINATED

    def get_final_response(self) -> Optional[Response]:
        """Get the final response (2xx-6xx) if any."""
        for response in reversed(self.responses):
            if response.is_final:
                return response
        return None

    @property
    def transactions(self) -> Dict[str, Transaction]:
        """Get all transactions."""
        return self._transactions

    @property
    def dialogs(self) -> Dict[str, Dialog]:
        """Get all dialogs."""
        return self._dialogs

    def __repr__(self) -> str:
        method = self.request.method if self.request else "?"
        return f"<Transaction({method}, {self.state.name}, {len(self.responses)} responses)>"


@dataclass
class Dialog:
    """
    Represents a SIP dialog.

    A dialog is a peer-to-peer SIP relationship between two UAs that persists
    for some time. Dialogs are identified by Call-ID, local tag, and remote tag.
    """

    # Identity (RFC 3261 Section 12)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    call_id: str = ""
    local_tag: str = ""
    remote_tag: str = ""

    # State
    state: DialogState = DialogState.EARLY

    # Route information
    local_uri: str = ""
    remote_uri: str = ""
    remote_target: str = ""  # Contact URI
    route_set: List[str] = field(default_factory=list)

    # Sequence numbers
    local_seq: int = 1
    remote_seq: int = 0

    # Timing
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Associated transactions
    transactions: List[str] = field(default_factory=list)  # Transaction IDs

    # Metadata
    metadata: Dict[str, any] = field(default_factory=dict)

    def transition_to(self, new_state: DialogState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The new state
        """
        self.state = new_state
        self.updated_at = time.time()

    def get_dialog_id(self) -> str:
        """
        Get the dialog identifier.

        Format: call_id:local_tag:remote_tag

        Returns:
            Dialog identifier string
        """
        return f"{self.call_id}:{self.local_tag}:{self.remote_tag}"

    def increment_local_seq(self) -> int:
        """
        Increment and return local sequence number.

        Returns:
            New local sequence number
        """
        self.local_seq += 1
        self.updated_at = time.time()
        return self.local_seq

    def update_remote_seq(self, seq: int) -> None:
        """
        Update remote sequence number.

        Args:
            seq: New remote sequence number
        """
        if seq > self.remote_seq:
            self.remote_seq = seq
            self.updated_at = time.time()

    def is_confirmed(self) -> bool:
        """Check if dialog is confirmed."""
        return self.state == DialogState.CONFIRMED

    def is_terminated(self) -> bool:
        """Check if dialog is terminated."""
        return self.state == DialogState.TERMINATED

    def add_transaction(self, transaction_id: str) -> None:
        """
        Add a transaction to this dialog.

        Args:
            transaction_id: Transaction ID
        """
        if transaction_id not in self.transactions:
            self.transactions.append(transaction_id)
            self.updated_at = time.time()

    def __repr__(self) -> str:
        return f"<Dialog({self.state.name}, {self.call_id[:8]}..., {len(self.transactions)} txns)>"


class StateManager:
    """
    Manages SIP transactions and dialogs.

    This is the central state machine that tracks all active transactions
    and dialogs for a SIP client or server.
    """

    def __init__(self) -> None:
        """Initialize state manager."""
        self._transactions: Dict[str, Transaction] = {}
        self._dialogs: Dict[str, Dialog] = {}

        # Event handlers
        self._transaction_handlers: Dict[TransactionState, List[Callable]] = {}
        self._dialog_handlers: Dict[DialogState, List[Callable]] = {}

    # Transaction management

    def create_transaction(
        self,
        request: Request,
        transaction_type: Optional[TransactionType] = None,
    ) -> Transaction:
        """
        Create a new transaction.

        Args:
            request: The SIP request
            transaction_type: Type of transaction (auto-detected if None)

        Returns:
            New transaction object
        """
        # Auto-detect transaction type
        if transaction_type is None:
            transaction_type = (
                TransactionType.INVITE
                if request.method == "INVITE"
                else TransactionType.NON_INVITE
            )

        # Extract branch from Via header
        branch = self._extract_branch(request)

        # Create transaction
        transaction = Transaction(
            branch=branch,
            transaction_type=transaction_type,
            request=request,
        )

        # Store transaction
        self._transactions[transaction.id] = transaction

        return transaction

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """
        Get transaction by ID.

        Args:
            transaction_id: Transaction ID

        Returns:
            Transaction or None
        """
        return self._transactions.get(transaction_id)

    def find_transaction(
        self,
        branch: Optional[str] = None,
        call_id: Optional[str] = None,
        method: Optional[str] = None,
    ) -> Optional[Transaction]:
        """
        Find transaction by criteria.

        Args:
            branch: Via branch parameter
            call_id: Call-ID header
            method: SIP method

        Returns:
            First matching transaction or None
        """
        for txn in self._transactions.values():
            if branch and txn.branch != branch:
                continue
            if (
                call_id
                and txn.request
                and txn.request.headers.get("Call-ID") != call_id
            ):
                continue
            if method and txn.request and txn.request.method != method:
                continue
            return txn
        return None

    def update_transaction(self, transaction_id: str, response: Response) -> None:
        """
        Update transaction with a response.

        Args:
            transaction_id: Transaction ID
            response: SIP response
        """
        transaction = self.get_transaction(transaction_id)
        if transaction:
            transaction.add_response(response)

            # Trigger handlers
            self._trigger_transaction_handlers(transaction)

    def remove_transaction(self, transaction_id: str) -> None:
        """
        Remove a transaction.

        Args:
            transaction_id: Transaction ID
        """
        if transaction_id in self._transactions:
            del self._transactions[transaction_id]

    def cleanup_transactions(self, max_age: float = 300.0) -> int:
        """
        Clean up old transactions.

        Args:
            max_age: Maximum age in seconds (default: 5 minutes)

        Returns:
            Number of transactions removed
        """
        now = time.time()
        to_remove = []

        for txn_id, txn in self._transactions.items():
            if txn.is_terminated() or (now - txn.updated_at) > max_age:
                to_remove.append(txn_id)

        for txn_id in to_remove:
            del self._transactions[txn_id]

        return len(to_remove)

    # Dialog management

    def create_dialog(
        self,
        call_id: str,
        local_tag: str,
        remote_tag: str,
        local_uri: str,
        remote_uri: str,
        remote_target: str,
    ) -> Dialog:
        """
        Create a new dialog.

        Args:
            call_id: Call-ID
            local_tag: Local tag
            remote_tag: Remote tag
            local_uri: Local URI (From/To)
            remote_uri: Remote URI (To/From)
            remote_target: Remote target URI (Contact)

        Returns:
            New dialog object
        """
        dialog = Dialog(
            call_id=call_id,
            local_tag=local_tag,
            remote_tag=remote_tag,
            local_uri=local_uri,
            remote_uri=remote_uri,
            remote_target=remote_target,
        )

        # Store dialog
        dialog_key = dialog.get_dialog_id()
        self._dialogs[dialog_key] = dialog

        return dialog

    def get_dialog(self, dialog_id: str) -> Optional[Dialog]:
        """
        Get dialog by ID.

        Args:
            dialog_id: Dialog ID (call_id:local_tag:remote_tag)

        Returns:
            Dialog or None
        """
        return self._dialogs.get(dialog_id)

    def find_dialog(
        self,
        call_id: str,
        local_tag: Optional[str] = None,
        remote_tag: Optional[str] = None,
    ) -> Optional[Dialog]:
        """
        Find dialog by Call-ID and tags.

        Args:
            call_id: Call-ID
            local_tag: Local tag (optional)
            remote_tag: Remote tag (optional)

        Returns:
            First matching dialog or None
        """
        for dialog in self._dialogs.values():
            if dialog.call_id != call_id:
                continue
            if local_tag and dialog.local_tag != local_tag:
                continue
            if remote_tag and dialog.remote_tag != remote_tag:
                continue
            return dialog
        return None

    def update_dialog(self, dialog_id: str, **kwargs) -> None:
        """
        Update dialog fields.

        Args:
            dialog_id: Dialog ID
            **kwargs: Fields to update
        """
        dialog = self.get_dialog(dialog_id)
        if dialog:
            for key, value in kwargs.items():
                if hasattr(dialog, key):
                    setattr(dialog, key, value)
            dialog.updated_at = time.time()

            # Trigger handlers
            self._trigger_dialog_handlers(dialog)

    def remove_dialog(self, dialog_id: str) -> None:
        """
        Remove a dialog.

        Args:
            dialog_id: Dialog ID
        """
        if dialog_id in self._dialogs:
            del self._dialogs[dialog_id]

    def cleanup_dialogs(self, max_age: float = 3600.0) -> int:
        """
        Clean up old dialogs.

        Args:
            max_age: Maximum age in seconds (default: 1 hour)

        Returns:
            Number of dialogs removed
        """
        now = time.time()
        to_remove = []

        for dlg_id, dlg in self._dialogs.items():
            if dlg.is_terminated() or (now - dlg.updated_at) > max_age:
                to_remove.append(dlg_id)

        for dlg_id in to_remove:
            del self._dialogs[dlg_id]

        return len(to_remove)

    # Event handlers

    def on_transaction_state(
        self,
        state: TransactionState,
        handler: Callable[[Transaction], None],
    ) -> None:
        """
        Register a handler for transaction state changes.

        Args:
            state: Transaction state to watch
            handler: Callback function
        """
        if state not in self._transaction_handlers:
            self._transaction_handlers[state] = []
        self._transaction_handlers[state].append(handler)

    def on_dialog_state(
        self,
        state: DialogState,
        handler: Callable[[Dialog], None],
    ) -> None:
        """
        Register a handler for dialog state changes.

        Args:
            state: Dialog state to watch
            handler: Callback function
        """
        if state not in self._dialog_handlers:
            self._dialog_handlers[state] = []
        self._dialog_handlers[state].append(handler)

    def _trigger_transaction_handlers(self, transaction: Transaction) -> None:
        """Trigger handlers for transaction state."""
        handlers = self._transaction_handlers.get(transaction.state, [])
        for handler in handlers:
            try:
                handler(transaction)
            except Exception:
                pass  # Ignore handler errors

    def _trigger_dialog_handlers(self, dialog: Dialog) -> None:
        """Trigger handlers for dialog state."""
        handlers = self._dialog_handlers.get(dialog.state, [])
        for handler in handlers:
            try:
                handler(dialog)
            except Exception:
                pass  # Ignore handler errors

    # Utility methods

    def _extract_branch(self, request: Request) -> str:
        """
        Extract branch parameter from Via header.

        Args:
            request: SIP request

        Returns:
            Branch parameter or empty string
        """
        via = request.headers.get("Via", "")
        if isinstance(via, bytes):
            via = via.decode("utf-8", errors="ignore")

        # Simple extraction - real implementation should properly parse Via
        if ";branch=" in via:
            branch = via.split(";branch=")[1].split(";")[0]
            return branch

        return ""

    def get_statistics(self) -> dict:
        """
        Get statistics about transactions and dialogs.

        Returns:
            Dictionary with statistics
        """
        return {
            "transactions": {
                "total": len(self._transactions),
                "by_state": self._count_by_state(
                    self._transactions.values(), lambda t: t.state
                ),
                "by_type": self._count_by_state(
                    self._transactions.values(), lambda t: t.transaction_type
                ),
            },
            "dialogs": {
                "total": len(self._dialogs),
                "by_state": self._count_by_state(
                    self._dialogs.values(), lambda d: d.state
                ),
            },
        }

    def _count_by_state(self, items, key_func) -> dict:
        """Count items by state using a key function."""
        counts = {}
        for item in items:
            key = key_func(item)
            counts[key.name if hasattr(key, "name") else str(key)] = (
                counts.get(key.name if hasattr(key, "name") else str(key), 0) + 1
            )
        return counts

    def __repr__(self) -> str:
        return (
            f"<StateManager("
            f"{len(self._transactions)} transactions, "
            f"{len(self._dialogs)} dialogs)>"
        )
