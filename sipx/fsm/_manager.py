"""State manager for SIP transactions and dialogs."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from .._types import (
    DialogState,
    TransactionState,
    TransactionType,
)
from ._models import Dialog, Transaction

if TYPE_CHECKING:
    from ..models._message import Request, Response


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

        # Determine initial state based on transaction type
        if transaction_type == TransactionType.INVITE_SERVER:
            initial_state = TransactionState.PROCEEDING
        elif transaction_type == TransactionType.NON_INVITE_SERVER:
            initial_state = TransactionState.TRYING
        elif transaction_type == TransactionType.INVITE:
            initial_state = TransactionState.CALLING
        else:
            initial_state = TransactionState.TRYING

        # Create transaction
        transaction = Transaction(
            branch=branch,
            transaction_type=transaction_type,
            state=initial_state,
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

        if not via:
            return ""

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
