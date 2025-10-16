import asyncio
import inspect
from collections import deque
from typing import Awaitable, Callable, Deque, Dict, Tuple
import logging
import socket
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.NOTSET,
    format="%(message)s",
    handlers=[RichHandler(omit_repeated_times=False)]
    )
logger = logging.getLogger('rich')

Addr = Tuple[str, int]
OnMessage = Callable[[str, Addr], Awaitable[None]]

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
            text = data.decode('utf-8', errors='replace')
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
        peer = transport.get_extra_info('peername')
        if isinstance(peer, tuple) and len(peer) >= 2:
            self._peer = (peer[0], peer[1])
        self._stack._register_tcp(self)

    def data_received(self, data):
        self._buffer.extend(data)
        while True:
            # keep-alive handling CRLF (RFC 5626)
            if self._buffer.startswith(b'\r\n\r\n'):
                if self._reply_crlf_keepalive and self._stack:
                    self._stack.write(b'\r\n')
                del self._buffer[:4]
                continue
            if self._buffer.startswith(b'\r\n'):
                del self._buffer[:2]
                continue
            header_marker = self._buffer.find(b'\r\n\r\n')
            if header_marker == -1:
                break
            headers_blob = self._buffer[:header_marker].decode('utf-8', errors='replace')
            content_length = _find_content_length(headers_blob)
            total_needed = header_marker + 4 + max(0, content_length)
            
            if len(self._buffer) < total_needed:
                break
            
            msg_bytes = bytes(self._buffer[:total_needed])
            del self._buffer[:total_needed]
            
            try:
                msg_text = msg_bytes.decode('utf-8', errors='replace')
            except Exception as e:
                logger.error(f"Failed to decode TCP data from {self._peer}: {e}")
                continue
            
            if self._peer:
                asyncio.create_task(self._stack.handle_message(msg_text, self._peer))
            else:
                p = self._stack.get_extra_info('peername') if self._stack else None
                if isinstance(p, tuple) and len(p) >= 2:
                    asyncio.create_task(self._stack.handle_message(msg_text, (p[0], p[1])))

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
    def __init__(self, on_message: Callable[[str, Addr], Awaitable[None]] | None = None):
        self.on_message = on_message
        self._loop = asyncio.get_event_loop()
        
        self._udp_transport: asyncio.transports.DatagramTransport | None = None
        self._udp_protocol: UDP | None = None
        
        self._tcp_server: asyncio.base_events.Server | None = None
        self._tcp_connections: Dict[Addr, TCP] = {}
        self._addr_cache: Dict[Tuple[str, int, int, int], Addr] = {}
        self._pending_udp: Dict[Addr, Deque[asyncio.Future[str]]] = {}
        self._pending_tcp: Dict[Addr, Deque[asyncio.Future[str]]] = {}
    
    async def handle_message(self, message: str, addr: Addr):
        logger.debug(f"Received message from {addr}:\n{message}")
        if self._deliver_response(self._pending_udp, addr, message):
            logger.debug(f"Delivered UDP response to waiter for {addr}")
        elif self._deliver_response(self._pending_tcp, addr, message):
            logger.debug(f"Delivered TCP response to waiter for {addr}")
        if not self.on_message:
            logger.warning("No on_message handler set")
            return
        await self.on_message(message, addr)
        logger.debug(f"Finished processing message from {addr}")

    def _deliver_response(
        self,
        pending: Dict[Addr, Deque[asyncio.Future[str]]],
        addr: Addr,
        message: str,
    ) -> bool:
        queue = pending.get(addr)
        if not queue:
            return False
        while queue:
            future = queue.popleft()
            if future.cancelled():
                continue
            if future.done():
                continue
            future.set_result(message)
            break
        if not queue:
            pending.pop(addr, None)
        else:
            pending[addr] = queue
        return True

    def _discard_future(
        self,
        pending: Dict[Addr, Deque[asyncio.Future[str]]],
        addr: Addr,
        future: asyncio.Future[str],
    ):
        queue = pending.get(addr)
        if not queue:
            return
        try:
            queue.remove(future)
        except ValueError:
            pass
        if not queue:
            pending.pop(addr, None)
        else:
            pending[addr] = queue
    
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
            logger.warning(f"Tried to unregister unknown TCP connection from {conn._peer}")
            return
        del self._tcp_connections[conn._peer]
        logger.info(f"Unregistered TCP connection from {conn._peer}")
    
    async def start_udp(self, local_addr: Addr):
        logger.info(f"Starting UDP on {local_addr}")
        self._udp_protocol = UDP(self)
        kwargs = {
            "local_addr": local_addr,
            "family": socket.AF_INET,
            "proto": socket.IPPROTO_UDP,
            "reuse_port": True,
        }
        if "reuse_address" in inspect.signature(self._loop.create_datagram_endpoint).parameters:
            kwargs["reuse_address"] = True
        self._udp_transport, _ = await self._loop.create_datagram_endpoint(
            lambda: self._udp_protocol,
            **kwargs,
        )
        logger.info(f"UDP server started on {local_addr}")
    
    async def start_tcp(self, local_addr: Addr, backlog: int = 100):
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
        logger.info(f"TCP server started on {local_addr}")
    
    async def start(self, udp_addr: Addr | None = None, tcp_addr: Addr | None = None):
        tasks = []
        if udp_addr:
            tasks.append(self.start_udp(udp_addr))
        if tcp_addr:
            tasks.append(self.start_tcp(tcp_addr))
        await asyncio.gather(*tasks)
    
    async def stop(self):
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
        self._tcp_connections.clear()
        logger.info("All TCP connections closed")
    
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
            raise RuntimeError(f"Failed to establish TCP connection to {addr}: {exc}") from exc

        if not isinstance(protocol, TCP):
            transport.close()
            raise RuntimeError("create_connection returned unexpected protocol instance")

        # connection_made registers the connection, but make sure it exists
        if addr not in self._tcp_connections:
            peer = transport.get_extra_info("peername")
            if isinstance(peer, tuple) and len(peer) >= 2:
                mapped = (peer[0], peer[1])
                if mapped in self._tcp_connections:
                    return self._tcp_connections[mapped]
            raise RuntimeError(f"TCP connection to {addr} did not register correctly")

        return self._tcp_connections[addr]

    async def send_udp(
        self,
        data: str,
        addr: Addr,
        *,
        wait_response: bool = False,
        timeout: float | None = None,
    ) -> str | None:
        logger.debug(f"Sending UDP message to {addr}")
        if not self._udp_transport or not self._udp_protocol:
            raise RuntimeError("UDP transport not started")
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

        future: asyncio.Future[str] | None = None
        if wait_response:
            future = self._loop.create_future()
            self._pending_udp.setdefault(resolved, deque()).append(future)

        try:
            self._udp_protocol.sendto(data, resolved)
        except OSError as exc:
            if future is not None:
                self._discard_future(self._pending_udp, resolved, future)
            raise RuntimeError(f"UDP send to {addr} failed: {exc}") from exc
        logger.debug(f"Sent UDP message to {addr}:\n\n{data}")

        if not wait_response:
            return None

        assert future is not None
        try:
            if timeout is not None:
                return await asyncio.wait_for(future, timeout)
            return await future
        except asyncio.TimeoutError:
            self._discard_future(self._pending_udp, resolved, future)
            raise
        except Exception:
            self._discard_future(self._pending_udp, resolved, future)
            raise
    
    async def send_tcp(
        self,
        data: str,
        addr: Addr,
        *,
        wait_response: bool = False,
        timeout: float | None = None,
    ) -> str | None:
        logger.debug(f"Sending TCP message to {addr}:\n{data}")
        resolved = await self._resolve_addr(addr, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        conn = self._tcp_connections.get(resolved)
        if not conn:
            conn = await self._ensure_tcp_connection(resolved)

        future: asyncio.Future[str] | None = None
        if wait_response:
            future = self._loop.create_future()
            self._pending_tcp.setdefault(resolved, deque()).append(future)

        conn.send(data)
        logger.debug(f"Sent TCP message to {addr}:\n{data}")

        if not wait_response:
            return None

        assert future is not None
        try:
            if timeout is not None:
                return await asyncio.wait_for(future, timeout)
            return await future
        except asyncio.TimeoutError:
            self._discard_future(self._pending_tcp, resolved, future)
            raise
        except Exception:
            self._discard_future(self._pending_tcp, resolved, future)
            raise

async def main():
    import uuid
    
    async def on_message(msg: str, addr: Addr):
        print(f"Received message from {addr}:\n\n{msg}\n")
    
    tr = SIPTransport(on_message=on_message)
    await tr.start(udp_addr=('0.0.0.0', 0), tcp_addr=('0.0.0.0', 0))

    udp_local = tr._udp_transport.get_extra_info("sockname") if tr._udp_transport else ('0.0.0.0', 0)
    addr_from = (udp_local[0], udp_local[1])
    user_to = '1111'
    addr_to = ('demo.mizu-voip.com', 37075)
    
    def gen_msg():
        return (
            f'OPTIONS sip:user@{addr_to[0]}:{addr_to[1]} SIP/2.0\r\n'
            f'Via: SIP/2.0/UDP <{addr_from[0]}:{addr_from[1]}>\r\n'
            f'From: <sip:tester@{addr_from[0]}:{addr_from[1]}>\r\n'
            f'To: <sip:{user_to}@{addr_to[0]}:{addr_to[1]}>\r\n'
            f'Call-ID: {uuid.uuid4()}@{addr_from[0]}\r\n'
            'CSeq: 1 OPTIONS\r\n'
            'Content-Length: 0\r\n'
            '\r\n'
        )
    
    try:
        udp_response = await tr.send_udp(
            gen_msg(),
            addr_to,
            wait_response=True,
            timeout=5,
        )
        if udp_response:
            print(f"UDP response received:\n\n{udp_response}")
    except RuntimeError as exc:
        logger.error(f"UDP send failed: {exc}")
    except asyncio.TimeoutError:
        logger.error("UDP response timed out")

    try:
        tcp_response = await tr.send_tcp(
            gen_msg(),
            addr_to,
            wait_response=True,
            timeout=5,
        )
        if tcp_response:
            print(f"TCP response received:\n\n{tcp_response}")
    except RuntimeError as exc:
        logger.error(f"TCP send failed: {exc}")
    except asyncio.TimeoutError:
        logger.error("TCP response timed out")

    await asyncio.sleep(5)
    await tr.stop()


if __name__ == "__main__":
    asyncio.run(main())