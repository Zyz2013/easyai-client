from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from pyai_assistant.types import Message, ProviderConfig


class ModelProvider(ABC):
    @abstractmethod
    def send(self, messages: Iterable[Message], config: ProviderConfig) -> str:
        raise NotImplementedError
