from __future__ import annotations

from pyai_assistant.providers.base import ModelProvider
from pyai_assistant.providers.ollama import OllamaProvider
from pyai_assistant.providers.openai_compatible import OpenAICompatibleProvider
from pyai_assistant.types import ProviderName


def build_provider(name: ProviderName) -> ModelProvider:
    if name == "ollama":
        return OllamaProvider()
    return OpenAICompatibleProvider()
