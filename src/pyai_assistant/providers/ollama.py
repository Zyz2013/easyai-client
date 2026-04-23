from __future__ import annotations

from typing import Iterable

from pyai_assistant.providers.base import ModelProvider
from pyai_assistant.providers.http import HttpError, post_json
from pyai_assistant.types import Message, ProviderConfig


class OllamaProvider(ModelProvider):
    def send(self, messages: Iterable[Message], config: ProviderConfig) -> str:
        payload = {
            "model": config.model,
            "messages": [{"role": message.role, "content": message.content} for message in list(messages)],
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
            },
        }
        data = post_json(config.base_url.rstrip("/") + "/api/chat", payload)
        message = data.get("message", {})
        if not isinstance(message, dict):
            raise HttpError("Ollama response missing message.")
        content = message.get("content")
        if not isinstance(content, str):
            raise HttpError("Ollama response missing content.")
        return content
