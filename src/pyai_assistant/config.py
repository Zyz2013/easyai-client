from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

import yaml

from pyai_assistant.presets import get_api_preset
from pyai_assistant.types import AppConfig


def _parse_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def load_local_config_files(root: Path) -> Tuple[Dict[str, object], Dict[str, str]]:
    file_config: Dict[str, object] = {}
    config_path = root / "config.yaml"
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            file_config = loaded
    return file_config, _parse_dotenv(root / ".env")


def write_local_config(root: Path, file_config: Dict[str, object]) -> None:
    config_path = root / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(file_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def write_dotenv(root: Path, env_values: Dict[str, str]) -> None:
    env_path = root / ".env"
    lines = ["%s=%s" % (key, value) for key, value in sorted(env_values.items()) if value != ""]
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_config(root: Path) -> AppConfig:
    file_config, dotenv_values = load_local_config_files(root)

    env = {**dotenv_values, **os.environ}

    preset_name = env.get("EASYAI_PRESET") or file_config.get("preset")
    preset = get_api_preset(str(preset_name)) if preset_name else None

    provider = str(file_config.get("provider", preset.provider if preset else "openai_compatible"))
    base_url = str(file_config.get("base_url", preset.base_url if preset else "https://api.openai.com/v1"))
    model = str(file_config.get("model", preset.default_model if preset else "gpt-4o-mini"))
    temperature = float(file_config.get("temperature", 0.2))
    max_tokens = int(file_config.get("max_tokens", 1200))
    allow_auto_run = bool(file_config.get("allow_auto_run", False))
    default_mode = str(file_config.get("default_mode", "chat"))
    ollama_base_url = str(
        file_config.get("ollama_base_url", env.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    )
    secret_key = str(file_config.get("secret_key", env.get("EASYAI_SECRET_KEY", "change-me")))
    database_url = str(
        file_config.get("database_url", env.get("EASYAI_DATABASE_URL", "easyai-data/easyai.json"))
    )
    app_base_url = str(file_config.get("app_base_url", env.get("EASYAI_APP_BASE_URL", "http://127.0.0.1:8000")))
    host = str(file_config.get("host", env.get("EASYAI_HOST", "127.0.0.1")))
    port = int(file_config.get("port", env.get("EASYAI_PORT", 8000)))
    session_cookie_secure = bool(file_config.get("session_cookie_secure", True))
    session_cookie_samesite = str(file_config.get("session_cookie_samesite", "Lax"))
    session_lifetime_minutes = int(file_config.get("session_lifetime_minutes", 720))
    trusted_hosts_raw = file_config.get("trusted_hosts", [host, "localhost"])
    trusted_hosts = trusted_hosts_raw if isinstance(trusted_hosts_raw, list) else [host, "localhost"]
    csrf_enabled = bool(file_config.get("csrf_enabled", True))
    login_rate_limit = int(file_config.get("login_rate_limit", 10))
    register_rate_limit = int(file_config.get("register_rate_limit", 5))
    chat_rate_limit = int(file_config.get("chat_rate_limit", 30))
    rate_limit_window_seconds = int(file_config.get("rate_limit_window_seconds", 300))
    max_prompt_chars = int(file_config.get("max_prompt_chars", 4000))

    api_key = None
    if preset and preset.api_key_env:
        api_key = env.get(preset.api_key_env)
    if not api_key:
        api_key = env.get("OPENAI_COMPATIBLE_API_KEY") or env.get("OPENAI_API_KEY")
    if provider == "ollama":
        base_url = ollama_base_url

    return AppConfig(
        preset=preset.name if preset else None,
        provider=provider,  # type: ignore[arg-type]
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        allow_auto_run=allow_auto_run,
        default_mode=default_mode,  # type: ignore[arg-type]
        ollama_base_url=ollama_base_url,
        secret_key=secret_key,
        database_url=database_url,
        app_base_url=app_base_url,
        host=host,
        port=port,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        session_lifetime_minutes=session_lifetime_minutes,
        trusted_hosts=[str(item) for item in trusted_hosts],
        csrf_enabled=csrf_enabled,
        login_rate_limit=login_rate_limit,
        register_rate_limit=register_rate_limit,
        chat_rate_limit=chat_rate_limit,
        rate_limit_window_seconds=rate_limit_window_seconds,
        max_prompt_chars=max_prompt_chars,
    )
