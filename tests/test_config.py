from dataclasses import is_dataclass

from sipx.config import Settings


def test_client_config_defaults():
    cfg = Settings()
    assert cfg.transport == "udp"
    assert cfg.local_host == "0.0.0.0"
    assert cfg.local_port == 0
    assert cfg.timeout == 30.0
    assert cfg.max_message_size == 65535
    assert cfg.user_agent == "sipx/2.0"
    assert cfg.from_uri is None
    assert cfg.contact_uri is None


def test_client_config_override():
    cfg = Settings(transport="tcp", timeout=60.0)
    assert cfg.transport == "tcp"
    assert cfg.timeout == 60.0
    assert cfg.local_host == "0.0.0.0"


def test_client_config_from_uri():
    cfg = Settings(from_uri="sip:alice@example.com")
    assert cfg.from_uri == "sip:alice@example.com"


def test_client_config_contact_uri():
    cfg = Settings(contact_uri="sip:alice@example.com:5060")
    assert cfg.contact_uri == "sip:alice@example.com:5060"


def test_client_config_is_dataclass():
    assert is_dataclass(Settings)
