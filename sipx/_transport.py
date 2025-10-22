import asyncio
import inspect
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Deque, Dict, Tuple
import logging
import socket
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.NOTSET,
    format="%(message)s",
    handlers=[RichHandler(omit_repeated_times=False)],
)
logger = logging.getLogger("rich")

Addr = Tuple[str, int]
OnMessage = Callable[[str, Addr], Awaitable[None]]

ResponseFutureResult = tuple[str, datetime]


def _parse_status_line(message: str | None) -> Tuple[int | None, str | None]:
    if not message:
        return None, None
    first_line = message.split("\r\n", 1)[0]
    if not first_line.startswith("SIP/2.0"):
        return None, None
    parts = first_line.split(" ", 2)
    if len(parts) < 2:
        return None, None
    code_part = parts[1]
    if not code_part.isdigit():
        return None, None
    code = int(code_part)
    text = parts[2] if len(parts) > 2 else None
    return code, text


@dataclass(slots=True)
class TransportResponse:
    protocol: str
    target: Addr
    resolved_target: Addr
    request_raw: str
    send_at: datetime
    response_at: datetime | None
    response_raw: str | None
    response_length: int | None
    status_code: int | None
    status_text: str | None
    timed_out: bool
    duration: float | None
    local_addr: Addr | None = None
    response_addr: Addr | None = None
    error: str | None = None


def _find_content_length(raw: str) -> int:
    for line in raw.split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                return int(line.split(":")[1].strip())
            except ValueError:
                return 0
    return 0


class UDP(asyncio.DatagramProtocol):
    def __init__(self, stack):
        self._stack = stack
        self._transport: asyncio.transports.DatagramTransport | None = None

    def connection_made(self, transport):
        self._transport = transport
        logger.info("UDP transport started")

    def datagram_received(self, data, addr):
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to decode UDP data from {addr}: {e}")
            return
        header_end = text.find("\r\n\r\n")
        if header_end != -1:
            headers = text[:header_end]
            cl = _find_content_length(headers)
            body_start = header_end + 4
            if cl > 0:
                expected_end = body_start + cl
                if expected_end <= len(text):
                    text = text[:expected_end]
        asyncio.create_task(self._stack.handle_message(text, addr))

    def error_received(self, exc):
        logger.error(f"Error UDP: {exc}")

    def connection_lost(self, exc):
        logger.info(f"UDP connection closed: {exc}")

    def sendto(self, data: str, addr: Addr):
        if not self._transport:
            raise RuntimeError("UDP transport not started")
        self._transport.sendto(data.encode("utf-8"), addr)


class TCP(asyncio.Protocol):
    def __init__(self, stack):
        self._stack = stack
        self._buffer = bytearray()
        self._transport: asyncio.transports.Transport | None = None
        self._peer: Addr | None = None
        self._closed = False
        self._reply_crlf_keepalive = False

    def connection_made(self, transport):
        self._transport = transport
        logger.info("TCP connection established")
        peer = transport.get_extra_info("peername")
        if isinstance(peer, tuple) and len(peer) >= 2:
            self._peer = (peer[0], peer[1])
        self._stack._register_tcp(self)

    def data_received(self, data):
        self._buffer.extend(data)
        while True:
            # keep-alive handling CRLF (RFC 5626)
            if self._buffer.startswith(b"\r\n\r\n"):
                if self._reply_crlf_keepalive and self._stack:
                    self._stack.write(b"\r\n")
                del self._buffer[:4]
                continue
            if self._buffer.startswith(b"\r\n"):
                del self._buffer[:2]
                continue
            header_marker = self._buffer.find(b"\r\n\r\n")
            if header_marker == -1:
                break
            headers_blob = self._buffer[:header_marker].decode(
                "utf-8", errors="replace"
            )
            content_length = _find_content_length(headers_blob)
            total_needed = header_marker + 4 + max(0, content_length)

            if len(self._buffer) < total_needed:
                break

            msg_bytes = bytes(self._buffer[:total_needed])
            del self._buffer[:total_needed]

            try:
                msg_text = msg_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                logger.error(f"Failed to decode TCP data from {self._peer}: {e}")
                continue

            if self._peer:
                asyncio.create_task(self._stack.handle_message(msg_text, self._peer))
            else:
                p = self._stack.get_extra_info("peername") if self._stack else None
                if isinstance(p, tuple) and len(p) >= 2:
                    asyncio.create_task(
                        self._stack.handle_message(msg_text, (p[0], p[1]))
                    )

    def connection_lost(self, exc):
        logger.info(f"TCP connection lost: {exc}")
        self._closed = True
        self._stack._unregister_tcp(self)

    def send(self, data):
        if not self._transport or self._closed:
            raise RuntimeError("TCP transport not available")
        self._transport.write(data.encode())

    def close(self):
        if self._transport and not self._closed:
            self._transport.close()
            self._closed = True


