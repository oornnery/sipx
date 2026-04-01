#!/usr/bin/env python3
"""
sipx — Dialog & Transaction FSM

Shows how the state machine tracks transactions and dialogs:
- Transaction lifecycle: CALLING -> PROCEEDING -> COMPLETED -> TERMINATED
- Dialog lifecycle: EARLY -> CONFIRMED -> TERMINATED
- Timer management for retransmissions

No network required — exercises the FSM in-memory.
"""

from sipx import Request, Response
from sipx.fsm import StateManager
from sipx._types import DialogState
from sipx._utils import console


def main():
    console.print("[bold]sipx — FSM: Transactions + Dialogs[/bold]\n")
    sm = StateManager()

    # --- 1. INVITE Transaction (ICT) ---
    console.print("[bold]1. INVITE Client Transaction (ICT)[/bold]")

    invite = Request(
        "INVITE",
        "sip:bob@example.com",
        headers={"Via": "SIP/2.0/UDP x;branch=z9hG4bKinvite1"},
    )
    txn = sm.create_transaction(invite)
    console.print(f"  Created: {txn.id[:8]}... state={txn.state.name}")

    # Simulate 100 Trying
    sm.update_transaction(txn.id, Response(100, reason_phrase="Trying"))
    console.print(f"  After 100: state={txn.state.name}")

    # Simulate 180 Ringing
    sm.update_transaction(txn.id, Response(180, reason_phrase="Ringing"))
    console.print(f"  After 180: state={txn.state.name}")

    # Simulate 200 OK
    sm.update_transaction(txn.id, Response(200, reason_phrase="OK"))
    console.print(f"  After 200: state={txn.state.name}")
    console.print(f"  Complete: {txn.is_complete()}")

    # --- 2. Non-INVITE Transaction (NICT) ---
    console.print("\n[bold]2. Non-INVITE Transaction (REGISTER)[/bold]")

    register = Request(
        "REGISTER",
        "sip:registrar.example.com",
        headers={"Via": "SIP/2.0/UDP x;branch=z9hG4bKreg1"},
    )
    txn2 = sm.create_transaction(register)
    console.print(f"  Created: {txn2.id[:8]}... type={txn2.transaction_type.name}")

    sm.update_transaction(txn2.id, Response(401, reason_phrase="Unauthorized"))
    console.print(f"  After 401: state={txn2.state.name}")

    # --- 3. Dialog ---
    console.print("\n[bold]3. Dialog Lifecycle[/bold]")

    dialog = sm.create_dialog(
        call_id="abc123@host",
        local_tag="tag-alice",
        remote_tag="tag-bob",
        local_uri="sip:alice@example.com",
        remote_uri="sip:bob@example.com",
        remote_target="sip:bob@10.0.0.2",
    )
    console.print(f"  Created: state={dialog.state.name}")
    console.print(f"  Dialog ID: {dialog.get_dialog_id()}")

    dialog.transition_to(DialogState.CONFIRMED)
    console.print(f"  After 200 OK: state={dialog.state.name}")

    dialog.transition_to(DialogState.TERMINATED)
    console.print(f"  After BYE: state={dialog.state.name}")

    # --- 4. State Manager stats ---
    console.print("\n[bold]4. State Manager[/bold]")
    console.print(f"  Active transactions: {len(sm._transactions)}")
    console.print(f"  Active dialogs: {len(sm._dialogs)}")

    # Cleanup
    expired = sm.cleanup_transactions(max_age=0)
    console.print(f"  Cleaned up: {expired} expired transactions")

    console.print("\n[bold green]FSM demo complete.[/bold green]")


if __name__ == "__main__":
    main()
