"""Tests for sipx._events module: Events, EventContext, event_handler decorator."""

from __future__ import annotations


from sipx._events import Events, EventContext, event_handler
from sipx._models._message import Request, Response


# ============================================================================
# event_handler decorator
# ============================================================================


class TestEventHandlerDecorator:
    """Test that @event_handler stores metadata on the decorated function."""

    def test_single_method_stores_metadata(self):
        @event_handler("INVITE")
        def handler(req, resp, ctx):
            pass

        assert handler._is_event_handler is True
        assert handler._event_handler_method == ("INVITE",)
        assert handler._event_handler_status is None

    def test_tuple_method_stores_metadata(self):
        @event_handler(("INVITE", "REGISTER"))
        def handler(req, resp, ctx):
            pass

        assert handler._event_handler_method == ("INVITE", "REGISTER")

    def test_none_method_matches_all(self):
        @event_handler(None, status=200)
        def handler(req, resp, ctx):
            pass

        assert handler._event_handler_method is None
        assert handler._event_handler_status == (200,)

    def test_single_status_stores_metadata(self):
        @event_handler("INVITE", status=200)
        def handler(req, resp, ctx):
            pass

        assert handler._event_handler_status == (200,)

    def test_tuple_status_stores_metadata(self):
        @event_handler("INVITE", status=(200, 401))
        def handler(req, resp, ctx):
            pass

        assert handler._event_handler_status == (200, 401)

    def test_range_status_stores_metadata(self):
        @event_handler("INVITE", status=range(200, 300))
        def handler(req, resp, ctx):
            pass

        # range is expanded to tuple
        assert 200 in handler._event_handler_status
        assert 299 in handler._event_handler_status
        assert 300 not in handler._event_handler_status

    def test_none_status_matches_all(self):
        @event_handler("INVITE")
        def handler(req, resp, ctx):
            pass

        assert handler._event_handler_status is None

    def test_no_args_matches_all(self):
        @event_handler()
        def handler(req, resp, ctx):
            pass

        assert handler._event_handler_method is None
        assert handler._event_handler_status is None


# ============================================================================
# EventContext
# ============================================================================


class TestEventContext:
    def test_creation_defaults(self):
        ctx = EventContext()
        assert ctx.request is None
        assert ctx.response is None
        assert ctx.destination is None
        assert ctx.source is None
        assert ctx.transaction_id is None
        assert ctx.dialog_id is None
        assert ctx.transaction is None
        assert ctx.dialog is None
        assert ctx.metadata == {}

    def test_creation_with_values(self):
        req = Request(method="INVITE", uri="sip:bob@example.com")
        ctx = EventContext(request=req, transaction_id="txn-1", metadata={"key": "val"})
        assert ctx.request is req
        assert ctx.transaction_id == "txn-1"
        assert ctx.metadata["key"] == "val"


# ============================================================================
# Events._discover_handlers
# ============================================================================


class TestDiscoverHandlers:
    def test_discovers_decorated_methods(self):
        class MyEvents(Events):
            @event_handler("INVITE", status=200)
            def on_invite_ok(self, req, resp, ctx):
                pass

            @event_handler("REGISTER")
            def on_register(self, req, resp, ctx):
                pass

        ev = MyEvents()
        assert len(ev._handlers) == 2

    def test_skips_non_decorated_methods(self):
        class MyEvents(Events):
            def normal_method(self):
                pass

            @event_handler("INVITE")
            def on_invite(self, req, resp, ctx):
                pass

        ev = MyEvents()
        assert len(ev._handlers) == 1

    def test_skips_private_methods(self):
        """Private/underscore methods are skipped by _discover_handlers."""

        class MyEvents(Events):
            @event_handler("INVITE")
            def _private_handler(self, req, resp, ctx):
                pass

        ev = MyEvents()
        assert len(ev._handlers) == 0


# ============================================================================
# Method matching
# ============================================================================


class TestMethodMatching:
    def test_single_method_match(self):
        ev = Events()
        assert ev._matches_method("INVITE", ("INVITE",)) is True
        assert ev._matches_method("REGISTER", ("INVITE",)) is False

    def test_tuple_method_match(self):
        ev = Events()
        assert ev._matches_method("INVITE", ("INVITE", "REGISTER")) is True
        assert ev._matches_method("REGISTER", ("INVITE", "REGISTER")) is True
        assert ev._matches_method("BYE", ("INVITE", "REGISTER")) is False

    def test_none_matches_all(self):
        ev = Events()
        assert ev._matches_method("ANYTHING", None) is True


# ============================================================================
# Status matching
# ============================================================================


