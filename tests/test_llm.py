import asyncio
import json
import os

import pytest

from sipx import LLMChatClient, LLMClientError


def test_llm_client_posts_chat_completion_without_leaking_key() -> None:
    captured = {}

    def fake_transport(url, headers, body, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(body.decode("utf-8"))
        captured["timeout"] = timeout
        return b'{"choices":[{"message":{"content":"ok"}}]}'

    client = LLMChatClient(
        api_key="test-key",
        base_url="https://llm.example.test/v1",
        model="test-model",
        transport=fake_transport,
        timeout=3.0,
    )

    result = asyncio.run(
        client.complete(
            "Return ok.",
            system="You are a SIP test assistant.",
            max_tokens=8,
        )
    )

    assert result == "ok"
    assert captured["url"] == "https://llm.example.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["messages"][1]["content"] == "Return ok."
    assert "test-key" not in result


def test_llm_client_rejects_missing_content() -> None:
    def fake_transport(url, headers, body, timeout):
        return b'{"choices":[]}'

    client = LLMChatClient(api_key="test-key", transport=fake_transport)

    with pytest.raises(LLMClientError, match="missing assistant content"):
        asyncio.run(client.complete("Return ok."))


def test_llm_client_builds_from_generic_env(monkeypatch) -> None:
    monkeypatch.setenv("SIPX_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SIPX_LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("SIPX_LLM_MODEL", "test-model")
    monkeypatch.setenv("SIPX_LLM_TIMEOUT", "7.5")

    client = LLMChatClient.from_env()

    assert client.api_key == "test-key"
    assert client.base_url == "https://llm.example.test/v1"
    assert client.model == "test-model"
    assert client.timeout == 7.5


@pytest.mark.skipif(
    not os.getenv("SIPX_LLM_API_KEY"),
    reason="set SIPX_LLM_API_KEY to run live LLM validation",
)
def test_llm_client_live_smoke() -> None:
    client = LLMChatClient.from_env()

    result = asyncio.run(
        client.complete(
            "Reply with exactly: sipx-ok",
            system="Follow the user instruction exactly.",
            max_tokens=16,
        )
    )

    assert "sipx-ok" in result.lower()
