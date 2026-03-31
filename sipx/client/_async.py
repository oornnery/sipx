"""Asynchronous SIP Client implementation."""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from ..models._auth import SipAuthCredentials
from .._events import Events
from ..models._message import Response
from ._sync import Client


class AsyncClient:
    """
    Asynchronous SIP client.

    Wraps the sync Client and runs all blocking I/O in a thread pool
    via ``asyncio.to_thread``. Same API as Client but with ``await``.

    Example::

        async with AsyncClient() as client:
            client.auth = ("alice", "secret")
            r = await client.register("sip:alice@pbx.com")
            r = await client.invite("sip:bob@pbx.com", body=sdp)
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 0,
        transport: str = "UDP",
        events: Optional[Events] = None,
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
    ):
        self._sync = Client(
            local_host=local_host,
            local_port=local_port,
            transport=transport,
            events=events,
            auth=auth,
            auto_auth=auto_auth,
        )
        self._reregister_task: Optional[asyncio.Task] = None

    # --- Properties (delegate to sync client) ---

    @property
    def events(self) -> Optional[Events]:
        return self._sync.events

    @events.setter
    def events(self, v):
        self._sync.events = v

    @property
    def auth(self):
        return self._sync.auth

    @auth.setter
    def auth(self, v):
        self._sync.auth = v

    @property
    def local_address(self):
        return self._sync.local_address

    @property
    def is_closed(self):
        return self._sync.is_closed

    @property
    def transport(self):
        return self._sync.transport

    # --- Async SIP methods (delegate to sync via to_thread) ---

    async def request(self, method, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.request, method, uri, **kwargs)

    async def invite(self, to_uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.invite, to_uri, **kwargs)

    async def register(self, aor, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.register, aor, **kwargs)

    async def options(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.options, uri, **kwargs)

    async def ack(self, **kwargs) -> None:
        return await asyncio.to_thread(self._sync.ack, **kwargs)

    async def bye(self, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.bye, **kwargs)

    async def cancel(self, response, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.cancel, response, **kwargs)

    async def message(self, to_uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.message, to_uri, **kwargs)

    async def subscribe(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.subscribe, uri, **kwargs)

    async def notify(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.notify, uri, **kwargs)

    async def refer(self, uri, refer_to, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.refer, uri, refer_to, **kwargs)

    async def info(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.info, uri, **kwargs)

    async def update(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.update, uri, **kwargs)

    async def prack(self, response, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.prack, response, **kwargs)

    async def publish(self, uri, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.publish, uri, **kwargs)

    async def retry_with_auth(self, response, auth=None) -> Optional[Response]:
        return await asyncio.to_thread(self._sync.retry_with_auth, response, auth)

    async def unregister(self, aor, **kwargs) -> Response:
        return await asyncio.to_thread(self._sync.unregister, aor, **kwargs)

    # --- Auto re-registration (async) ---

    def enable_auto_reregister(self, aor, interval, callback=None):
        self._sync._reregister_aor = aor
        self._sync._reregister_interval = interval
        self._sync._reregister_callback = callback
        if self._reregister_task:
            self._reregister_task.cancel()
        self._reregister_task = asyncio.create_task(self._reregister_loop())

    def disable_auto_reregister(self):
        if self._reregister_task:
            self._reregister_task.cancel()
            self._reregister_task = None
        self._sync.disable_auto_reregister()

    async def _reregister_loop(self):
        while not self._sync._closed and self._sync._reregister_aor:
            try:
                await asyncio.sleep(self._sync._reregister_interval or 300)
                r = await self.register(
                    aor=self._sync._reregister_aor,
                    expires=(self._sync._reregister_interval or 300) + 30,
                )
                if self._sync._reregister_callback and r:
                    self._sync._reregister_callback(r)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30)

    # --- Lifecycle ---

    async def close(self):
        if self._reregister_task:
            self._reregister_task.cancel()
        self._sync.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    def __repr__(self):
        return f"AsyncClient({self._sync!r})"
