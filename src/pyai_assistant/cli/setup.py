from __future__ import annotations

import secrets
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from pyai_assistant.config import load_local_config_files, write_dotenv, write_local_config
from pyai_assistant.presets import API_PRESETS, ApiPreset, get_api_preset


class SetupWizard:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.console = Console()
        self.file_config, self.env_values = load_local_config_files(root)

    def run(self) -> None:
        self.console.print(
            Panel(
                "EasyAI 命令行配置向导\n将在当前目录写入 config.yaml 和 .env。",
                title="easyai-setup",
                border_style="cyan",
            )
        )

        preset = self._choose_preset()
        if preset is None:
            self._configure_custom_openai()
        elif preset.name == "ollama":
            self._configure_ollama(preset)
        else:
            self._configure_preset(preset)

        self._configure_domain()
        self._configure_security()
        self._save()
        self.console.print("[green]配置已写入 config.yaml 和 .env[/]")

    def _choose_preset(self) -> Optional[ApiPreset]:
        presets = ["cpl", "deepseek", "openrouter", "openai", "ollama", "custom"]
        self.console.print("可选预设:")
        for index, name in enumerate(presets, start=1):
            if name == "custom":
                description = "自定义 OpenAI-compatible 接口"
            else:
                description = API_PRESETS[name].description
            self.console.print("%s. %s - %s" % (index, name, description))

        choice = Prompt.ask("选择预设编号", default="1")
        mapping = {str(i): name for i, name in enumerate(presets, start=1)}
        selected = mapping.get(choice.strip(), "deepseek")
        return None if selected == "custom" else get_api_preset(selected)

    def _configure_preset(self, preset: ApiPreset) -> None:
        self.file_config["preset"] = preset.name
        self.file_config["provider"] = preset.provider
        self.file_config["base_url"] = preset.base_url
        model = Prompt.ask("模型名", default=str(self.file_config.get("model", preset.default_model)))
        self.file_config["model"] = model
        if preset.api_key_env:
            existing = self.env_values.get(preset.api_key_env, "")
            api_key = Prompt.ask("API Key", password=True, default=existing)
            self.env_values[preset.api_key_env] = api_key
            self.env_values.pop("OPENAI_COMPATIBLE_API_KEY", None)

    def _configure_ollama(self, preset: ApiPreset) -> None:
        self.file_config["preset"] = preset.name
        self.file_config["provider"] = "ollama"
        self.file_config["base_url"] = preset.base_url
        self.file_config["ollama_base_url"] = Prompt.ask(
            "Ollama 地址",
            default=str(self.file_config.get("ollama_base_url", preset.base_url)),
        )
        self.file_config["model"] = Prompt.ask(
            "Ollama 模型名",
            default=str(self.file_config.get("model", preset.default_model)),
        )

    def _configure_custom_openai(self) -> None:
        self.file_config["preset"] = "custom"
        self.file_config["provider"] = "openai_compatible"
        self.file_config["base_url"] = Prompt.ask(
            "自定义兼容接口 base_url",
            default=str(self.file_config.get("base_url", "https://example.com/v1")),
        )
        self.file_config["model"] = Prompt.ask(
            "模型名",
            default=str(self.file_config.get("model", "gpt-4o-mini")),
        )
        existing = self.env_values.get("OPENAI_COMPATIBLE_API_KEY", "")
        self.env_values["OPENAI_COMPATIBLE_API_KEY"] = Prompt.ask("API Key", password=True, default=existing)

    def _configure_domain(self) -> None:
        public_url = Prompt.ask(
            "公网访问地址",
            default=str(self.file_config.get("app_base_url", "https://xingkongtech.top")),
        )
        host = Prompt.ask("本机监听地址", default=str(self.file_config.get("host", "127.0.0.1")))
        port = Prompt.ask("本机监听端口", default=str(self.file_config.get("port", 8000)))
        self.file_config["app_base_url"] = public_url
        self.file_config["host"] = host
        self.file_config["port"] = int(port)

        trusted_hosts = {host, "localhost"}
        public_host = public_url.replace("https://", "").replace("http://", "").split("/", 1)[0]
        if public_host:
            trusted_hosts.add(public_host)
        self.file_config["trusted_hosts"] = sorted(trusted_hosts)

    def _configure_security(self) -> None:
        self.file_config["session_cookie_secure"] = Confirm.ask("是否按 HTTPS 安全 Cookie 运行", default=True)
        self.file_config["session_cookie_samesite"] = "Lax"
        self.file_config["csrf_enabled"] = True
        self.file_config["login_rate_limit"] = int(self.file_config.get("login_rate_limit", 10))
        self.file_config["register_rate_limit"] = int(self.file_config.get("register_rate_limit", 5))
        self.file_config["chat_rate_limit"] = int(self.file_config.get("chat_rate_limit", 30))
        self.file_config["rate_limit_window_seconds"] = int(self.file_config.get("rate_limit_window_seconds", 300))
        self.file_config["max_prompt_chars"] = int(self.file_config.get("max_prompt_chars", 4000))
        self.file_config["database_url"] = str(self.file_config.get("database_url", "easyai-data/easyai.json"))
        self.file_config["temperature"] = float(self.file_config.get("temperature", 0.2))
        self.file_config["max_tokens"] = int(self.file_config.get("max_tokens", 1200))
        self.file_config["default_mode"] = str(self.file_config.get("default_mode", "chat"))
        self.file_config["allow_auto_run"] = bool(self.file_config.get("allow_auto_run", False))

        if not self.env_values.get("EASYAI_SECRET_KEY"):
            self.env_values["EASYAI_SECRET_KEY"] = secrets.token_urlsafe(32)

    def _save(self) -> None:
        write_local_config(self.root, self.file_config)
        write_dotenv(self.root, self.env_values)


def main() -> None:
    SetupWizard(Path.cwd()).run()
