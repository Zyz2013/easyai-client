from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional


ProviderName = Literal["openai_compatible", "ollama"]
AgentMode = Literal["chat", "code", "edit"]
CommandType = Literal["python", "pytest", "node", "npm", "pnpm", "yarn", "bun"]


@dataclass
class ProviderConfig:
    provider: ProviderName
    model: str
    base_url: str
    api_key: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 1200


@dataclass
class AppConfig:
    preset: Optional[str] = None
    provider: ProviderName = "openai_compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 1200
    allow_auto_run: bool = False
    default_mode: AgentMode = "chat"
    ollama_base_url: str = "http://localhost:11434"
    secret_key: str = "change-me"
    database_url: str = "easyai-data/easyai.json"
    app_base_url: str = "http://127.0.0.1:8000"
    host: str = "127.0.0.1"
    port: int = 8000
    session_cookie_secure: bool = True
    session_cookie_samesite: str = "Lax"
    session_lifetime_minutes: int = 720
    trusted_hosts: List[str] = field(default_factory=lambda: ["127.0.0.1", "localhost"])
    csrf_enabled: bool = True
    login_rate_limit: int = 10
    register_rate_limit: int = 5
    chat_rate_limit: int = 30
    rate_limit_window_seconds: int = 300
    max_prompt_chars: int = 4000

    def provider_config(self) -> ProviderConfig:
        if self.provider == "ollama":
            return ProviderConfig(
                provider="ollama",
                model=self.model,
                base_url=self.ollama_base_url or self.base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return ProviderConfig(
            provider="openai_compatible",
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class WorkspaceChange:
    path: str
    original_text: str
    updated_text: str
    diff_text: str
    intent: str = ""


@dataclass
class RunRequest:
    command_type: CommandType = "python"
    target: str = ""
    args: List[str] = field(default_factory=list)


@dataclass
class AssistantResult:
    message: str
    proposed_changes: List[WorkspaceChange] = field(default_factory=list)
    suggested_run: Optional[RunRequest] = None
    raw_response: Optional[str] = None


@dataclass
class RunResult:
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class SessionState:
    mode: AgentMode = "chat"
    context_files: List[Path] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    pending_result: Optional[AssistantResult] = None
    applied_changes: List[WorkspaceChange] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
