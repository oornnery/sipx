"""Runtime SIP protocol layer used by the AsyncClient.

Contains the pieces the client drives at runtime: the Digest authentication
flow, dialog tracking, transaction state machines, and event hooks. Built on
``sipx.models`` and consumed by ``sipx.client``.

References:
    RFC 3261 §12 - Dialogs
    RFC 3261 §17 - Transactions
    RFC 3261 §22 - Usage of HTTP Authentication
"""

from sipx.protocol.auth import AuthFlow, DigestChallenge
from sipx.protocol.dialog import Dialog, DialogId, DialogState
from sipx.protocol.hooks import EventHooks
from sipx.protocol.transaction import ClientTransaction, ServerTransaction

__all__ = [
    "AuthFlow",
    "ClientTransaction",
    "DigestChallenge",
    "Dialog",
    "DialogId",
    "DialogState",
    "EventHooks",
    "ServerTransaction",
]
