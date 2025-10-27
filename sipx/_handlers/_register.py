"""
REGISTER flow handler for managing SIP registration.

This module handles the REGISTER transaction flow including registration,
re-registration, unregistration, and contact/expires tracking.
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
class RegisterFlowState:
    """
    State tracking for REGISTER transaction flow.

    Tracks registration attempts, expiration times, registered contacts,
    and registration status.
    """

    registration_attempts: int = 0
    last_expires: Optional[int] = None
    registered: bool = False
    contacts: list[str] = field(default_factory=list)


class RegisterFlowHandler(EventHandler):
    """
    Handles REGISTER transaction flows according to RFC 3261 Section 10.

    REGISTER flow:
    1. Client sends REGISTER with Contact and Expires headers
    2. Server may respond with 401/407 (authentication required)
    3. Client resends REGISTER with Authorization
    4. Server responds with 200 OK containing registered contacts
    5. Client can re-register before expiration or unregister (Expires: 0)

    Key features:
    - Tracks registration attempts and status
    - Extracts registered contacts from responses
    - Extracts and tracks expiration times
    - Detects unregistration (Expires: 0)
    - Optional callbacks for registration events
    - Foundation for auto-reregistration (to be implemented)
    """

    def __init__(
        self,
        auto_reregister: bool = False,
        reregister_margin: int = 60,
        on_registered: Optional[Callable[[Response, EventContext], None]] = None,
        on_unregistered: Optional[Callable[[Response, EventContext], None]] = None,
        on_registration_failed: Optional[
            Callable[[Response, EventContext], None]
        ] = None,
    ):
        """
        Initialize REGISTER flow handler.

        Args:
            auto_reregister: If True, automatically re-register before expiration (TODO)
            reregister_margin: Seconds before expiration to re-register (default: 60)
            on_registered: Callback when registration succeeds
            on_unregistered: Callback when unregistration succeeds
            on_registration_failed: Callback when registration fails
        """
        self.auto_reregister = auto_reregister
        self.reregister_margin = reregister_margin
        self.on_registered = on_registered
        self.on_unregistered = on_unregistered
        self.on_registration_failed = on_registration_failed
        self._register_states: dict[str, RegisterFlowState] = {}

    def on_request(self, request: Request, context: EventContext) -> Request:
        """Track REGISTER requests and initialize state."""
        if request.method == "REGISTER":
            # Use To header (AOR) as key
            aor = request.to_header
            if aor:
                # Get or create state for this AOR
                if aor not in self._register_states:
                    self._register_states[aor] = RegisterFlowState()

                state = self._register_states[aor]
                state.registration_attempts += 1

                # Check if this is unregistration (Expires: 0)
                expires = request.headers.get("Expires")
                if expires == "0":
                    logger.info("📤 Unregistration request")
                    context.metadata["is_unregister"] = True
                else:
                    logger.info(
                        f"📤 Registration request (attempt {state.registration_attempts})"
                    )
                    context.metadata["is_register"] = True
                    if expires:
                        try:
                            state.last_expires = int(expires)
                        except ValueError:
                            logger.warning(f"Invalid Expires value: {expires}")

                context.metadata["register_flow_state"] = state

        return request

    def on_response(self, response: Response, context: EventContext) -> Response:
        """Handle responses to REGISTER requests."""
        # Only process responses to REGISTER
        if not response.request or response.request.method != "REGISTER":
            return response

        aor = response.to_header
        if not aor or aor not in self._register_states:
            return response

        state = self._register_states[aor]
        category = ResponseCategory.from_status_code(response.status_code)

        # Handle success responses (2xx)
        if category == ResponseCategory.SUCCESS:
            is_unregister = context.metadata.get("is_unregister", False)

            if is_unregister:
                # Unregistration succeeded
                logger.info("✅ Unregistration successful")
                state.registered = False
                state.contacts = []

                if self.on_unregistered:
                    self.on_unregistered(response, context)

            else:
                # Registration succeeded
                logger.info("✅ Registration successful")
                state.registered = True

                # Extract registered contacts from response
                contact_header = response.headers.get("Contact")
                if contact_header:
                    # Simple parsing - can be enhanced for multiple contacts
                    state.contacts = [contact_header]

                # Extract expires value from response
                expires_header = response.headers.get("Expires")
                if expires_header:
                    try:
                        state.last_expires = int(expires_header)
                        logger.debug(f"Registration expires in {state.last_expires}s")
                    except ValueError:
                        logger.warning(f"Invalid Expires in response: {expires_header}")

                if self.on_registered:
                    self.on_registered(response, context)

                # TODO: Schedule re-registration if auto_reregister is True
                # Calculate reregister time: expires - margin
                # Set up timer/callback for re-registration

        # Handle final error responses (non-2xx, non-1xx)
        elif category != ResponseCategory.PROVISIONAL:
            logger.error(
                f"❌ Registration failed: {response.status_code} {response.reason_phrase}"
            )

            if self.on_registration_failed:
                self.on_registration_failed(response, context)

        # Update context with current state
        context.metadata["register_flow_state"] = state

        return response

    def get_state(self, aor: str) -> Optional[RegisterFlowState]:
        """
        Get the registration state for a specific Address of Record.

        Args:
            aor: Address of Record (To header value)

        Returns:
            RegisterFlowState or None if not found
        """
        return self._register_states.get(aor)

    def is_registered(self, aor: str) -> bool:
        """
        Check if an Address of Record is currently registered.

        Args:
            aor: Address of Record to check

        Returns:
            True if registered, False otherwise
        """
        state = self._register_states.get(aor)
        return state.registered if state else False

    def get_contacts(self, aor: str) -> list[str]:
        """
        Get registered contacts for an Address of Record.

        Args:
            aor: Address of Record

        Returns:
            List of registered contact URIs
        """
        state = self._register_states.get(aor)
        return state.contacts if state else []

    def cleanup(self, aor: str) -> None:
        """
        Clean up state for a specific Address of Record.

        Args:
            aor: Address of Record to clean up
        """
        if aor in self._register_states:
            del self._register_states[aor]
            logger.debug(f"Cleaned up REGISTER state for AOR: {aor}")
