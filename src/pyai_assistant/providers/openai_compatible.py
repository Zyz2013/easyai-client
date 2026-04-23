from __future__ import annotations

from typing import Iterable, List

from pyai_assistant.providers.base import ModelProvider
from pyai_assistant.providers.http import HttpError, post_json
from pyai_assistant.types import Message, ProviderConfig


class OpenAICompatibleProvider(ModelProvider):
    def send(self, messages: Iterable[Message], config: ProviderConfig) -> str:
        if not config.api_key:
            raise ValueError("Missing API key for OpenAI-compatible provider.")

        payload = {
            "model": config.model,
            "messages": [{"role": message.role, "content": message.content} for message in list(messages)],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        headers = {"Authorization": "Bearer %s" % config.api_key}
        data = post_json(config.base_url.rstrip("/") + "/chat/completions", payload, headers=headers)
        choices = data.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise HttpError("OpenAI-compatible response missing choices.")
        first = choices[0]
        if not isinstance(first, dict):
            raise HttpError("OpenAI-compatible response has invalid choice.")
        message = first.get("message", {})
        if not isinstance(message, dict):
            raise HttpError("OpenAI-compatible response missing message.")
        content = message.get("content")
        if not isinstance(content, str):
            raise HttpError("OpenAI-compatible response missing content.")
        return content
