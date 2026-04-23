from __future__ import annotations

from typing import List

from pyai_assistant.agent.prompts import BASE_SYSTEM_PROMPT
from pyai_assistant.providers.factory import build_provider
from pyai_assistant.types import AppConfig, Message


class ChatService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def generate_reply(self, history: List[dict], prompt: str) -> str:
        provider = build_provider(self.config.provider)
        messages = [Message(role="system", content=BASE_SYSTEM_PROMPT)]
        recent_history = history[-12:]
        for item in recent_history:
            role = item["role"]
            if role not in {"user", "assistant"}:
                continue
            messages.append(Message(role=role, content=item["content"]))
        messages.append(Message(role="user", content=prompt[: self.config.max_prompt_chars]))
        return provider.send(messages, self.config.provider_config()).strip()
