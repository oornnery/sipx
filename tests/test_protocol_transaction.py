"""Tests for transaction state machines in sipx.protocol.transaction."""

from __future__ import annotations

import pytest

from sipx.exceptions import TransactionError
from sipx.models import Request
from sipx.protocol.transaction import (
    ClientTransaction,
    ServerTransaction,
    T1,
    T2,
    TIMER_B,
    TIMER_D_UNRELIABLE,
    TIMER_F,
    TIMER_H,
    TIMER_I_UNRELIABLE,
    TIMER_J_UNRELIABLE,
    TIMER_K_UNRELIABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invite_request() -> Request:
    return Request(method="INVITE", uri="sip:bob@example.com", headers={}, body=None)


def _non_invite_request(method: str = "OPTIONS") -> Request:
    return Request(method=method, uri="sip:bob@example.com", headers={}, body=None)


# ===========================================================================
# Client Transaction – INVITE
# ===========================================================================


class TestInviteClientTransaction:
    """INVITE client transaction state machine tests."""

    def test_initial_state_is_calling(self):
        t = ClientTransaction(_invite_request())
        assert t.state == "Calling"

    def test_calling_to_proceeding_on_1xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(100, "Trying", {}, None)
        assert t.state == "Proceeding"

    def test_calling_to_terminated_on_2xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Terminated"

    def test_calling_to_completed_on_3xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(302, "Moved Temporarily", {}, None)
        assert t.state == "Completed"

    def test_calling_to_completed_on_4xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(404, "Not Found", {}, None)
        assert t.state == "Completed"

    def test_calling_to_completed_on_5xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(500, "Server Internal Error", {}, None)
        assert t.state == "Completed"

    def test_calling_to_completed_on_6xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(603, "Decline", {}, None)
        assert t.state == "Completed"

    def test_proceeding_stays_on_additional_1xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(100, "Trying", {}, None)
        t.receive_response(180, "Ringing", {}, None)
        assert t.state == "Proceeding"

    def test_proceeding_to_terminated_on_2xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(100, "Trying", {}, None)
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Terminated"

    def test_proceeding_to_completed_on_4xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(180, "Ringing", {}, None)
        t.receive_response(487, "Request Terminated", {}, None)
        assert t.state == "Completed"

    def test_completed_to_terminated_via_timer_d(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(404, "Not Found", {}, None)
        assert t.state == "Completed"
        t.timer_fire("D")
        assert t.state == "Terminated"

    def test_invalid_transition_from_terminated(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Terminated"
        with pytest.raises(TransactionError):
            t.receive_response(180, "Ringing", {}, None)

    def test_invalid_transition_from_completed(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(404, "Not Found", {}, None)
        assert t.state == "Completed"
        with pytest.raises(TransactionError):
            t.receive_response(200, "OK", {}, None)

    def test_invalid_status_code_below_100(self):
        t = ClientTransaction(_invite_request())
        with pytest.raises(TransactionError):
            t.receive_response(99, "Invalid", {}, None)

    def test_invalid_status_code_above_699(self):
        t = ClientTransaction(_invite_request())
        with pytest.raises(TransactionError):
            t.receive_response(700, "Invalid", {}, None)


# ===========================================================================
# Client Transaction – Non-INVITE
# ===========================================================================


class TestNonInviteClientTransaction:
    """Non-INVITE client transaction state machine tests."""

    def test_initial_state_is_trying(self):
        t = ClientTransaction(_non_invite_request())
        assert t.state == "Trying"

    def test_trying_to_proceeding_on_1xx(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(100, "Trying", {}, None)
        assert t.state == "Proceeding"

    def test_trying_to_completed_on_2xx(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Completed"

    def test_trying_to_completed_on_4xx(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(404, "Not Found", {}, None)
        assert t.state == "Completed"

    def test_trying_to_completed_on_5xx(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(503, "Service Unavailable", {}, None)
        assert t.state == "Completed"

    def test_proceeding_stays_on_additional_1xx(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(100, "Trying", {}, None)
        t.receive_response(199, "Info", {}, None)
        assert t.state == "Proceeding"

    def test_proceeding_to_completed_on_2xx(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(100, "Trying", {}, None)
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Completed"

    def test_completed_to_terminated_via_timer_k(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Completed"
        t.timer_fire("K")
        assert t.state == "Terminated"

    def test_invalid_transition_from_terminated(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(200, "OK", {}, None)
        t.timer_fire("K")
        assert t.state == "Terminated"
        with pytest.raises(TransactionError):
            t.receive_response(100, "Trying", {}, None)

    def test_invalid_transition_from_completed(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(200, "OK", {}, None)
        assert t.state == "Completed"
        with pytest.raises(TransactionError):
            t.receive_response(100, "Trying", {}, None)


# ===========================================================================
# Server Transaction – INVITE
# ===========================================================================


class TestInviteServerTransaction:
    """INVITE server transaction state machine tests."""

    def test_initial_state_is_proceeding(self):
        t = ServerTransaction(_invite_request())
        assert t.state == "Proceeding"

    def test_proceeding_stays_on_1xx(self):
        t = ServerTransaction(_invite_request())
        t.send_response(100, "Trying", {}, None)
        assert t.state == "Proceeding"

    def test_proceeding_stays_on_additional_1xx(self):
        t = ServerTransaction(_invite_request())
        t.send_response(100, "Trying", {}, None)
        t.send_response(180, "Ringing", {}, None)
        assert t.state == "Proceeding"

    def test_proceeding_to_terminated_on_2xx(self):
        t = ServerTransaction(_invite_request())
        t.send_response(200, "OK", {}, None)
        assert t.state == "Terminated"

    def test_proceeding_to_completed_on_3xx(self):
        t = ServerTransaction(_invite_request())
        t.send_response(302, "Moved Temporarily", {}, None)
        assert t.state == "Completed"

    def test_proceeding_to_completed_on_4xx(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        assert t.state == "Completed"

    def test_proceeding_to_completed_on_5xx(self):
        t = ServerTransaction(_invite_request())
        t.send_response(500, "Server Internal Error", {}, None)
        assert t.state == "Completed"

    def test_completed_to_confirmed_on_ack(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        assert t.state == "Completed"
        t.receive_ack()
        assert t.state == "Confirmed"

    def test_confirmed_to_terminated_via_timer_i(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        t.receive_ack()
        assert t.state == "Confirmed"
        t.timer_fire("I")
        assert t.state == "Terminated"

    def test_completed_to_terminated_via_timer_h(self):
        """Timer H fires when no ACK received → Terminated."""
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        assert t.state == "Completed"
        t.timer_fire("H")
        assert t.state == "Terminated"

    def test_invalid_response_in_completed(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        with pytest.raises(TransactionError):
            t.send_response(200, "OK", {}, None)

    def test_invalid_response_in_confirmed(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        t.receive_ack()
        with pytest.raises(TransactionError):
            t.send_response(100, "Trying", {}, None)

    def test_invalid_response_in_terminated(self):
        t = ServerTransaction(_invite_request())
        t.send_response(200, "OK", {}, None)
        with pytest.raises(TransactionError):
            t.send_response(100, "Trying", {}, None)

    def test_ack_on_non_invite_raises(self):
        t = ServerTransaction(_non_invite_request())
        with pytest.raises(TransactionError):
            t.receive_ack()

    def test_ack_in_wrong_state_raises(self):
        t = ServerTransaction(_invite_request())
        # State is Proceeding, not Completed
        with pytest.raises(TransactionError):
            t.receive_ack()


# ===========================================================================
# Server Transaction – Non-INVITE
# ===========================================================================


class TestNonInviteServerTransaction:
    """Non-INVITE server transaction state machine tests."""

    def test_initial_state_is_trying(self):
        t = ServerTransaction(_non_invite_request())
        assert t.state == "Trying"

    def test_trying_to_proceeding_on_1xx(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(100, "Trying", {}, None)
        assert t.state == "Proceeding"

    def test_trying_to_completed_on_2xx(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(200, "OK", {}, None)
        assert t.state == "Completed"

    def test_trying_to_completed_on_4xx(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(404, "Not Found", {}, None)
        assert t.state == "Completed"

    def test_proceeding_stays_on_additional_1xx(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(100, "Trying", {}, None)
        t.send_response(199, "Info", {}, None)
        assert t.state == "Proceeding"

    def test_proceeding_to_completed_on_2xx(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(100, "Trying", {}, None)
        t.send_response(200, "OK", {}, None)
        assert t.state == "Completed"

    def test_completed_to_terminated_via_timer_j(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(200, "OK", {}, None)
        assert t.state == "Completed"
        t.timer_fire("J")
        assert t.state == "Terminated"

    def test_invalid_response_in_completed(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(200, "OK", {}, None)
        with pytest.raises(TransactionError):
            t.send_response(100, "Trying", {}, None)

    def test_invalid_response_in_terminated(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(200, "OK", {}, None)
        t.timer_fire("J")
        with pytest.raises(TransactionError):
            t.send_response(100, "Trying", {}, None)


# ===========================================================================
# Timer behaviour
# ===========================================================================


class TestTimerBehaviour:
    """Verify timer state tracking and transitions."""

    def test_invite_client_starts_with_timers_a_and_b(self):
        t = ClientTransaction(_invite_request())
        timers = t.timers
        assert "A" in timers
        assert "B" in timers
        assert timers["A"].active is True
        assert timers["B"].active is True
        assert timers["A"].duration == T1
        assert timers["B"].duration == TIMER_B

    def test_non_invite_client_starts_with_timers_e_and_f(self):
        t = ClientTransaction(_non_invite_request())
        timers = t.timers
        assert "E" in timers
        assert "F" in timers
        assert timers["E"].active is True
        assert timers["F"].active is True
        assert timers["E"].duration == T1
        assert timers["F"].duration == TIMER_F

    def test_timer_a_doubles_on_fire(self):
        t = ClientTransaction(_invite_request())
        initial = t.timers["A"].duration
        t.timer_fire("A")
        assert t.timers["A"].duration == initial * 2

    def test_timer_e_caps_at_t2(self):
        t = ClientTransaction(_non_invite_request())
        # Fire Timer E enough times to exceed T2
        for _ in range(20):
            t.timer_fire("E")
        assert t.timers["E"].duration <= T2

    def test_timer_b_terminates_invite_client(self):
        t = ClientTransaction(_invite_request())
        t.timer_fire("B")
        assert t.state == "Terminated"
        # All timers should be deactivated
        for timer in t.timers.values():
            assert timer.active is False

    def test_timer_f_terminates_non_invite_client(self):
        t = ClientTransaction(_non_invite_request())
        t.timer_fire("F")
        assert t.state == "Terminated"
        for timer in t.timers.values():
            assert timer.active is False

    def test_timer_d_starts_on_completed_invite_client(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(404, "Not Found", {}, None)
        timers = t.timers
        assert "D" in timers
        assert timers["D"].active is True
        assert timers["D"].duration == TIMER_D_UNRELIABLE

    def test_timer_k_starts_on_completed_non_invite_client(self):
        t = ClientTransaction(_non_invite_request())
        t.receive_response(200, "OK", {}, None)
        timers = t.timers
        assert "K" in timers
        assert timers["K"].active is True
        assert timers["K"].duration == TIMER_K_UNRELIABLE

    def test_invite_server_starts_timers_g_h_on_failure(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        timers = t.timers
        assert "G" in timers
        assert "H" in timers
        assert timers["G"].active is True
        assert timers["H"].active is True
        assert timers["G"].duration == T1
        assert timers["H"].duration == TIMER_H

    def test_timer_g_doubles_on_fire(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        initial = t.timers["G"].duration
        t.timer_fire("G")
        assert t.timers["G"].duration == initial * 2

    def test_timer_i_starts_on_ack(self):
        t = ServerTransaction(_invite_request())
        t.send_response(486, "Busy Here", {}, None)
        t.receive_ack()
        timers = t.timers
        assert "I" in timers
        assert timers["I"].active is True
        assert timers["I"].duration == TIMER_I_UNRELIABLE
        # G and H should be deactivated
        assert timers["G"].active is False
        assert timers["H"].active is False

    def test_timer_j_starts_on_completed_non_invite_server(self):
        t = ServerTransaction(_non_invite_request())
        t.send_response(200, "OK", {}, None)
        timers = t.timers
        assert "J" in timers
        assert timers["J"].active is True
        assert timers["J"].duration == TIMER_J_UNRELIABLE

    def test_inactive_timer_fire_is_noop(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(200, "OK", {}, None)
        # All timers deactivated; firing any should be a no-op
        assert t.timer_fire("A") == "Terminated"
        assert t.state == "Terminated"

    def test_unknown_timer_fire_is_noop(self):
        t = ClientTransaction(_invite_request())
        # Timer Z doesn't exist; should return current state
        assert t.timer_fire("Z") == "Calling"


# ===========================================================================
# Final response tracking
# ===========================================================================


class TestFinalResponse:
    """Verify final_response property."""

    def test_no_final_response_initially(self):
        t = ClientTransaction(_invite_request())
        assert t.final_response is None

    def test_final_response_after_2xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(200, "OK", {}, None)
        assert t.final_response is not None
        assert t.final_response.status_code == 200

    def test_final_response_after_4xx(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(404, "Not Found", {}, None)
        assert t.final_response is not None
        assert t.final_response.status_code == 404

    def test_provisional_is_not_final(self):
        t = ClientTransaction(_invite_request())
        t.receive_response(180, "Ringing", {}, None)
        assert t.final_response is None
