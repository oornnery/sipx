"""Typed exception hierarchy for SIP errors."""

from __future__ import annotations


class SipError(Exception):
    """Base exception for all SIP-related errors."""

    def __init__(
        self,
        message: str,
        *,
        details: dict | None = None,
        rfc_ref: str | None = None,
    ) -> None:
        """Initialize SipError.

        Args:
            message: Human-readable error description.
            details: Optional structured data about the error.
            rfc_ref: Optional RFC reference (e.g. ``RFC 3261 §17``).
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.rfc_ref = rfc_ref


class TransportError(SipError):
    """Network or transport failure."""


class TimeoutError(SipError):
    """Transaction or operation timeout."""


class ProtocolError(SipError):
    """Malformed SIP message or protocol violation."""


class AuthError(SipError):
    """Authentication or authorization failure."""


class DialogError(SipError):
    """Dialog state violation."""


class TransactionError(SipError):
    """Transaction state violation."""
