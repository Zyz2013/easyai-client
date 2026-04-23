from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

from pyai_assistant.agent.prompts import BASE_SYSTEM_PROMPT, mode_prompt
from pyai_assistant.providers.base import ModelProvider
from pyai_assistant.types import (
    AgentMode,
    AppConfig,
    AssistantResult,
    Message,
    RunRequest,
    SessionState,
)
from pyai_assistant.workspace.manager import WorkspaceManager


class AssistantAgent:
    def __init__(
        self,
        provider: ModelProvider,
        config: AppConfig,
        workspace: WorkspaceManager,
        state: Optional[SessionState] = None,
    ) -> None:
        self.provider = provider
        self.config = config
        self.workspace = workspace
        self.state = state or SessionState(mode=config.default_mode)

    def set_mode(self, mode: AgentMode) -> None:
        self.state.mode = mode

    def add_context_file(self, raw_path: str) -> Path:
        path = self.workspace.resolve_path(raw_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        if path not in self.state.context_files:
            self.state.context_files.append(path)
        return path

    def remove_context_file(self, raw_path: str) -> None:
        path = self.workspace.resolve_path(raw_path)
        self.state.context_files = [item for item in self.state.context_files if item != path]

    def reset(self) -> None:
        self.state.messages.clear()
        self.state.context_files.clear()
        self.state.pending_result = None
        self.state.metadata.clear()
        self.state.mode = self.config.default_mode

    def ask(self, user_input: str) -> AssistantResult:
        messages = self._build_messages(user_input)
        raw_response = self.provider.send(messages, self.config.provider_config())
        result = self._parse_response(raw_response)
        result.raw_response = raw_response
        self.state.messages.append(Message(role="user", content=user_input))
        self.state.messages.append(Message(role="assistant", content=result.message))
        self.state.pending_result = result
        return result

    def _build_messages(self, user_input: str) -> List[Message]:
        messages: List[Message] = [
            Message(role="system", content=BASE_SYSTEM_PROMPT),
            Message(role="system", content=mode_prompt(self.state.mode)),
        ]
        if self.state.context_files:
            snapshot = self.workspace.snapshot_context(self.state.context_files)
            messages.append(Message(role="system", content="Current workspace file context:\n\n%s" % snapshot))
        if self.state.pending_result and self.state.pending_result.proposed_changes:
            messages.append(
                Message(
                    role="system",
                    content="There is a pending change proposal. Revise it carefully if the user asks for changes.",
                )
            )
        messages.extend(self.state.messages[-8:])
        messages.append(Message(role="user", content=user_input))
        return messages

    def _parse_response(self, raw_response: str) -> AssistantResult:
        if self.state.mode != "edit":
            return AssistantResult(message=raw_response.strip())

        payload = self._extract_json_payload(raw_response)
        message = str(payload.get("message", "")).strip() or "No message provided."

        changes = []
        proposed_changes = payload.get("proposed_changes", [])
        if isinstance(proposed_changes, list):
            for item in proposed_changes:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                updated_text = item.get("updated_text")
                if not isinstance(path, str) or not isinstance(updated_text, str):
                    continue
                intent = str(item.get("intent", "")).strip()
                changes.append(self.workspace.build_change(path, updated_text, intent=intent))

        suggested_run = None
        raw_run = payload.get("suggested_run")
        allowed_commands = {"python", "pytest", "node", "npm", "pnpm", "yarn", "bun"}
        if isinstance(raw_run, dict) and raw_run.get("command_type") in allowed_commands:
            target = raw_run.get("target")
            args = raw_run.get("args", [])
            if isinstance(target, str) and isinstance(args, list) and all(isinstance(arg, str) for arg in args):
                suggested_run = RunRequest(command_type=raw_run["command_type"], target=target, args=args)  # type: ignore[arg-type]

        return AssistantResult(message=message, proposed_changes=changes, suggested_run=suggested_run)

    def _extract_json_payload(self, raw_response: str) -> dict:
        text = raw_response.strip()
        if text.startswith("```"):
            match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
            if match:
                text = match.group(1)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("Model returned invalid JSON in edit mode: %s" % exc)
        if not isinstance(payload, dict):
            raise ValueError("Model returned a non-object JSON payload in edit mode.")
        return payload
