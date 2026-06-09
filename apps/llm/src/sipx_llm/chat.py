from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


ChatCompletionTransport = Callable[[str, dict[str, str], bytes, float], bytes]
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_TIMEOUT = 30.0


class LLMClientError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LLMChatClient:
    """Small OpenAI-compatible chat-completions client."""

    api_key: str
    model: str = DEFAULT_LLM_MODEL
    base_url: str = DEFAULT_LLM_BASE_URL
    timeout: float = DEFAULT_LLM_TIMEOUT
    transport: ChatCompletionTransport | None = None

    @classmethod
    def from_env(
        cls,
        *,
        prefix: str = "SIPX_LLM",
        transport: ChatCompletionTransport | None = None,
    ) -> LLMChatClient:
        api_key = os.getenv(f"{prefix}_API_KEY")
        if not api_key:
            raise ValueError(f"{prefix}_API_KEY is required")
        return cls(
            api_key=api_key,
            base_url=os.getenv(f"{prefix}_BASE_URL", DEFAULT_LLM_BASE_URL),
            model=os.getenv(f"{prefix}_MODEL", DEFAULT_LLM_MODEL),
            timeout=float(os.getenv(f"{prefix}_TIMEOUT", str(DEFAULT_LLM_TIMEOUT))),
            transport=transport,
        )

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.model:
            raise ValueError("model is required")
        if not self.base_url:
            raise ValueError("base_url is required")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 128,
    ) -> str:
        if not prompt:
            raise ValueError("prompt is required")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": _messages(prompt, system),
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        transport = self.transport or _urlopen_transport
        response = await asyncio.to_thread(transport, url, headers, body, self.timeout)
        return _extract_content(response)


def _messages(prompt: str, system: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _urlopen_transport(
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: float,
) -> bytes:
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise LLMClientError(f"LLM HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LLMClientError("LLM request failed") from exc


def _extract_content(response: bytes) -> str:
    try:
        payload: dict[str, Any] = json.loads(response.decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMClientError("LLM response missing assistant content") from exc
    if not isinstance(content, str) or not content:
        raise LLMClientError("LLM response content is empty")
    return content
