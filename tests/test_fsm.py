"""Tests for sipx._fsm module: Transaction, Dialog, StateManager."""

from __future__ import annotations

import time

import pytest

from sipx._fsm import Dialog, StateManager, Transaction
from sipx._models._message import Request, Response
from sipx._types import DialogState, TransactionState, TransactionType


# ============================================================================
# Transaction
# ============================================================================


class TestTransaction:
    def test_creation_with_defaults(self):
        txn = Transaction()
        assert txn.transaction_type == TransactionType.NON_INVITE
        assert txn.state == TransactionState.CALLING
        assert txn.request is None
        assert txn.responses == []
        assert txn.branch == ""
        assert txn.id  # UUID generated
        assert txn.created_at <= time.time()

    def test_transition_to_changes_state(self):
        txn = Transaction()
        txn.transition_to(TransactionState.TRYING)
        assert txn.state == TransactionState.TRYING

    def test_transition_to_updates_timestamp(self):
        txn = Transaction()
        old_updated = txn.updated_at
        # Small delay to ensure time difference
        time.sleep(0.01)
        txn.transition_to(TransactionState.TRYING)
        assert txn.updated_at >= old_updated

    def test_add_response_provisional_invite(self):
        """1xx response on INVITE in CALLING -> TRYING."""
        txn = Transaction(transaction_type=TransactionType.INVITE)
        resp = Response(status_code=100)
        txn.add_response(resp)
        assert len(txn.responses) == 1
        assert txn.state == TransactionState.TRYING

    def test_add_response_provisional_invite_trying_to_proceeding(self):
        """Second 1xx response on INVITE in TRYING -> PROCEEDING."""
        txn = Transaction(transaction_type=TransactionType.INVITE)
        txn.transition_to(TransactionState.TRYING)
        resp = Response(status_code=180)
        txn.add_response(resp)
        assert txn.state == TransactionState.PROCEEDING

    def test_add_response_final_completes(self):
        """2xx+ response -> COMPLETED."""
        txn = Transaction(transaction_type=TransactionType.INVITE)
        resp = Response(status_code=200)
        txn.add_response(resp)
        assert txn.state == TransactionState.COMPLETED

    def test_add_response_4xx_completes(self):
        """4xx response -> COMPLETED."""
        txn = Transaction(transaction_type=TransactionType.NON_INVITE)
        resp = Response(status_code=404)
        txn.add_response(resp)
        assert txn.state == TransactionState.COMPLETED

    def test_is_complete(self):
        txn = Transaction()
        assert txn.is_complete() is False
        txn.transition_to(TransactionState.COMPLETED)
        assert txn.is_complete() is True

    def test_is_complete_includes_confirmed(self):
        txn = Transaction()
        txn.transition_to(TransactionState.CONFIRMED)
        assert txn.is_complete() is True

    def test_is_complete_includes_terminated(self):
        txn = Transaction()
        txn.transition_to(TransactionState.TERMINATED)
        assert txn.is_complete() is True

    def test_is_terminated(self):
        txn = Transaction()
        assert txn.is_terminated() is False
        txn.transition_to(TransactionState.TERMINATED)
        assert txn.is_terminated() is True

    def test_get_final_response_returns_final(self):
        txn = Transaction()
        provisional = Response(status_code=180)
        final = Response(status_code=200)
        txn.responses = [provisional, final]
        assert txn.get_final_response() is final

    def test_get_final_response_returns_none_when_only_provisional(self):
        txn = Transaction()
        txn.responses = [Response(status_code=100)]
        assert txn.get_final_response() is None

    def test_get_final_response_returns_none_when_empty(self):
        txn = Transaction()
        assert txn.get_final_response() is None

    def test_timer_values_set_on_invite_calling(self):
        txn = Transaction(transaction_type=TransactionType.INVITE)
        txn.transition_to(TransactionState.CALLING)
        assert txn.timer_a == 0.5
        assert txn.timer_b == 32.0

    def test_timer_values_set_on_invite_completed(self):
        txn = Transaction(transaction_type=TransactionType.INVITE)
        txn.transition_to(TransactionState.COMPLETED)
        assert txn.timer_d == 32.0

    def test_timer_values_set_on_non_invite_trying(self):
        txn = Transaction(transaction_type=TransactionType.NON_INVITE)
        txn.transition_to(TransactionState.TRYING)
        assert txn.timer_e == 0.5
        assert txn.timer_f == 32.0

    def test_timer_values_set_on_non_invite_completed(self):
        txn = Transaction(transaction_type=TransactionType.NON_INVITE)
        txn.transition_to(TransactionState.COMPLETED)
        assert txn.timer_k == 5.0