class TestStatusMatching:
    def test_single_status_match(self):
        ev = Events()
        assert ev._matches_status(200, (200,)) is True
        assert ev._matches_status(401, (200,)) is False

    def test_tuple_status_match(self):
        ev = Events()
        assert ev._matches_status(200, (200, 401)) is True
        assert ev._matches_status(401, (200, 401)) is True
        assert ev._matches_status(500, (200, 401)) is False

    def test_range_status_match(self):
        """range(200, 300) gets expanded to a tuple, so status matching uses 'in'."""
        ev = Events()
        statuses = tuple(range(200, 300))
        assert ev._matches_status(200, statuses) is True
        assert ev._matches_status(299, statuses) is True
        assert ev._matches_status(300, statuses) is False

    def test_none_matches_all(self):
        ev = Events()
        assert ev._matches_status(999, None) is True


# ============================================================================
# _call_request_handlers
# ============================================================================


class TestCallRequestHandlers:
    def test_calls_on_request(self):
        called = []

        class MyEvents(Events):
            def on_request(self, request, context):
                called.append("on_request")
                return request

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        ctx = EventContext(request=req)
        result = ev._call_request_handlers(req, ctx)
        assert "on_request" in called
        assert isinstance(result, Request)

    def test_calls_matched_handlers(self):
        called = []

        class MyEvents(Events):
            @event_handler("INVITE")
            def on_invite(self, req, resp, ctx):
                called.append("on_invite")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        ctx = EventContext(request=req)
        ev._call_request_handlers(req, ctx)
        assert "on_invite" in called

    def test_does_not_call_unmatched_handlers(self):
        called = []

        class MyEvents(Events):
            @event_handler("REGISTER")
            def on_register(self, req, resp, ctx):
                called.append("on_register")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        ctx = EventContext(request=req)
        ev._call_request_handlers(req, ctx)
        assert "on_register" not in called

    def test_handler_returns_modified_request(self):
        class MyEvents(Events):
            @event_handler("INVITE")
            def on_invite(self, req, resp, ctx):
                new_req = Request(method="INVITE", uri="sip:modified@example.com")
                return new_req

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        ctx = EventContext(request=req)
        result = ev._call_request_handlers(req, ctx)
        assert result.uri == "sip:modified@example.com"

    def test_handler_error_does_not_crash(self):
        class MyEvents(Events):
            @event_handler("INVITE")
            def on_invite(self, req, resp, ctx):
                raise RuntimeError("handler exploded")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        ctx = EventContext(request=req)
        # Should not raise
        result = ev._call_request_handlers(req, ctx)
        assert isinstance(result, Request)


# ============================================================================
# _call_response_handlers
# ============================================================================


class TestCallResponseHandlers:
    def test_calls_on_response(self):
        called = []

        class MyEvents(Events):
            def on_response(self, response, context):
                called.append("on_response")
                return response

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        ctx = EventContext(request=req, response=resp)
        result = ev._call_response_handlers(resp, ctx)
        assert "on_response" in called
        assert isinstance(result, Response)

    def test_calls_matched_handlers(self):
        called = []

        class MyEvents(Events):
            @event_handler("INVITE", status=200)
            def on_invite_ok(self, req, resp, ctx):
                called.append("on_invite_ok")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        ctx = EventContext(request=req, response=resp)
        ev._call_response_handlers(resp, ctx)
        assert "on_invite_ok" in called

    def test_does_not_call_unmatched_status(self):
        called = []

        class MyEvents(Events):
            @event_handler("INVITE", status=401)
            def on_invite_auth(self, req, resp, ctx):
                called.append("on_invite_auth")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        ctx = EventContext(request=req, response=resp)
        ev._call_response_handlers(resp, ctx)
        assert "on_invite_auth" not in called

    def test_handler_returns_modified_response(self):
        class MyEvents(Events):
            @event_handler("INVITE", status=200)
            def on_invite_ok(self, req, resp, ctx):
                return Response(status_code=200, reason_phrase="Modified")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        ctx = EventContext(request=req, response=resp)
        result = ev._call_response_handlers(resp, ctx)
        assert result.reason_phrase == "Modified"

    def test_handler_returns_request_triggers_retry_metadata(self):
        class MyEvents(Events):
            @event_handler("INVITE", status=401)
            def on_auth(self, req, resp, ctx):
                return Request(method="INVITE", uri="sip:retry@example.com")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=401)
        ctx = EventContext(request=req, response=resp)
        ev._call_response_handlers(resp, ctx)
        assert "retry_request" in ctx.metadata
        assert ctx.metadata["retry_request"].uri == "sip:retry@example.com"

    def test_handler_error_does_not_crash(self):
        class MyEvents(Events):
            @event_handler("INVITE", status=200)
            def on_invite_ok(self, req, resp, ctx):
                raise ValueError("boom")

        ev = MyEvents()
        req = Request(method="INVITE", uri="sip:bob@example.com")
        resp = Response(status_code=200)
        ctx = EventContext(request=req, response=resp)
        result = ev._call_response_handlers(resp, ctx)
        assert isinstance(result, Response)
