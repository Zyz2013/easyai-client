from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.prompt import Prompt

from pyai_assistant.cli.secret_input import prompt_secret
from pyai_assistant.config import load_config, load_local_config_files, write_dotenv, write_local_config
from pyai_assistant.presets import get_api_preset
from pyai_assistant.providers.http import get_json
from pyai_assistant.types import AppConfig


def has_model_connection(config: AppConfig) -> Tuple[bool, str]:
    if config.provider == "ollama":
        try:
            get_json(config.ollama_base_url.rstrip("/") + "/api/tags", timeout=3)
        except Exception as exc:
            return False, "Ollama is not reachable: %s" % exc
        return True, "Ollama is reachable."

    if not config.api_key:
        return False, "API key is missing."
    if not config.base_url or not config.model:
        return False, "API base URL or model is missing."
    if not config.api_key.isascii() or any(ch.isspace() for ch in config.api_key):
        return False, "API key contains invalid characters."
    return True, "API configuration exists."


def ensure_model_connection(root: Path, console: Console, language: str = "zh") -> AppConfig:
    config = load_config(root)
    connected, reason = has_model_connection(config)
    file_config, env_values = load_local_config_files(root)
    configured_before = bool(file_config.get("model_connection_configured"))
    if configured_before:
        if language == "zh":
            status = "可用" if connected else "不可用"
            message = (
                "检测到旧的模型连接配置。\n"
                "当前状态: %s\n"
                "详情: %s\n\n"
                "是否继续使用旧配置？"
            ) % (status, reason)
            title = "模型连接"
            prompt = "继续使用旧配置"
        else:
            status = "available" if connected else "unavailable"
            message = (
                "An existing model connection was found.\n"
                "Current status: %s\n"
                "Details: %s\n\n"
                "Do you want to keep using the old configuration?"
            ) % (status, reason)
            title = "Model Connection"
            prompt = "Use old configuration"

        console.print(Panel(message, title=title, border_style="yellow"))
        if Confirm.ask(prompt, default=True):
            return config

    if connected and not configured_before:
        return config

    if language == "zh":
        console.print(
            Panel(
                "未检测到可用的 API Key 或本地 Ollama。请选择一种模型连接方式并保存。",
                title="模型连接",
                border_style="yellow",
            )
        )
        provider_choice = Prompt.ask("选择连接方式", choices=["api", "ollama"], default="api")
    else:
        console.print(
            Panel(
                "No usable API key or local Ollama was detected. Choose a model connection. "
                "Save it to continue.",
                title="Model Connection",
                border_style="yellow",
            )
        )
        provider_choice = Prompt.ask("Connection type", choices=["api", "ollama"], default="api")

    if provider_choice == "ollama":
        _configure_ollama(file_config, env_values, language)
    else:
        _configure_api(console, file_config, env_values, language)

    file_config["model_connection_configured"] = True
    write_local_config(root, file_config)
    write_dotenv(root, env_values)
    return load_config(root)


def _configure_api(console: Console, file_config: Dict[str, object], env_values: Dict[str, str], language: str) -> None:
    preset_choice = Prompt.ask(
        "API preset / API 预设" if language == "zh" else "API preset",
        choices=["deepseek", "openrouter", "openai", "custom"],
        default=str(file_config.get("preset", "deepseek")),
    )

    if preset_choice == "custom":
        file_config["preset"] = ""
        file_config["provider"] = "openai_compatible"
        file_config["base_url"] = Prompt.ask("Base URL", default=str(file_config.get("base_url", "")) or "https://api.openai.com/v1")
        file_config["model"] = Prompt.ask("Model", default=str(file_config.get("model", "")) or "gpt-4o-mini")
        env_key = "OPENAI_COMPATIBLE_API_KEY"
    else:
        preset = get_api_preset(preset_choice)
        if not preset:
            raise ValueError("Unsupported preset: %s" % preset_choice)
        file_config["preset"] = preset.name
        file_config["provider"] = preset.provider
        file_config["base_url"] = preset.base_url
        file_config["model"] = Prompt.ask("Model / 模型" if language == "zh" else "Model", default=preset.default_model)
        env_key = preset.api_key_env or "OPENAI_COMPATIBLE_API_KEY"

    existing_key = env_values.get(env_key, "").strip()
    while True:
        api_key = prompt_secret(console, "API Key", default=existing_key, allow_empty=bool(existing_key)).strip()
        if not api_key:
            console.print("[red]%s[/]" % ("API Key 不能为空。" if language == "zh" else "API key is required."))
            continue
        if not api_key.isascii() or any(ch.isspace() for ch in api_key):
            console.print(
                "[red]%s[/]"
                % ("API Key 包含无效字符，请重新输入。" if language == "zh" else "API key contains invalid characters.")
            )
            continue
        env_values[env_key] = api_key
        break


def _configure_ollama(file_config: Dict[str, object], env_values: Dict[str, str], language: str) -> None:
    base_url = Prompt.ask(
        "Ollama URL",
        default=str(file_config.get("ollama_base_url", env_values.get("OLLAMA_BASE_URL", "http://localhost:11434"))),
    )
    model = Prompt.ask("Ollama model / Ollama 模型" if language == "zh" else "Ollama model", default=str(file_config.get("model", "qwen2.5-coder:7b")))
    file_config["preset"] = "ollama"
    file_config["provider"] = "ollama"
    file_config["base_url"] = base_url
    file_config["ollama_base_url"] = base_url
    file_config["model"] = model
    env_values["OLLAMA_BASE_URL"] = base_url