# ============================================================================
# Dialog
# ============================================================================


class TestDialog:
    def test_creation_defaults(self):
        dlg = Dialog()
        assert dlg.state == DialogState.EARLY
        assert dlg.call_id == ""
        assert dlg.local_tag == ""
        assert dlg.remote_tag == ""
        assert dlg.local_seq == 1
        assert dlg.remote_seq == 0
        assert dlg.transactions == []

    def test_creation_with_values(self):
        dlg = Dialog(
            call_id="abc123",
            local_tag="tag1",
            remote_tag="tag2",
            local_uri="sip:alice@example.com",
            remote_uri="sip:bob@example.com",
        )
        assert dlg.call_id == "abc123"
        assert dlg.local_tag == "tag1"
        assert dlg.remote_tag == "tag2"

    def test_get_dialog_id_format(self):
        dlg = Dialog(call_id="abc", local_tag="ltag", remote_tag="rtag")
        assert dlg.get_dialog_id() == "abc:ltag:rtag"

    def test_increment_local_seq(self):
        dlg = Dialog()
        assert dlg.local_seq == 1
        result = dlg.increment_local_seq()
        assert result == 2
        assert dlg.local_seq == 2
        result = dlg.increment_local_seq()
        assert result == 3

    def test_update_remote_seq(self):
        dlg = Dialog()
        assert dlg.remote_seq == 0
        dlg.update_remote_seq(5)
        assert dlg.remote_seq == 5

    def test_update_remote_seq_ignores_lower(self):
        dlg = Dialog()
        dlg.update_remote_seq(10)
        dlg.update_remote_seq(5)
        assert dlg.remote_seq == 10

    def test_transition_to(self):
        dlg = Dialog()
        assert dlg.state == DialogState.EARLY
        dlg.transition_to(DialogState.CONFIRMED)
        assert dlg.state == DialogState.CONFIRMED

    def test_is_confirmed(self):
        dlg = Dialog()
        assert dlg.is_confirmed() is False
        dlg.transition_to(DialogState.CONFIRMED)
        assert dlg.is_confirmed() is True

    def test_is_terminated(self):
        dlg = Dialog()
        assert dlg.is_terminated() is False
        dlg.transition_to(DialogState.TERMINATED)
        assert dlg.is_terminated() is True

    def test_add_transaction(self):
        dlg = Dialog()
        dlg.add_transaction("txn-1")
        assert "txn-1" in dlg.transactions
        # Adding duplicate does nothing
        dlg.add_transaction("txn-1")
        assert dlg.transactions.count("txn-1") == 1


# ============================================================================
# StateManager
# ============================================================================


