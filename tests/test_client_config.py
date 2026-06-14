"""Tests for Settings creation and merge logic."""

from __future__ import annotations

from sipx.client import AsyncClient
from sipx.config import Settings
from sipx.protocol.auth import AuthDigest


class TestSettingsCreation:
    def test_config_defaults(self):
        cfg = Settings()
        assert cfg.transport == "udp"
        assert cfg.local_host == "0.0.0.0"
        assert cfg.local_port == 0
        assert cfg.timeout == 30.0
        assert cfg.max_message_size == 65535
        assert cfg.user_agent == "sipx/2.0"
        assert cfg.from_uri is None
        assert cfg.contact_uri is None
        assert cfg.headers is None
        assert cfg.params is None
        assert cfg.cookies is None

    def test_config_override_fields(self):
        cfg = Settings(transport="tcp", timeout=60.0, user_agent="custom/1.0")
        assert cfg.transport == "tcp"
        assert cfg.timeout == 60.0
        assert cfg.user_agent == "custom/1.0"
        assert cfg.local_host == "0.0.0.0"

    def test_config_override_dict_fields(self):
        cfg = Settings(headers={"X-Custom": "val"}, params={"foo": "bar"})
        assert cfg.headers == {"X-Custom": "val"}
        assert cfg.params == {"foo": "bar"}


class TestSettingsMerge:
    def test_merge_simple_overrides(self):
        cfg = Settings()
        merged = cfg.merge(timeout=60.0, user_agent="custom/1.0")
        assert merged.timeout == 60.0
        assert merged.user_agent == "custom/1.0"
        assert merged.transport == "udp"
        assert merged.local_host == "0.0.0.0"

    def test_merge_headers(self):
        cfg = Settings(headers={"X-Base": "base"})
        merged = cfg.merge(headers={"X-Extra": "extra"})
        assert merged.headers == {"X-Base": "base", "X-Extra": "extra"}

    def test_merge_params(self):
        cfg = Settings(params={"a": "1"})
        merged = cfg.merge(params={"b": "2"})
        assert merged.params == {"a": "1", "b": "2"}

    def test_merge_cookies(self):
        cfg = Settings(cookies={"session": "abc"})
        merged = cfg.merge(cookies={"track": "xyz"})
        assert merged.cookies == {"session": "abc", "track": "xyz"}

    def test_merge_preserves_defaults_when_no_override(self):
        cfg = Settings(transport="tcp", timeout=45.0)
        merged = cfg.merge(user_agent="other")
        assert merged.transport == "tcp"
        assert merged.timeout == 45.0
        assert merged.user_agent == "other"

    def test_merge_from_clientconfig_instance(self):
        base = Settings(transport="udp", timeout=30.0)
        override = Settings(transport="tcp", timeout=60.0)
        merged = base.merge(override)
        assert merged.transport == "tcp"
        assert merged.timeout == 60.0

    def test_merge_none_values_ignored(self):
        cfg = Settings(timeout=30.0)
        merged = cfg.merge(timeout=None, transport="tls")
        assert merged.timeout == 30.0
        assert merged.transport == "tls"

    def test_merge_dict_fields_override_none_base(self):
        cfg = Settings()
        merged = cfg.merge(headers={"X-Test": "value"})
        assert merged.headers == {"X-Test": "value"}


class TestAsyncClientMergedConfig:
    def test_client_merged_config_returns_tuple(self):
        client = AsyncClient()
        merged, auth = client.merged_config(timeout=60.0)
        assert isinstance(merged, Settings)
        assert merged.timeout == 60.0
        assert auth is None

    def test_client_merged_config_with_auth_override(self):
        client_auth = AuthDigest(username="alice", password="secret")
        client = AsyncClient(auth=client_auth)
        req_auth = AuthDigest(username="bob", password="other")
        merged, auth = client.merged_config(auth=req_auth)
        assert auth is req_auth

    def test_client_merged_config_fallback_auth(self):
        client_auth = AuthDigest(username="alice", password="secret")
        client = AsyncClient(auth=client_auth)
        merged, auth = client.merged_config()
        assert auth is client_auth
