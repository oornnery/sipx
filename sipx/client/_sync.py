"""Synchronous SIP Client implementation."""

from __future__ import annotations

import re
import socket
import threading
from typing import Optional, Union, Callable

from .._utils import logger
from .._types import SIPTimeoutError
from ..models._auth import SipAuthCredentials
from .._events import Events
from ..fsm import StateManager, TimerManager
from ..models._message import Request, Response, MessageParser
from ..transports import TransportConfig
from ._base import (
    SIPClientBase,
    ForkTracker,
    _ack_and_bye_forked,
    _create_sync_transport,
    _ensure_required_headers,
)


class SIPClient(SIPClientBase):
    """
    Synchronous SIP client with simplified API.

    Inherits shared business logic (properties, header building,
    SIP method helpers) from :class:`SIPClientBase`.

    Example:
        >>> with SIPClient() as client:
        ...     client.auth = ("alice", "secret")
        ...     response = client.invite('sip:bob@example.com')
    """

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        transport: str = "UDP",
        events: Optional[Events] = None,
        auth: Optional[Union[SipAuthCredentials, tuple]] = None,
        auto_auth: bool = True,
        auto_dns: bool = True,
        fork_policy: str = "first",
    ) -> None:
        config = TransportConfig(local_host=local_host, local_port=local_port)
        transport_protocol = transport.upper()
        _transport = _create_sync_transport(transport_protocol, config)

        super().__init__(
            config=config,
            transport_protocol=transport_protocol,
            transport=_transport,
            events=events,
            auth=auth,
            auto_auth=auto_auth,
            auto_dns=auto_dns,
            fork_policy=fork_policy,
        )

        self._state_manager = StateManager()

        # Re-registration support (sync: threading.Timer)
        self._reregister_timer: Optional[threading.Timer] = None
        self._reregister_interval: Optional[int] = None
        self._reregister_aor: Optional[str] = None
        self._reregister_callback: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Thin wrappers around standalone helpers (backward compat)
    # ------------------------------------------------------------------

    def _ensure_required_headers(
        self, request: Request, host: str, port: int
    ) -> Request:
        """Ensure all required SIP headers are present."""
        _ensure_required_headers(
            method=request.method,
            uri=request.uri,
            headers=request.headers,
            local_addr=self._transport.local_address,
            transport_protocol=self.transport_protocol,
            auth=self._auth,
        )
        return request

    def retry_with_auth(
        self, response: Response, auth: Optional[SipAuthCredentials] = None
    ) -> Optional[Response]:
        """
        Retry a request with authentication after receiving 401/407.

        This method allows the user to manually handle authentication challenges.
        Unlike automatic retry, this gives full control over when and how to retry.
        """
        request, destination = self._build_auth_retry_request(response, auth=auth)
        if request is None or destination is None:
            return None

        try:
            logger.debug(
                ">>> AUTH RETRY %s (%s -> %s:%s)",
                request.method,
                self._transport.local_address,
                destination.host,
                destination.port,
            )
            logger.debug(request.to_string())

            self._transport.send(request.to_bytes(), destination)

            parser = MessageParser()
            final_response = None

            while True:
                response_data, source = self._transport.receive(
                    timeout=self._transport.config.read_timeout
                )
                final_response, done = self._handle_auth_retry_message(
                    request=request,
                    response_data=response_data,
                    source=source,
                    parser=parser,
                    final_response=final_response,
                )
                if done:
                    break

            return final_response

        except (OSError, SIPTimeoutError, ValueError, re.error) as e:
            logger.error("Auth retry failed: %s", e, exc_info=True)
            return None

    def request(
        self,
        method: str,
        uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        headers: Optional[dict] = None,
        content: Optional[Union[str, bytes]] = None,
        **kwargs,
    ) -> Optional[Response]:
        """
        Send a SIP request and return the response.

        Args:
            method: SIP method (INVITE, REGISTER, etc.)
            uri: Request URI
            host: Destination host (auto-extracted from uri if not provided)
            port: Destination port (default: 5060)
            headers: Optional headers dict
            content: Optional message body
            **kwargs: Additional request parameters

        Returns:
            SIP response, or None if request timed out.
        """
        request, destination, context, transaction = self._prepare_request_message(
            method=method,
            uri=uri,
            host=host,
            port=port,
            headers=headers,
            content=content,
            **kwargs,
        )
        host = destination.host
        port = destination.port

        # Wire up timer manager for automatic retransmissions
        timer_manager = TimerManager()
        transaction.timer_manager = timer_manager
        transaction.transport = self.transport_protocol
        transaction._retransmit_fn = lambda: self._transport.send(
            request.to_bytes(), destination
        )

        # Trigger initial state timers (Timer A/E for retransmission)
        transaction._on_state_change(transaction.state, transaction.state)

        self._log_outgoing_request(method, uri, host, port, request)

        try:
            import time as _time

            # Send request
            self._transport.send(request.to_bytes(), destination)

            # Receive responses with short timeout polling.
            # This allows FSM timers (Timer A/E) to retransmit in background
            # while we wait for a response. Total deadline = Timer B/F (32s).
            parser = MessageParser()
            final_response = None
            deadline = _time.monotonic() + self._transport.config.read_timeout
            poll_interval = 0.1  # 100ms -- responsive to Ctrl+C and FSM timers
            fork_tracker = ForkTracker() if method == "INVITE" else None
            fork_deadline: float | None = None

            while _time.monotonic() < deadline:
                try:
                    response_data, source = self._transport.receive(
                        timeout=poll_interval
                    )
                except (socket.timeout, SIPTimeoutError, OSError):
                    if not self._should_continue_waiting(
                        transaction=transaction,
                        fork_deadline=fork_deadline,
                        now=_time.monotonic(),
                    ):
                        break
                    continue

                response, prack_req = self._process_received_response(
                    request=request,
                    response_data=response_data,
                    source=source,
                    parser=parser,
                    context=context,
                    uri=uri,
                )
                if response is None:
                    continue

                if prack_req is not None:
                    self._transport.send(prack_req.to_bytes(), destination)
                    logger.debug(
                        ">>> Auto PRACK to %s:%s",
                        destination.host,
                        destination.port,
                    )

                self._state_manager.update_transaction(transaction.id, response)

                final_response, fork_deadline, should_break = (
                    self._collect_response_result(
                        method=method,
                        response=response,
                        final_response=final_response,
                        fork_tracker=fork_tracker,
                        fork_deadline=fork_deadline,
                        now=_time.monotonic(),
                    )
                )
                if should_break:
                    break

            final_response, extra_forks = self._resolve_fork_final_response(
                final_response, fork_tracker
            )
            if self._fork_policy == "first" and extra_forks:
                logger.debug(
                    "Forking: %d extra legs detected — auto-ACK+BYE",
                    len(extra_forks),
                )
                for extra in extra_forks:
                    _ack_and_bye_forked(self._transport, extra, destination)

            if final_response is None:
                logger.warning(
                    "Request timed out after %.0fs",
                    self._transport.config.read_timeout,
                )
                return None

            if self._should_auto_retry_auth(final_response):
                retry_result = self.retry_with_auth(final_response)
                if retry_result:
                    final_response = retry_result

            return self._finalize_response(final_response)

        finally:
            # Clean up all timers for this transaction
            timer_manager.cancel_all()

    def ack(
        self,
        response: Optional[Response] = None,
        **kwargs,
    ) -> None:
        """
        Send ACK for INVITE response.

        Args:
            response: The INVITE response to acknowledge (uses tracked dialog if omitted)
            **kwargs: Additional parameters
        """
        ack_request, destination = self._build_ack(response, **kwargs)
        self._transport.send(ack_request.to_bytes(), destination)
        logger.debug(
            ">>> SENDING ACK (%s -> %s:%s)",
            self._transport.local_address,
            destination.host,
            destination.port,
        )
        logger.debug(ack_request.to_string())

    def bye(
        self,
        response: Optional[Response] = None,
        dialog_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[Response]:
        """
        Send BYE request to terminate a call.

        Args:
            response: Previous INVITE response (to extract dialog info)
            dialog_id: Dialog ID (if not using response)
            **kwargs: Additional parameters

        Returns:
            SIP response

        Example:
            >>> invite_response = client.invite('sip:bob@example.com', body=sdp)
            >>> bye_response = client.bye(response=invite_response)
        """
        uri, headers = self._build_bye_headers(response, dialog_id=dialog_id, **kwargs)
        result = self.request(method="BYE", uri=uri, headers=headers, **kwargs)
        self._dialog.clear()
        return result

    def refer_and_wait(
        self,
        uri: str,
        refer_to: str,
        timeout: float = 30.0,
        **kwargs,
    ) -> Request | Response | None:
        """Send REFER and wait for the transfer result via NOTIFY (RFC 3515).

        Sends REFER, then polls for ``NOTIFY Event: refer`` messages until
        the transfer completes (final sipfrag or ``Subscription-State:
        terminated``) or ``timeout`` expires.  Each NOTIFY is automatically
        acknowledged with 200 OK.

        Args:
            uri: Target URI (the transferee, e.g. current call party).
            refer_to: Transfer destination URI.
            timeout: Maximum seconds to wait for a final NOTIFY.
            **kwargs: Extra parameters forwarded to :meth:`refer`.

        Returns:
            The last ``NOTIFY`` :class:`Request` received (its body is the
            sipfrag), or ``None`` on timeout / REFER rejection.

        Example::

            notify = client.refer_and_wait(
                "sip:alice@pbx.com",
                refer_to="sip:carol@pbx.com",
            )
            if notify:
                print(notify.content_text)  # SIP/2.0 200 OK
        """
        import time as _time

        r = self.refer(uri, refer_to, **kwargs)
        if r is None or r.status_code not in (200, 202):
            return r

        from ..session import ReferSubscription
        from ..models._message import MessageParser as _MP

        sub = ReferSubscription(refer_to=refer_to)
        deadline = _time.monotonic() + timeout
        last_notify: Optional[Request] = None

        while _time.monotonic() < deadline:
            try:
                data, src = self._transport.receive(timeout=1.0)
            except (socket.timeout, SIPTimeoutError, OSError):
                continue

            msg = _MP.parse(data)
            if not isinstance(msg, Request) or msg.method != "NOTIFY":
                continue
            if "refer" not in msg.headers.get("Event", "").lower():
                continue

            # Auto-200 OK the NOTIFY
            self._transport.send(msg.ok().to_bytes(), src)
            last_notify = msg
            logger.debug(
                "<<< NOTIFY (refer) body=%r sub_state=%r",
                msg.content_text[:60] if msg.content else "",
                msg.headers.get("Subscription-State", ""),
            )

            sipfrag = msg.content_text if msg.content else ""
            sub_state = msg.headers.get("Subscription-State", "")
            if sub.update(sipfrag, sub_state):
                break

        return last_notify

    def close(self) -> None:
        """Close the transport."""
        if not self._closed:
            self._transport.close()
            self._closed = True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _resolve_dns(self, host: str):
        """Resolve hostname via SIP DNS SRV (lazy init)."""
        if self._resolver is None:
            from ..dns._sync import SipResolver

            self._resolver = SipResolver()
        targets = self._resolver.resolve(host, self.transport_protocol)
        return targets[0] if targets else None

    def enable_auto_reregister(
        self,
        aor: str,
        interval: int,
        callback: Optional[Callable[[Response], None]] = None,
    ) -> None:
        """
        Enable automatic re-registration.

        Args:
            aor: Address of Record to register
            interval: Re-registration interval in seconds (should be < expires)
            callback: Optional callback function called after each registration
                      with the Response object as argument

        Example:
            >>> def on_register(response):
            ...     print(f"Re-registered: {response.status_code}")
            >>> client.enable_auto_reregister(
            ...     aor="sip:alice@domain.com",
            ...     interval=300,  # Re-register every 5 minutes
            ...     callback=on_register
            ... )
        """
        self._reregister_aor = aor
        self._reregister_interval = interval
        self._reregister_callback = callback
        self._schedule_reregister()

    def disable_auto_reregister(self) -> None:
        """
        Disable automatic re-registration.

        Cancels any pending re-registration timer.
        """
        if self._reregister_timer:
            self._reregister_timer.cancel()
            self._reregister_timer = None
        self._reregister_aor = None
        self._reregister_interval = None
        self._reregister_callback = None

    def _schedule_reregister(self) -> None:
        """Schedule the next re-registration."""
        if not self._reregister_interval or not self._reregister_aor:
            return

        # Cancel existing timer
        if self._reregister_timer:
            self._reregister_timer.cancel()

        # Schedule new timer
        self._reregister_timer = threading.Timer(
            self._reregister_interval, self._do_reregister
        )
        self._reregister_timer.daemon = True
        self._reregister_timer.start()

    def _do_reregister(self) -> None:
        """Perform re-registration (called by timer)."""
        if self._closed or not self._reregister_aor:
            return

        try:
            # Calculate expires as interval + buffer (30 seconds)
            expires = self._reregister_interval + 30

            # Send REGISTER
            response = self.register(aor=self._reregister_aor, expires=expires)

            # Handle auth challenge
            if response and response.status_code in (401, 407):
                response = self.retry_with_auth(response)

            # Call callback if provided
            if self._reregister_callback and response:
                try:
                    self._reregister_callback(response)
                except (ValueError, TypeError, RuntimeError, OSError) as e:
                    logger.warning("Re-register callback error: %s", e, exc_info=True)

            # Schedule next re-registration
            if response and response.status_code == 200:
                self._schedule_reregister()
            else:
                logger.warning(
                    "Re-registration failed: %s",
                    response.status_code if response else "No response",
                )
                # Retry after shorter interval on failure
                if self._reregister_interval:
                    retry_timer = threading.Timer(30, self._do_reregister)
                    retry_timer.daemon = True
                    retry_timer.start()

        except (OSError, SIPTimeoutError) as e:
            logger.error("Re-registration error: %s", e, exc_info=True)
            # Retry after shorter interval on error
            if self._reregister_interval:
                retry_timer = threading.Timer(30, self._do_reregister)
                retry_timer.daemon = True
                retry_timer.start()

    def __repr__(self):
        return f"SIPClient(local={self.local_address}, transport={self.transport_protocol})"