class TestStateManager:
    def test_create_transaction_auto_detects_invite(self):
        sm = StateManager()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        txn = sm.create_transaction(req)
        assert txn.transaction_type == TransactionType.INVITE
        assert txn.request is req

    def test_create_transaction_auto_detects_non_invite(self):
        sm = StateManager()
        req = Request(method="REGISTER", uri="sip:example.com")
        txn = sm.create_transaction(req)
        assert txn.transaction_type == TransactionType.NON_INVITE

    def test_create_transaction_explicit_type(self):
        sm = StateManager()
        req = Request(method="OPTIONS", uri="sip:example.com")
        txn = sm.create_transaction(req, transaction_type=TransactionType.INVITE)
        assert txn.transaction_type == TransactionType.INVITE

    def test_create_transaction_extracts_branch(self):
        sm = StateManager()
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"Via": "SIP/2.0/UDP 10.0.0.1;branch=z9hG4bKtest123"},
        )
        txn = sm.create_transaction(req)
        assert txn.branch == "z9hG4bKtest123"

    def test_create_dialog(self):
        sm = StateManager()
        dlg = sm.create_dialog(
            call_id="abc",
            local_tag="ltag",
            remote_tag="rtag",
            local_uri="sip:alice@example.com",
            remote_uri="sip:bob@example.com",
            remote_target="sip:bob@192.168.1.1",
        )
        assert dlg.call_id == "abc"
        assert dlg.state == DialogState.EARLY

    def test_find_transaction_by_branch(self):
        sm = StateManager()
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"Via": "SIP/2.0/UDP 10.0.0.1;branch=z9hG4bKfind"},
        )
        txn = sm.create_transaction(req)
        found = sm.find_transaction(branch="z9hG4bKfind")
        assert found is txn

    def test_find_transaction_by_call_id(self):
        sm = StateManager()
        req = Request(
            method="INVITE",
            uri="sip:bob@example.com",
            headers={"Call-ID": "unique-call-id-123"},
        )
        txn = sm.create_transaction(req)
        found = sm.find_transaction(call_id="unique-call-id-123")
        assert found is txn

    def test_find_transaction_by_method(self):
        sm = StateManager()
        req = Request(method="REGISTER", uri="sip:example.com")
        txn = sm.create_transaction(req)
        found = sm.find_transaction(method="REGISTER")
        assert found is txn

    def test_find_transaction_returns_none_when_not_found(self):
        sm = StateManager()
        found = sm.find_transaction(branch="nonexistent")
        assert found is None

    def test_find_dialog(self):
        sm = StateManager()
        sm.create_dialog(
            call_id="abc",
            local_tag="ltag",
            remote_tag="rtag",
            local_uri="sip:alice@example.com",
            remote_uri="sip:bob@example.com",
            remote_target="sip:bob@192.168.1.1",
        )
        found = sm.find_dialog(call_id="abc")
        assert found is not None
        assert found.call_id == "abc"

    def test_find_dialog_with_tags(self):
        sm = StateManager()
        sm.create_dialog(
            call_id="abc",
            local_tag="ltag",
            remote_tag="rtag",
            local_uri="sip:alice@example.com",
            remote_uri="sip:bob@example.com",
            remote_target="sip:bob@192.168.1.1",
        )
        found = sm.find_dialog(call_id="abc", local_tag="ltag", remote_tag="rtag")
        assert found is not None

    def test_find_dialog_returns_none_when_not_found(self):
        sm = StateManager()
        found = sm.find_dialog(call_id="nonexistent")
        assert found is None

    def test_cleanup_transactions_removes_old(self):
        sm = StateManager()
        req = Request(method="OPTIONS", uri="sip:example.com")
        txn = sm.create_transaction(req)
        # Force the updated_at to be old
        txn.updated_at = time.time() - 600
        removed = sm.cleanup_transactions(max_age=300)
        assert removed == 1
        assert sm.get_transaction(txn.id) is None

    def test_cleanup_transactions_removes_terminated(self):
        sm = StateManager()
        req = Request(method="OPTIONS", uri="sip:example.com")
        txn = sm.create_transaction(req)
        txn.transition_to(TransactionState.TERMINATED)
        removed = sm.cleanup_transactions(max_age=99999)
        assert removed == 1

    def test_cleanup_transactions_keeps_active(self):
        sm = StateManager()
        req = Request(method="OPTIONS", uri="sip:example.com")
        sm.create_transaction(req)
        removed = sm.cleanup_transactions(max_age=300)
        assert removed == 0

    def test_cleanup_dialogs_removes_old(self):
        sm = StateManager()
        dlg = sm.create_dialog(
            call_id="old",
            local_tag="l",
            remote_tag="r",
            local_uri="sip:a@x.com",
            remote_uri="sip:b@x.com",
            remote_target="sip:b@1.2.3.4",
        )
        dlg.updated_at = time.time() - 7200
        removed = sm.cleanup_dialogs(max_age=3600)
        assert removed == 1

    def test_cleanup_dialogs_removes_terminated(self):
        sm = StateManager()
        dlg = sm.create_dialog(
            call_id="term",
            local_tag="l",
            remote_tag="r",
            local_uri="sip:a@x.com",
            remote_uri="sip:b@x.com",
            remote_target="sip:b@1.2.3.4",
        )
        dlg.transition_to(DialogState.TERMINATED)
        removed = sm.cleanup_dialogs(max_age=99999)
        assert removed == 1

    def test_cleanup_dialogs_keeps_active(self):
        sm = StateManager()
        sm.create_dialog(
            call_id="active",
            local_tag="l",
            remote_tag="r",
            local_uri="sip:a@x.com",
            remote_uri="sip:b@x.com",
            remote_target="sip:b@1.2.3.4",
        )
        removed = sm.cleanup_dialogs(max_age=3600)
        assert removed == 0

    def test_get_statistics(self):
        sm = StateManager()
        req1 = Request(method="INVITE", uri="sip:bob@example.com")
        req2 = Request(method="REGISTER", uri="sip:example.com")
        sm.create_transaction(req1)
        sm.create_transaction(req2)
        sm.create_dialog(
            call_id="abc",
            local_tag="l",
            remote_tag="r",
            local_uri="sip:a@x.com",
            remote_uri="sip:b@x.com",
            remote_target="sip:b@1.2.3.4",
        )

        stats = sm.get_statistics()
        assert stats["transactions"]["total"] == 2
        assert stats["dialogs"]["total"] == 1
        assert "by_state" in stats["transactions"]
        assert "by_type" in stats["transactions"]
        assert "by_state" in stats["dialogs"]
