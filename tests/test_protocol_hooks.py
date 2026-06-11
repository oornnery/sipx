import asyncio

import pytest

from sipx.models import Request, Response
from sipx.protocol.hooks import EventHooks, run_hooks


# ---------------------------------------------------------------------------
# Hook registration / basic structure
# ---------------------------------------------------------------------------

def test_event_hooks_type_is_dict_of_callable_lists():
    hooks: EventHooks = {
        "request": [lambda req: None],
        "response": [lambda resp, remote: None],
    }
    assert isinstance(hooks, dict)
    assert all(isinstance(v, list) for v in hooks.values())
    assert all(callable(h) for v in hooks.values() for h in v)


# ---------------------------------------------------------------------------
# Hook execution — sync
# ---------------------------------------------------------------------------

def test_run_hooks_executes_sync_hook():
    called = []

    def hook(arg):
        called.append(arg)

    hooks: EventHooks = {"request": [hook]}
    asyncio.run(run_hooks(hooks, "request", "value"))
    assert called == ["value"]


def test_run_hooks_executes_multiple_sync_hooks():
    called = []

    def hook1(arg):
        called.append(("hook1", arg))

    def hook2(arg):
        called.append(("hook2", arg))

    hooks: EventHooks = {"request": [hook1, hook2]}
    asyncio.run(run_hooks(hooks, "request", "x"))
    assert called == [("hook1", "x"), ("hook2", "x")]


# ---------------------------------------------------------------------------
# Hook execution — async
# ---------------------------------------------------------------------------

def test_run_hooks_executes_async_hook():
    called = []

    async def hook(arg):
        called.append(arg)

    hooks: EventHooks = {"response": [hook]}
    asyncio.run(run_hooks(hooks, "response", "value"))
    assert called == ["value"]


def test_run_hooks_executes_mixed_sync_and_async_hooks():
    called = []

    def sync_hook(arg):
        called.append(("sync", arg))

    async def async_hook(arg):
        called.append(("async", arg))

    hooks: EventHooks = {"request": [sync_hook, async_hook]}
    asyncio.run(run_hooks(hooks, "request", "x"))
    assert called == [("sync", "x"), ("async", "x")]


# ---------------------------------------------------------------------------
# Error tolerance
# ---------------------------------------------------------------------------

def test_run_hooks_sync_error_does_not_break_flow():
    called = []

    def bad_hook(arg):
        raise ValueError("boom")

    def good_hook(arg):
        called.append(arg)

    hooks: EventHooks = {"request": [bad_hook, good_hook]}
    asyncio.run(run_hooks(hooks, "request", "x"))
    assert called == ["x"]


def test_run_hooks_async_error_does_not_break_flow():
    called = []

    async def bad_hook(arg):
        raise RuntimeError("async boom")

    async def good_hook(arg):
        called.append(arg)

    hooks: EventHooks = {"response": [bad_hook, good_hook]}
    asyncio.run(run_hooks(hooks, "response", "x"))
    assert called == ["x"]


def test_run_hooks_mixed_errors_do_not_break_flow():
    called = []

    def bad_sync(arg):
        raise ValueError("sync boom")

    async def bad_async(arg):
        raise RuntimeError("async boom")

    def good_sync(arg):
        called.append("good_sync")

    async def good_async(arg):
        called.append("good_async")

    hooks: EventHooks = {
        "provisional": [bad_sync, bad_async, good_sync, good_async],
    }
    asyncio.run(run_hooks(hooks, "provisional", "x"))
    assert called == ["good_sync", "good_async"]


# ---------------------------------------------------------------------------
# Edge cases — empty / missing
# ---------------------------------------------------------------------------

def test_run_hooks_empty_hooks_dict():
    hooks: EventHooks = {}
    asyncio.run(run_hooks(hooks, "request", None))


def test_run_hooks_missing_event_key():
    hooks: EventHooks = {"response": [lambda x: x]}
    asyncio.run(run_hooks(hooks, "request", None))


# ---------------------------------------------------------------------------
# Integration with sipx models
# ---------------------------------------------------------------------------

def test_run_hooks_with_request_and_response_objects():
    req = Request(method="INVITE", uri="sip:bob@example.com", headers={}, body=None)
    resp = Response(status_code=200, reason="OK", headers={}, body=None)

    captured_req = []
    captured_resp = []
    captured_prov = []

    def request_hook(request, remote):
        captured_req.append((request.method, remote))

    def response_hook(response, remote):
        captured_resp.append((response.status_code, remote))

    def provisional_hook(response, remote):
        captured_prov.append((response.status_code, remote))

    hooks: EventHooks = {
        "request": [request_hook],
        "response": [response_hook],
        "provisional": [provisional_hook],
    }

    asyncio.run(run_hooks(hooks, "request", req, ("127.0.0.1", 5060)))
    asyncio.run(run_hooks(hooks, "response", resp, ("127.0.0.1", 5060)))

    prov = Response(status_code=180, reason="Ringing", headers={}, body=None)
    asyncio.run(run_hooks(hooks, "provisional", prov, ("127.0.0.1", 5060)))

    assert captured_req == [("INVITE", ("127.0.0.1", 5060))]
    assert captured_resp == [(200, ("127.0.0.1", 5060))]
    assert captured_prov == [(180, ("127.0.0.1", 5060))]
