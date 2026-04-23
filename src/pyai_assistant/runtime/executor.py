from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

from pyai_assistant.types import RunRequest, RunResult
from pyai_assistant.workspace.manager import WorkspaceManager


BLOCKED_PACKAGE_ACTIONS = {"add", "audit", "create", "dlx", "exec", "install", "link", "publish", "remove", "uninstall"}


class PythonRunner:
    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace

    def run(self, request: RunRequest) -> RunResult:
        command = self._build_command(request)
        completed = subprocess.run(
            command,
            cwd=str(self.workspace.root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return RunResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _build_command(self, request: RunRequest) -> List[str]:
        if request.command_type == "python":
            target_path = self._resolve_existing_target(request.target)
            return [sys.executable, str(target_path)] + request.args

        if request.command_type == "pytest":
            command = [sys.executable, "-m", "pytest"]
            if request.target:
                command.append(str(self._resolve_existing_target(request.target)))
            return command + request.args

        if request.command_type == "node":
            target_path = self._resolve_existing_target(request.target)
            return ["node", str(target_path)] + request.args

        if request.command_type in {"npm", "pnpm", "yarn", "bun"}:
            return self._build_package_command(request)

        raise ValueError("Unsupported command type: %s" % request.command_type)

    def _resolve_existing_target(self, target: str) -> Path:
        if not target:
            raise ValueError("Run target is required.")
        target_path = self.workspace.resolve_path(target)
        if not target_path.exists():
            raise FileNotFoundError(str(target_path))
        return target_path

    def _build_package_command(self, request: RunRequest) -> List[str]:
        parts = [item for item in [request.target] + request.args if item]
        if not parts:
            raise ValueError("Package command requires a target or args.")
        action = parts[0].lower()
        if action in BLOCKED_PACKAGE_ACTIONS:
            raise ValueError("Package manager action is not allowed for validation: %s" % action)
        return [request.command_type] + parts
