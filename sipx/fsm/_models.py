"""Transaction and Dialog dataclasses for SIP FSM."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .._types import (
    DialogState,
    TransactionState,
    TransactionType,
)
from .._utils import logger

_log = logger.getChild("fsm")

if TYPE_CHECKING:
    from ..models._message import Request, Response
    from ._timer import TimerManager


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

    # Timers (in seconds) - Client-side (ICT/NICT)
    timer_a: Optional[float] = None  # Retransmit timer (INVITE)
    timer_b: Optional[float] = None  # Transaction timeout (INVITE)
    timer_d: Optional[float] = None  # Wait time for response retransmissions
    timer_e: Optional[float] = None  # Retransmit timer (non-INVITE)
    timer_f: Optional[float] = None  # Transaction timeout (non-INVITE)
    timer_k: Optional[float] = (
        None  # Wait time for response retransmissions (non-INVITE)
    )

    # Timers (in seconds) - Server-side (IST/NIST)
    timer_g: Optional[float] = None  # Retransmit response (IST)
    timer_h: Optional[float] = None  # Transaction timeout (IST)
    timer_i: Optional[float] = None  # Wait for ACK retransmissions (IST)
    timer_j: Optional[float] = None  # Wait for retransmissions (NIST)

    # Transport type for timer calculation ("UDP" vs reliable)
    transport: str = "UDP"

    # Active timer manager (not serialized, set externally)
    timer_manager: Optional[TimerManager] = field(default=None, repr=False)

    # Retransmit callback (set by Client to re-send the request)
    _retransmit_fn: Optional[Callable[[], None]] = field(default=None, repr=False)

    # Metadata
    dialog_id: Optional[str] = None  # Associated dialog
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: TransactionState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The new state
        """
        old_state = self.state
        self.state = new_state
        self.updated_at = time.time()
        _log.debug(
            "Transaction %s: %s -> %s", self.id[:8], old_state.name, new_state.name
        )

        # Trigger state-specific actions
        self._on_state_change(old_state, new_state)

    def _on_state_change(
        self, old_state: TransactionState, new_state: TransactionState
    ) -> None:
        """
        Handle state change side effects.

        Sets timer values and schedules active timers (via TimerManager)
        based on transaction type and new state per RFC 3261 Sections 17.1/17.2.

        Args:
            old_state: Previous state
            new_state: New state
        """
        is_reliable = self.transport.upper() in ("TCP", "TLS")

        # --- Client-side transactions ---
        if self.transaction_type == TransactionType.INVITE:
            if new_state == TransactionState.CALLING:
                self.timer_a = 0.5  # T1 (500ms)
                self.timer_b = 32.0  # 64*T1
                if not is_reliable and self._retransmit_fn:
                    self._schedule_timer("Timer A", self.timer_a, self._on_timer_a)
                self._schedule_timer("Timer B", self.timer_b, self._on_timer_expired)
            elif new_state == TransactionState.PROCEEDING:
                # Stop retransmissions, keep timeout
                self._cancel_active_timers("Timer A")
            elif new_state == TransactionState.COMPLETED:
                self._cancel_active_timers("Timer A", "Timer B")
                self.timer_d = 32.0  # > 32s for UDP
                self._schedule_timer("Timer D", self.timer_d, self._on_timer_expired)
            elif new_state == TransactionState.TERMINATED:
                self._cancel_all_timers()

        elif self.transaction_type == TransactionType.NON_INVITE:
            if new_state == TransactionState.TRYING:
                self.timer_e = 0.5  # T1
                self.timer_f = 32.0  # 64*T1
                if not is_reliable and self._retransmit_fn:
                    self._schedule_timer("Timer E", self.timer_e, self._on_timer_e)
                self._schedule_timer("Timer F", self.timer_f, self._on_timer_expired)
            elif new_state == TransactionState.PROCEEDING:
                # Stop retransmissions, keep timeout
                self._cancel_active_timers("Timer E")
            elif new_state == TransactionState.COMPLETED:
                self._cancel_active_timers("Timer E", "Timer F")
                self.timer_k = 5.0  # T4
                self._schedule_timer("Timer K", self.timer_k, self._on_timer_expired)
            elif new_state == TransactionState.TERMINATED:
                self._cancel_all_timers()

        # --- Server-side: IST (INVITE Server Transaction, RFC 3261 17.2.1) ---
        elif self.transaction_type == TransactionType.INVITE_SERVER:
            if new_state == TransactionState.PROCEEDING:
                if not is_reliable:
                    self.timer_g = 0.5  # T1 (500ms) - retransmit response
                self.timer_h = 32.0  # 64*T1 - timeout waiting for ACK
                self._schedule_ist_timers()
            elif new_state == TransactionState.COMPLETED:
                self._cancel_active_timers("Timer G", "Timer H")
                self.timer_i = 0.0 if is_reliable else 5.0  # T4 for UDP
                self._schedule_timer("Timer I", self.timer_i, self._on_timer_expired)
            elif new_state == TransactionState.CONFIRMED:
                self._cancel_active_timers("Timer I")
                self.transition_to(TransactionState.TERMINATED)
            elif new_state == TransactionState.TERMINATED:
                self._cancel_all_timers()

        # --- Server-side: NIST (Non-Invite Server Transaction, RFC 3261 17.2.2) ---
        elif self.transaction_type == TransactionType.NON_INVITE_SERVER:
            if new_state == TransactionState.COMPLETED:
                self.timer_j = 0.0 if is_reliable else 32.0  # 64*T1 for UDP
                self._schedule_timer("Timer J", self.timer_j, self._on_timer_expired)
            elif new_state == TransactionState.TERMINATED:
                self._cancel_all_timers()

    # --- Timer scheduling helpers ---

    def _schedule_timer(
        self, name: str, delay: float, callback: Callable[[], None]
    ) -> None:
        """Schedule a single timer via the TimerManager, if available."""
        if self.timer_manager is not None and delay > 0:
            self.timer_manager.start_timer(name, delay, callback)
        elif self.timer_manager is not None and delay == 0:
            # Zero delay means immediate transition
            callback()

    def _cancel_active_timers(self, *names: str) -> None:
        """Cancel specific active timers."""
        if self.timer_manager is not None:
            for name in names:
                self.timer_manager.cancel_timer(name)

    def _cancel_all_timers(self) -> None:
        """Cancel all active timers for this transaction."""
        if self.timer_manager is not None:
            self.timer_manager.cancel_all()

    def _schedule_ist_timers(self) -> None:
        """Schedule IST timers G and H when entering PROCEEDING."""
        if self.timer_g is not None:
            self._schedule_timer("Timer G", self.timer_g, self._on_timer_g)
        if self.timer_h is not None:
            self._schedule_timer("Timer H", self.timer_h, self._on_timer_expired)

    def _on_timer_a(self) -> None:
        """Timer A fired (ICT): retransmit INVITE and double the interval."""
        if self.state != TransactionState.CALLING:
            return
        if self._retransmit_fn:
            self._retransmit_fn()
        # Double timer A up to T2 (4s)
        if self.timer_a is not None:
            self.timer_a = min(self.timer_a * 2, 4.0)
            self._schedule_timer("Timer A", self.timer_a, self._on_timer_a)

    def _on_timer_e(self) -> None:
        """Timer E fired (NICT): retransmit request and double the interval."""
        if self.state not in (TransactionState.TRYING, TransactionState.PROCEEDING):
            return
        if self._retransmit_fn:
            self._retransmit_fn()
        # Double timer E up to T2 (4s)
        if self.timer_e is not None:
            self.timer_e = min(self.timer_e * 2, 4.0)
            self._schedule_timer("Timer E", self.timer_e, self._on_timer_e)

    def _on_timer_g(self) -> None:
        """Timer G fired: retransmit last response and double the interval."""
        if self.state != TransactionState.PROCEEDING:
            return
        # Double timer G up to T2 (4s)
        if self.timer_g is not None:
            self.timer_g = min(self.timer_g * 2, 4.0)
            self._schedule_timer("Timer G", self.timer_g, self._on_timer_g)

    def _on_timer_expired(self) -> None:
        """Generic timer expiry: transition to TERMINATED."""
        if self.state != TransactionState.TERMINATED:
            self.transition_to(TransactionState.TERMINATED)

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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: DialogState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The new state
        """
        self.state = new_state
        self.updated_at = time.time()
        _log.debug(
            "Dialog %s: state -> %s",
            self.call_id[:8] if self.call_id else "?",
            new_state.name,
        )

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
