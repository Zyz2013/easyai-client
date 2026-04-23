from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ApiPreset:
    name: str
    provider: str
    base_url: str
    default_model: str
    api_key_env: Optional[str]
    description: str


API_PRESETS: Dict[str, ApiPreset] = {
    "openai": ApiPreset(
        name="openai",
        provider="openai_compatible",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="OpenAI 官方兼容接口",
    ),
    "deepseek": ApiPreset(
        name="deepseek",
        provider="openai_compatible",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        description="DeepSeek 官方兼容接口",
    ),
    "openrouter": ApiPreset(
        name="openrouter",
        provider="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        api_key_env="OPENROUTER_API_KEY",
        description="OpenRouter 统一兼容接口",
    ),
    "ollama": ApiPreset(
        name="ollama",
        provider="ollama",
        base_url="http://localhost:11434",
        default_model="qwen2.5-coder:7b",
        api_key_env=None,
        description="本地 Ollama",
    ),
}


def get_api_preset(name: Optional[str]) -> Optional[ApiPreset]:
    if not name:
        return None
    return API_PRESETS.get(name.strip().lower())