class SIPTransport:
    def __init__(
        self,
        on_message: Callable[[str, Addr], Awaitable[None]] | None = None,
        protocol: str = "UDP",
    ):
        self.on_message = on_message
        self._loop = asyncio.get_event_loop()

        self._protocol = protocol.upper()
        if self._protocol not in {"UDP", "TCP"}:
            raise ValueError("protocol must be 'UDP' or 'TCP'")

        self._udp_transport: asyncio.transports.DatagramTransport | None = None
        self._udp_protocol: UDP | None = None

        self._tcp_server: asyncio.base_events.Server | None = None
        self._tcp_connections: Dict[Addr, TCP] = {}
        self._addr_cache: Dict[Tuple[str, int, int, int], Addr] = {}
        self._pending: Dict[Addr, Deque[asyncio.Future[ResponseFutureResult]]] = {}
        self._is_running = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
        return False

    async def handle_message(self, message: str, addr: Addr):
        logger.debug(f"Received message from {addr}")
        if self._deliver_response(addr, message):
            logger.debug(f"Delivered response to waiter for {addr}")
        if not self.on_message:
            logger.warning("No on_message handler set")
            return
        await self.on_message(message, addr)
        logger.debug(f"Finished processing message from {addr}")

    def _deliver_response(
        self,
        addr: Addr,
        message: str,
    ) -> bool:
        queue = self._pending.get(addr)
        if not queue:
            return False
        while queue:
            future = queue.popleft()
            if future.cancelled():
                continue
            if future.done():
                continue
            future.set_result((message, datetime.now(timezone.utc)))
            break
        if not queue:
            self._pending.pop(addr, None)
        else:
            self._pending[addr] = queue
        return True

    def _discard_future(
        self,
        addr: Addr,
        future: asyncio.Future[str],
    ):
        queue = self._pending.get(addr)
        if not queue:
            return
        try:
            queue.remove(future)
        except ValueError:
            pass
        if not queue:
            self._pending.pop(addr, None)
        else:
            self._pending[addr] = queue

    def _fail_pending(self, exc: Exception):
        for queue in list(self._pending.values()):
            while queue:
                future = queue.popleft()
                if future.cancelled():
                    continue
                if future.done():
                    continue
                future.set_exception(exc)
        self._pending.clear()

    def _register_tcp(self, conn: TCP):
        logger.debug("Registering new TCP connection")
        if not conn._peer:
            logger.error("Attempted to register TCP connection without peer info")
            return
        self._tcp_connections[conn._peer] = conn
        logger.info(f"Registered TCP connection from {conn._peer}")

    def _unregister_tcp(self, conn: TCP):
        logger.debug("Unregistering TCP connection")
        if not conn._peer:
            logger.error("Attempted to unregister TCP connection without peer info")
            return
        if conn._peer not in self._tcp_connections:
            logger.warning(
                f"Tried to unregister unknown TCP connection from {conn._peer}"
            )
            return
        del self._tcp_connections[conn._peer]
        logger.info(f"Unregistered TCP connection from {conn._peer}")

    async def _start_udp(self, local_addr: Addr):
        logger.info(f"Starting UDP on {local_addr}")
        self._udp_protocol = UDP(self)
        kwargs = {
            "local_addr": local_addr,
            "family": socket.AF_INET,
            "proto": socket.IPPROTO_UDP,
            "reuse_port": True,
        }
        if (
            "reuse_address"
            in inspect.signature(self._loop.create_datagram_endpoint).parameters
        ):
            kwargs["reuse_address"] = True
        self._udp_transport, _ = await self._loop.create_datagram_endpoint(
            lambda: self._udp_protocol,
            **kwargs,
        )
        local_addr = self.local_address() or local_addr
        logger.info(f"UDP server started on {local_addr}")

    async def _start_tcp(self, local_addr: Addr, backlog: int = 100):
        logger.info(f"Starting TCP on {local_addr}")
        kwargs = {
            "host": local_addr[0],
            "port": local_addr[1],
            "family": socket.AF_INET,
            "backlog": backlog,
            "reuse_port": True,
        }
        if "reuse_address" in inspect.signature(self._loop.create_server).parameters:
            kwargs["reuse_address"] = True
        self._tcp_server = await self._loop.create_server(
            lambda: TCP(self),
            **kwargs,
        )
        local_addr = self.local_address() or local_addr
        logger.info(f"TCP server started on {local_addr}")

    async def start(self, local_addr: Addr, backlog: int = 100):
        if self._is_running:
            raise RuntimeError("SIPTransport already started")
        if self._protocol == "UDP":
            await self._start_udp(local_addr)
        else:
            await self._start_tcp(local_addr, backlog)
        self._is_running = True

    async def stop(self):
        if not self._is_running and not any(
            [self._udp_transport, self._tcp_server, self._tcp_connections]
        ):
            self._fail_pending(RuntimeError("SIPTransport stopped"))
            return

        self._is_running = False
        logger.info("Stopping SIPTransport")
        if self._udp_transport:
            self._udp_transport.close()
            self._udp_transport = None
            self._udp_protocol = None
            logger.info("UDP transport closed")

        if self._tcp_server:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
            self._tcp_server = None
            logger.info("TCP server closed")

        for conn in list(self._tcp_connections.values()):
            conn.close()
        if self._tcp_connections:
            logger.info("All TCP connections closed")
        self._tcp_connections.clear()

        self._fail_pending(RuntimeError("SIPTransport stopped"))

    def local_address(self) -> Addr | None:
        if self._protocol == "UDP" and self._udp_transport:
            sockname = self._udp_transport.get_extra_info("sockname")
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                return sockname[0], sockname[1]
        if self._protocol == "TCP" and self._tcp_server:
            sockets = getattr(self._tcp_server, "sockets", None)
            if sockets:
                sockname = sockets[0].getsockname()
                if isinstance(sockname, tuple) and len(sockname) >= 2:
                    return sockname[0], sockname[1]
        return None

    async def _resolve_addr(self, addr: Addr, sock_type: int, proto: int) -> Addr:
        host, port = addr
        cache_key = (host, port, sock_type, proto)
        if cache_key in self._addr_cache:
            return self._addr_cache[cache_key]

        try:
            infos = await self._loop.getaddrinfo(
                host,
                port,
                family=socket.AF_INET,
                type=sock_type,
                proto=proto,
            )
        except socket.gaierror as exc:
            raise RuntimeError(f"Failed to resolve address {addr}: {exc}") from exc

        for _family, _type, _proto, _canonname, sockaddr in infos:
            if len(sockaddr) >= 2:
                resolved = (sockaddr[0], sockaddr[1])
                self._addr_cache[cache_key] = resolved
                return resolved

        raise RuntimeError(f"getaddrinfo returned no usable address for {addr}")

    async def _ensure_tcp_connection(self, addr: Addr):
        if self._protocol != "TCP":
            raise RuntimeError(
                "SIPTransport configured for UDP cannot create TCP connections"
            )
        if addr in self._tcp_connections:
            return self._tcp_connections[addr]

        logger.debug(f"Establishing new TCP connection to {addr}")
        try:
            transport, protocol = await self._loop.create_connection(
                lambda: TCP(self),
                host=addr[0],
                port=addr[1],
                family=socket.AF_INET,
            )
        except OSError as exc:
            raise RuntimeError(
                f"Failed to establish TCP connection to {addr}: {exc}"
            ) from exc

        if not isinstance(protocol, TCP):
            transport.close()
            raise RuntimeError(
                "create_connection returned unexpected protocol instance"
            )

        # connection_made registers the connection, but make sure it exists
        if addr not in self._tcp_connections:
            peer = transport.get_extra_info("peername")
            if isinstance(peer, tuple) and len(peer) >= 2:
                mapped = (peer[0], peer[1])
                if mapped in self._tcp_connections:
                    return self._tcp_connections[mapped]
            raise RuntimeError(f"TCP connection to {addr} did not register correctly")

        return self._tcp_connections[addr]

    async def send(
        self,
        data: str,
        addr: Addr,
        *,
        wait_response: bool = False,
        timeout: float | None = None,
    ) -> TransportResponse:
        if self._protocol == "UDP":
            return await self._send_udp(
                data,
                addr,
                wait_response=wait_response,
                timeout=timeout,
            )
        return await self._send_tcp(
            data,
            addr,
            wait_response=wait_response,
            timeout=timeout,
        )

    async def _send_udp(
        self,
        data: str,
        addr: Addr,
        *,
        wait_response: bool,
        timeout: float | None,
    ) -> TransportResponse:
        logger.debug(f"Sending UDP message to {addr}")
        if self._protocol != "UDP":
            raise RuntimeError(
                "SIPTransport configured for TCP cannot send UDP messages"
            )
        if not self._udp_transport or not self._udp_protocol:
            raise RuntimeError("UDP transport not started")
        send_at = datetime.now(timezone.utc)
        resolved = await self._resolve_addr(addr, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sockname = self._udp_transport.get_extra_info("sockname")
        if (
            isinstance(sockname, tuple)
            and len(sockname) >= 2
            and sockname[0].startswith("127.")
            and not resolved[0].startswith("127.")
        ):
            raise RuntimeError(
                "UDP transport is bound to 127.0.0.1 and cannot reach non-loopback destinations; "
                "bind to 0.0.0.0 or the appropriate interface instead"
            )

        future: asyncio.Future[ResponseFutureResult] | None = None
        if wait_response:
            future = self._loop.create_future()
            self._pending.setdefault(resolved, deque()).append(future)

        error: str | None = None
        try:
            self._udp_protocol.sendto(data, resolved)
        except OSError as exc:
            if future is not None:
                self._discard_future(resolved, future)
            error = f"UDP send to {addr} failed: {exc}"
            logger.error(error)
        else:
            logger.debug(f"Sent UDP message to {addr}")

        response_raw: str | None = None
        response_at: datetime | None = None
        timed_out = False

        if wait_response and error is None:
            assert future is not None
            try:
                if timeout is not None:
                    response_raw, response_at = await asyncio.wait_for(future, timeout)
                else:
                    response_raw, response_at = await future
            except asyncio.TimeoutError:
                self._discard_future(resolved, future)
                logger.debug("UDP response timed out; returning None")
                timed_out = True
            except Exception:
                self._discard_future(resolved, future)
                raise

        response_length = len(response_raw) if response_raw is not None else None
        status_code, status_text = _parse_status_line(response_raw)
        if response_at is not None:
            duration = (response_at - send_at).total_seconds()
        elif timed_out and timeout is not None:
            duration = timeout
        else:
            duration = None

        return TransportResponse(
            protocol="UDP",
            target=addr,
            resolved_target=resolved,
            request_raw=data,
            send_at=send_at,
            response_at=response_at,
            response_raw=response_raw,
            response_length=response_length,
            status_code=status_code,
            status_text=status_text,
            timed_out=timed_out,
            duration=duration,
            local_addr=self.local_address(),
            response_addr=resolved,
            error=error,
        )

    async def _send_tcp(
        self,
        data: str,
        addr: Addr,
        *,
        wait_response: bool,
        timeout: float | None,
    ) -> TransportResponse:
        logger.debug(f"Sending TCP message to {addr}:\n{data}")
        if self._protocol != "TCP":
            raise RuntimeError(
                "SIPTransport configured for UDP cannot send TCP messages"
            )
        resolved = await self._resolve_addr(
            addr, socket.SOCK_STREAM, socket.IPPROTO_TCP
        )
        conn = self._tcp_connections.get(resolved)
        if not conn:
            conn = await self._ensure_tcp_connection(resolved)

        send_at = datetime.now(timezone.utc)

        future: asyncio.Future[ResponseFutureResult] | None = None
        if wait_response:
            future = self._loop.create_future()
            self._pending.setdefault(resolved, deque()).append(future)

        error: str | None = None
        try:
            conn.send(data)
        except Exception as exc:
            if future is not None:
                self._discard_future(resolved, future)
            error = f"TCP send to {addr} failed: {exc}"
            logger.error(error)
        else:
            logger.debug(f"Sent TCP message to {addr}:\n{data}")

        response_raw: str | None = None
        response_at: datetime | None = None
        timed_out = False

        if wait_response and error is None:
            assert future is not None
            try:
                if timeout is not None:
                    response_raw, response_at = await asyncio.wait_for(future, timeout)
                else:
                    response_raw, response_at = await future
            except asyncio.TimeoutError:
                self._discard_future(resolved, future)
                logger.debug("TCP response timed out; returning None")
                timed_out = True
            except Exception:
                self._discard_future(resolved, future)
                raise

        response_length = len(response_raw) if response_raw is not None else None
        status_code, status_text = _parse_status_line(response_raw)
        if response_at is not None:
            duration = (response_at - send_at).total_seconds()
        elif timed_out and timeout is not None:
            duration = timeout
        else:
            duration = None

        local_addr = None
        if conn._transport:
            sockname = conn._transport.get_extra_info("sockname")
            if isinstance(sockname, tuple) and len(sockname) >= 2:
                local_addr = (sockname[0], sockname[1])

        return TransportResponse(
            protocol="TCP",
            target=addr,
            resolved_target=resolved,
            request_raw=data,
            send_at=send_at,
            response_at=response_at,
            response_raw=response_raw,
            response_length=response_length,
            status_code=status_code,
            status_text=status_text,
            timed_out=timed_out,
            duration=duration,
            local_addr=local_addr or self.local_address(),
            response_addr=resolved,
            error=error,
        )


async def main():
    import uuid
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    async def on_message(msg: str, addr: Addr):
        console.print(Panel(msg, title=f"From {addr}"))

    async with (
        SIPTransport(on_message=on_message, protocol="UDP") as tr_udp,
        SIPTransport(on_message=on_message, protocol="TCP") as tr_tcp,
    ):
        await asyncio.gather(
            tr_udp.start(("0.0.0.0", 0)),
            tr_tcp.start(("0.0.0.0", 0)),
        )

        udp_local = tr_udp.local_address() or ("0.0.0.0", 0)
        tcp_local = tr_tcp.local_address() or ("0.0.0.0", 0)
        user_to = "1111"
        addr_to = ("demo.mizu-voip.com", 37075)

        def build_msg(local_addr: Addr, transport: str) -> str:
            host, port = local_addr
            host = host or "0.0.0.0"
            return (
                f"OPTIONS sip:user@{addr_to[0]}:{addr_to[1]} SIP/2.0\r\n"
                f"Via: SIP/2.0/{transport} {host}:{port}\r\n"
                f"From: <sip:tester@{host}:{port}>\r\n"
                f"To: <sip:{user_to}@{addr_to[0]}:{addr_to[1]}>\r\n"
                f"Call-ID: {uuid.uuid4()}@{host}\r\n"
                "CSeq: 1 OPTIONS\r\n"
                "Content-Length: 0\r\n"
                "\r\n"
            )

        udp_response = await tr_udp.send(
            build_msg(udp_local, "UDP"),
            addr_to,
            wait_response=True,
            timeout=5,
        )
        if udp_response.response_raw:
            console.print(Panel(udp_response.response_raw, title="UDP response"))
        console.print(udp_response)

        tcp_response = await tr_tcp.send(
            build_msg(tcp_local, "TCP"),
            addr_to,
            wait_response=True,
            timeout=5,
        )
        if tcp_response.response_raw:
            console.print(Panel(tcp_response.response_raw, title="TCP response"))
        console.print(tcp_response)

        udp_response_timeout = await tr_udp.send(
            build_msg(udp_local, "UDP"),
            ("192.168.1.1", 5060),
            wait_response=True,
            timeout=5,
        )
        if udp_response_timeout.response_raw:
            console.print(
                Panel(udp_response_timeout.response_raw, title="Timeout response")
            )
        console.print(udp_response_timeout)


if __name__ == "__main__":
    asyncio.run(main())
