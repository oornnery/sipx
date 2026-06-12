"""Tests for TlsTransport implementation."""

import asyncio
import ssl
import tempfile
from pathlib import Path

import pytest

from sipx.exceptions import TransportError
from sipx.transport.base import Transport, TransportConfig
from sipx.transport.tls import TlsConfig, TlsTransport


def test_import_tls_transport() -> None:
    from sipx.transport.tls import TlsConfig, TlsTransport

    assert TlsTransport is not None
    assert TlsConfig is not None


def test_tls_transport_is_subclass() -> None:
    assert issubclass(TlsTransport, Transport)


def test_transport_type() -> None:
    config = TransportConfig(local_host="127.0.0.1", local_port=0)
    tls_config = TlsConfig(verify_mode=False, check_hostname=False)
    transport = TlsTransport(config, tls_config)
    assert transport.transport_type == "tls"


def test_tls_config_dataclass() -> None:
    config = TlsConfig(
        certfile=None,
        keyfile=None,
        ca_certs=None,
        verify_mode=True,
        check_hostname=True,
    )
    assert config.verify_mode is True
    assert config.check_hostname is True
    assert config.certfile is None


def test_tls_config_defaults() -> None:
    config = TlsConfig()
    assert config.certfile is None
    assert config.keyfile is None
    assert config.ca_certs is None
    assert config.verify_mode is True
    assert config.check_hostname is True


def test_connect_with_tls() -> None:
    asyncio.run(_test_connect_with_tls())


async def _test_connect_with_tls() -> None:
    cert_file, key_file = _create_self_signed_cert()

    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)

        connected = asyncio.Event()

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            connected.set()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=ssl_context)
        port = server.sockets[0].getsockname()[1]

        config = TransportConfig(local_host="127.0.0.1", local_port=0)
        tls_config = TlsConfig(verify_mode=False, check_hostname=False)
        transport = TlsTransport(config, tls_config)

        await transport.connect(("127.0.0.1", port))

        assert transport.is_connected_to(("127.0.0.1", port))
        assert transport.connected

        await transport.close()
        server.close()
        await server.wait_closed()
    finally:
        Path(cert_file).unlink(missing_ok=True)
        Path(key_file).unlink(missing_ok=True)


def test_send_over_tls() -> None:
    asyncio.run(_test_send_over_tls())


async def _test_send_over_tls() -> None:
    cert_file, key_file = _create_self_signed_cert()

    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)

        received_data = asyncio.Event()
        received_bytes = b""

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            nonlocal received_bytes
            data = await reader.read(1024)
            received_bytes = data
            received_data.set()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=ssl_context)
        port = server.sockets[0].getsockname()[1]

        config = TransportConfig(local_host="127.0.0.1", local_port=0)
        tls_config = TlsConfig(verify_mode=False, check_hostname=False)
        transport = TlsTransport(config, tls_config)

        await transport.send(b"OPTIONS sip:test SIP/2.0\r\n\r\n", ("127.0.0.1", port))

        await asyncio.wait_for(received_data.wait(), timeout=1.0)
        assert received_bytes == b"OPTIONS sip:test SIP/2.0\r\n\r\n"

        await transport.close()
        server.close()
        await server.wait_closed()
    finally:
        Path(cert_file).unlink(missing_ok=True)
        Path(key_file).unlink(missing_ok=True)


def test_receive_over_tls() -> None:
    asyncio.run(_test_receive_over_tls())


async def _test_receive_over_tls() -> None:
    cert_file, key_file = _create_self_signed_cert()

    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)

        message = b"SIP/2.0 200 OK\r\nContent-Length: 4\r\n\r\ntest"

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            writer.write(message)
            await writer.drain()
            await asyncio.sleep(0.1)
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=ssl_context)
        port = server.sockets[0].getsockname()[1]

        config = TransportConfig(local_host="127.0.0.1", local_port=0, timeout=1.0)
        tls_config = TlsConfig(verify_mode=False, check_hostname=False)
        transport = TlsTransport(config, tls_config)

        await transport.connect(("127.0.0.1", port))

        received = []
        async for data, remote in transport.receive():
            received.append((data, remote))
            break

        assert len(received) == 1
        assert received[0][0] == message
        assert received[0][1] == ("127.0.0.1", port)

        await transport.close()
        server.close()
        await server.wait_closed()
    finally:
        Path(cert_file).unlink(missing_ok=True)
        Path(key_file).unlink(missing_ok=True)


def test_close_tls() -> None:
    asyncio.run(_test_close_tls())


async def _test_close_tls() -> None:
    cert_file, key_file = _create_self_signed_cert()

    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await asyncio.sleep(1)
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=ssl_context)
        port = server.sockets[0].getsockname()[1]

        config = TransportConfig(local_host="127.0.0.1", local_port=0)
        tls_config = TlsConfig(verify_mode=False, check_hostname=False)
        transport = TlsTransport(config, tls_config)

        await transport.connect(("127.0.0.1", port))

        assert transport.connected
        await transport.close()
        assert not transport.connected

        server.close()
        await server.wait_closed()
    finally:
        Path(cert_file).unlink(missing_ok=True)
        Path(key_file).unlink(missing_ok=True)


def test_send_after_close_raises() -> None:
    asyncio.run(_test_send_after_close_raises())


async def _test_send_after_close_raises() -> None:
    cert_file, key_file = _create_self_signed_cert()

    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=ssl_context)
        port = server.sockets[0].getsockname()[1]

        config = TransportConfig(local_host="127.0.0.1", local_port=0)
        tls_config = TlsConfig(verify_mode=False, check_hostname=False)
        transport = TlsTransport(config, tls_config)

        await transport.connect(("127.0.0.1", port))
        await transport.close()

        with pytest.raises(TransportError, match="closed"):
            await transport.send(b"test", ("127.0.0.1", port))

        server.close()
        await server.wait_closed()
    finally:
        Path(cert_file).unlink(missing_ok=True)
        Path(key_file).unlink(missing_ok=True)


def test_tls_config_verify_mode_false() -> None:
    config = TlsConfig(verify_mode=False, check_hostname=False)
    transport = TlsTransport(tls_config=config)
    assert transport._ssl_context.verify_mode == ssl.CERT_NONE


def test_tls_config_verify_mode_true() -> None:
    config = TlsConfig(verify_mode=True, check_hostname=False)
    transport = TlsTransport(tls_config=config)
    assert transport._ssl_context.verify_mode == ssl.CERT_REQUIRED


def _create_self_signed_cert() -> tuple[str, str]:
    """Create a temporary self-signed certificate for testing."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.UTC)
    ).not_valid_after(
        datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)
    ).sign(key, hashes.SHA256(), default_backend())

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as cert_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
        cert_path = cert_file.name

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as key_file:
        key_file.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        key_path = key_file.name

    return cert_path, key_path
