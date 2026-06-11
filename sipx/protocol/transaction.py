"""Transaction state machines per RFC 3261 §17.

This module implements client and server transaction state machines for both
INVITE and non-INVITE transactions. The implementation is sans-I/O: timers
are tracked as state but do not fire automatically. Callers must invoke
`timer_fire()` when timers expire.

State transitions follow RFC 3261 §17 with updates from RFC 6026.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sipx.exceptions import TransactionError
from sipx.models import Request, Response


# Timer constants (seconds). Based on T1=500ms, T2=4s, T4=5s per RFC 3261 §17.1.1.2.
T1 = 0.5
T2 = 4.0
T4 = 5.0
TIMER_B = 64 * T1  # 32s - INVITE client timeout
TIMER_D_UNRELIABLE = 32.0  # Wait in Completed (unreliable transport)
TIMER_D_RELIABLE = 0.0  # Wait in Completed (reliable transport)
TIMER_F = 64 * T1  # 32s - non-INVITE client timeout
TIMER_H = 64 * T1  # 32s - INVITE server ACK wait
TIMER_I_UNRELIABLE = T4  # Absorb retransmitted ACKs (unreliable)
TIMER_I_RELIABLE = 0.0  # Absorb retransmitted ACKs (reliable)
TIMER_J_UNRELIABLE = 64 * T1  # Wait in Completed (non-INVITE server, unreliable)
TIMER_J_RELIABLE = 0.0  # Wait in Completed (non-INVITE server, reliable)
TIMER_K_UNRELIABLE = T4  # Wait in Completed (non-INVITE client, unreliable)
TIMER_K_RELIABLE = 0.0  # Wait in Completed (non-INVITE client, reliable)


@dataclass
class TimerState:
    """Represents an active timer with its current duration."""

    name: str
    duration: float
    active: bool = True


class ClientTransaction:
    """Client transaction state machine (RFC 3261 §17.1).

    Handles both INVITE and non-INVITE client transactions. The transaction
    type is determined by the request method: INVITE requests create INVITE
    client transactions; all other methods create non-INVITE client transactions.

    State transitions:
        INVITE:     Calling → Proceeding → Completed → Terminated
                    Calling → Terminated (2xx)
        Non-INVITE: Trying → Proceeding → Completed → Terminated
                    Trying → Completed (final response)

    Timers:
        INVITE:     A (retransmit), B (timeout), D (completed wait)
        Non-INVITE: E (retransmit), F (timeout), K (completed wait)
    """

    def __init__(self, request: Request) -> None:
        """Initialize a client transaction for the given request.

        Args:
            request: The SIP request that initiated this transaction.

        Raises:
            TransactionError: If the request is invalid for a transaction.
        """
        self.request = request
        self._is_invite = request.method == "INVITE"
        self._state = "Calling" if self._is_invite else "Trying"
        self._responses: list[Response] = []
        self._timers: dict[str, TimerState] = {}
        self._start_initial_timers()

    def _start_initial_timers(self) -> None:
        """Start timers that are active when the transaction begins."""
        if self._is_invite:
            # Timer A: retransmission (only for unreliable transport, but we track it)
            self._timers["A"] = TimerState("A", T1)
            # Timer B: transaction timeout
            self._timers["B"] = TimerState("B", TIMER_B)
        else:
            # Timer E: retransmission
            self._timers["E"] = TimerState("E", T1)
            # Timer F: transaction timeout
            self._timers["F"] = TimerState("F", TIMER_F)

    @property
    def state(self) -> str:
        """Current transaction state."""
        return self._state

    @property
    def timers(self) -> dict[str, TimerState]:
        """Active timers and their current state."""
        return dict(self._timers)

    @property
    def final_response(self) -> Response | None:
        """The final (2xx-6xx) response, if received."""
        for response in reversed(self._responses):
            if response.status_code >= 200:
                return response
        return None

    def receive_response(
        self,
        status_code: int,
        reason: str,
        headers: dict[str, Any] | None = None,
        body: bytes | None = None,
    ) -> str:
        """Process a received response and transition state.

        Args:
            status_code: SIP response status code (100-699).
            reason: SIP response reason phrase.
            headers: Response headers as a dictionary.
            body: Response body as bytes, or None.

        Returns:
            The new transaction state as a string.

        Raises:
            TransactionError: If the response is invalid for the current state,
                or if the status code is outside the valid range.
        """
        response = Response(
            status_code=status_code,
            reason=reason,
            headers=headers or {},
            body=body,
            request=self.request,
        )
        self._responses.append(response)

        if self._is_invite:
            return self._invite_transition(status_code)
        else:
            return self._non_invite_transition(status_code)

    def _invite_transition(self, status_code: int) -> str:
        """Handle state transition for INVITE client transaction."""
        if self._state == "Calling":
            if 100 <= status_code < 200:
                # Provisional response: Calling → Proceeding
                self._state = "Proceeding"
                # Stop Timer A (retransmission)
                if "A" in self._timers:
                    self._timers["A"].active = False
            elif 200 <= status_code < 300:
                # Success response: Calling → Terminated
                self._state = "Terminated"
                self._deactivate_all_timers()
            elif 300 <= status_code < 700:
                # Failure response: Calling → Completed
                self._state = "Completed"
                # Stop Timer A, start Timer D
                if "A" in self._timers:
                    self._timers["A"].active = False
                self._timers["D"] = TimerState("D", TIMER_D_UNRELIABLE)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.1.1",
                )

        elif self._state == "Proceeding":
            if 100 <= status_code < 200:
                # Additional provisional: stay in Proceeding
                pass
            elif 200 <= status_code < 300:
                # Success response: Proceeding → Terminated
                self._state = "Terminated"
                self._deactivate_all_timers()
            elif 300 <= status_code < 700:
                # Failure response: Proceeding → Completed
                self._state = "Completed"
                self._timers["D"] = TimerState("D", TIMER_D_UNRELIABLE)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.1.1",
                )

        elif self._state == "Completed":
            # In Completed state, only Timer D can transition to Terminated
            raise TransactionError(
                f"Invalid transition: response {status_code} in Completed state",
                rfc_ref="RFC 3261 §17.1.1",
            )

        elif self._state == "Terminated":
            # Transaction is complete, no further responses allowed
            raise TransactionError(
                f"Invalid transition: response {status_code} in Terminated state",
                rfc_ref="RFC 3261 §17.1.1",
            )

        else:
            raise TransactionError(
                f"Unexpected state: {self._state}",
                rfc_ref="RFC 3261 §17.1.1",
            )

        return self._state

    def _non_invite_transition(self, status_code: int) -> str:
        """Handle state transition for non-INVITE client transaction."""
        if self._state == "Trying":
            if 100 <= status_code < 200:
                # Provisional response: Trying → Proceeding
                self._state = "Proceeding"
                # Stop Timer E (retransmission)
                if "E" in self._timers:
                    self._timers["E"].active = False
            elif 200 <= status_code < 700:
                # Final response: Trying → Completed
                self._state = "Completed"
                # Stop Timers E and F, start Timer K
                if "E" in self._timers:
                    self._timers["E"].active = False
                if "F" in self._timers:
                    self._timers["F"].active = False
                self._timers["K"] = TimerState("K", TIMER_K_UNRELIABLE)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.1.2",
                )

        elif self._state == "Proceeding":
            if 100 <= status_code < 200:
                # Additional provisional: stay in Proceeding
                pass
            elif 200 <= status_code < 700:
                # Final response: Proceeding → Completed
                self._state = "Completed"
                # Stop Timers E and F, start Timer K
                if "E" in self._timers:
                    self._timers["E"].active = False
                if "F" in self._timers:
                    self._timers["F"].active = False
                self._timers["K"] = TimerState("K", TIMER_K_UNRELIABLE)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.1.2",
                )

        elif self._state == "Completed":
            # In Completed state, only Timer K can transition to Terminated
            raise TransactionError(
                f"Invalid transition: response {status_code} in Completed state",
                rfc_ref="RFC 3261 §17.1.2",
            )

        elif self._state == "Terminated":
            # Transaction is complete, no further responses allowed
            raise TransactionError(
                f"Invalid transition: response {status_code} in Terminated state",
                rfc_ref="RFC 3261 §17.1.2",
            )

        else:
            raise TransactionError(
                f"Unexpected state: {self._state}",
                rfc_ref="RFC 3261 §17.1.2",
            )

        return self._state

    def timer_fire(self, timer_name: str) -> str:
        """Handle a timer firing event.

        Args:
            timer_name: The name of the timer that fired (A, B, D, E, F, K).

        Returns:
            The new transaction state as a string.

        Raises:
            TransactionError: If the timer is invalid for this transaction type.
        """
        timer = self._timers.get(timer_name)
        if timer is None or not timer.active:
            # Timer not active or not applicable, no state change
            return self._state

        if timer_name == "A":
            # Timer A: retransmit request, double interval
            timer.duration *= 2
            # State remains unchanged

        elif timer_name == "B":
            # Timer B: transaction timeout → Terminated
            self._state = "Terminated"
            self._deactivate_all_timers()

        elif timer_name == "D":
            # Timer D: Completed → Terminated
            self._state = "Terminated"
            timer.active = False

        elif timer_name == "E":
            # Timer E: retransmit request, double interval up to T2
            timer.duration = min(timer.duration * 2, T2)
            # State remains unchanged

        elif timer_name == "F":
            # Timer F: transaction timeout → Terminated
            self._state = "Terminated"
            self._deactivate_all_timers()

        elif timer_name == "K":
            # Timer K: Completed → Terminated
            self._state = "Terminated"
            timer.active = False

        else:
            raise TransactionError(
                f"Invalid timer {timer_name} for client transaction",
                rfc_ref="RFC 3261 §17.1",
            )

        return self._state

    def _deactivate_all_timers(self) -> None:
        """Deactivate all active timers."""
        for timer in self._timers.values():
            timer.active = False


class ServerTransaction:
    """Server transaction state machine (RFC 3261 §17.2).

    Handles both INVITE and non-INVITE server transactions. The transaction
    type is determined by the request method: INVITE requests create INVITE
    server transactions; all other methods create non-INVITE server transactions.

    State transitions:
        INVITE:     Proceeding → Completed → Confirmed → Terminated
                    Proceeding → Terminated (2xx)
        Non-INVITE: Trying → Proceeding → Completed → Terminated
                    Trying → Completed (final response)

    Timers:
        INVITE:     G (retransmit failure), H (ACK wait), I (absorb ACK)
        Non-INVITE: J (completed wait)
    """

    def __init__(self, request: Request) -> None:
        """Initialize a server transaction for the given request.

        Args:
            request: The SIP request that initiated this transaction.

        Raises:
            TransactionError: If the request is invalid for a transaction.
        """
        self.request = request
        self._is_invite = request.method == "INVITE"
        self._state = "Proceeding" if self._is_invite else "Trying"
        self._responses: list[Response] = []
        self._timers: dict[str, TimerState] = {}

    @property
    def state(self) -> str:
        """Current transaction state."""
        return self._state

    @property
    def timers(self) -> dict[str, TimerState]:
        """Active timers and their current state."""
        return dict(self._timers)

    def send_response(
        self,
        status_code: int,
        reason: str,
        headers: dict[str, Any] | None = None,
        body: bytes | None = None,
    ) -> str:
        """Process a response to send and transition state.

        Args:
            status_code: SIP response status code (100-699).
            reason: SIP response reason phrase.
            headers: Response headers as a dictionary.
            body: Response body as bytes, or None.

        Returns:
            The new transaction state as a string.

        Raises:
            TransactionError: If the response is invalid for the current state,
                or if the status code is outside the valid range.
        """
        response = Response(
            status_code=status_code,
            reason=reason,
            headers=headers or {},
            body=body,
            request=self.request,
        )
        self._responses.append(response)

        if self._is_invite:
            return self._invite_transition(status_code)
        else:
            return self._non_invite_transition(status_code)

    def _invite_transition(self, status_code: int) -> str:
        """Handle state transition for INVITE server transaction."""
        if self._state == "Proceeding":
            if 100 <= status_code < 200:
                # Provisional response: stay in Proceeding
                pass
            elif 200 <= status_code < 300:
                # Success response: Proceeding → Terminated
                self._state = "Terminated"
            elif 300 <= status_code < 700:
                # Failure response: Proceeding → Completed
                self._state = "Completed"
                # Start Timer G (retransmit) and Timer H (ACK wait)
                self._timers["G"] = TimerState("G", T1)
                self._timers["H"] = TimerState("H", TIMER_H)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.2.1",
                )

        elif self._state == "Completed":
            # In Completed state, only ACK can transition to Confirmed
            raise TransactionError(
                f"Invalid transition: response {status_code} in Completed state",
                rfc_ref="RFC 3261 §17.2.1",
            )

        elif self._state == "Confirmed":
            # In Confirmed state, only Timer I can transition to Terminated
            raise TransactionError(
                f"Invalid transition: response {status_code} in Confirmed state",
                rfc_ref="RFC 3261 §17.2.1",
            )

        elif self._state == "Terminated":
            # Transaction is complete, no further responses allowed
            raise TransactionError(
                f"Invalid transition: response {status_code} in Terminated state",
                rfc_ref="RFC 3261 §17.2.1",
            )

        else:
            raise TransactionError(
                f"Unexpected state: {self._state}",
                rfc_ref="RFC 3261 §17.2.1",
            )

        return self._state

    def _non_invite_transition(self, status_code: int) -> str:
        """Handle state transition for non-INVITE server transaction."""
        if self._state == "Trying":
            if 100 <= status_code < 200:
                # Provisional response: Trying → Proceeding
                self._state = "Proceeding"
            elif 200 <= status_code < 700:
                # Final response: Trying → Completed
                self._state = "Completed"
                # Start Timer J
                self._timers["J"] = TimerState("J", TIMER_J_UNRELIABLE)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.2.2",
                )

        elif self._state == "Proceeding":
            if 100 <= status_code < 200:
                # Additional provisional: stay in Proceeding
                pass
            elif 200 <= status_code < 700:
                # Final response: Proceeding → Completed
                self._state = "Completed"
                # Start Timer J
                self._timers["J"] = TimerState("J", TIMER_J_UNRELIABLE)
            else:
                raise TransactionError(
                    f"Invalid status code {status_code} in state {self._state}",
                    rfc_ref="RFC 3261 §17.2.2",
                )

        elif self._state == "Completed":
            # In Completed state, only Timer J can transition to Terminated
            raise TransactionError(
                f"Invalid transition: response {status_code} in Completed state",
                rfc_ref="RFC 3261 §17.2.2",
            )

        elif self._state == "Terminated":
            # Transaction is complete, no further responses allowed
            raise TransactionError(
                f"Invalid transition: response {status_code} in Terminated state",
                rfc_ref="RFC 3261 §17.2.2",
            )

        else:
            raise TransactionError(
                f"Unexpected state: {self._state}",
                rfc_ref="RFC 3261 §17.2.2",
            )

        return self._state

    def receive_ack(self) -> str:
        """Handle receiving an ACK (INVITE server transaction only).

        Returns:
            The new transaction state as a string.

        Raises:
            TransactionError: If ACK is not valid for this transaction type or state.
        """
        if not self._is_invite:
            raise TransactionError(
                "ACK only valid for INVITE server transactions",
                rfc_ref="RFC 3261 §17.2.1",
            )

        if self._state != "Completed":
            raise TransactionError(
                f"ACK not valid in {self._state} state (requires Completed)",
                rfc_ref="RFC 3261 §17.2.1",
            )

        # Completed → Confirmed
        self._state = "Confirmed"

        # Stop Timers G and H, start Timer I
        for name in ("G", "H"):
            if name in self._timers:
                self._timers[name].active = False
        self._timers["I"] = TimerState("I", TIMER_I_UNRELIABLE)

        return self._state

    def timer_fire(self, timer_name: str) -> str:
        """Handle a timer firing event.

        Args:
            timer_name: The name of the timer that fired (G, H, I, J).

        Returns:
            The new transaction state as a string.

        Raises:
            TransactionError: If the timer is invalid for this transaction type.
        """
        timer = self._timers.get(timer_name)
        if timer is None or not timer.active:
            # Timer not active or not applicable, no state change
            return self._state

        if timer_name == "G":
            # Timer G: retransmit response, double interval
            timer.duration *= 2
            # State remains unchanged

        elif timer_name == "H":
            # Timer H: ACK timeout → Terminated
            self._state = "Terminated"
            self._deactivate_all_timers()

        elif timer_name == "I":
            # Timer I: Confirmed → Terminated
            self._state = "Terminated"
            timer.active = False

        elif timer_name == "J":
            # Timer J: Completed → Terminated
            self._state = "Terminated"
            timer.active = False

        else:
            raise TransactionError(
                f"Invalid timer {timer_name} for server transaction",
                rfc_ref="RFC 3261 §17.2",
            )

        return self._state

    def _deactivate_all_timers(self) -> None:
        """Deactivate all active timers."""
        for timer in self._timers.values():
            timer.active = False
