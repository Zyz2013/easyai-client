from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateStatus:
    available: bool
    local_revision: str
    remote_revision: str
    message: str = ""
    offline: bool = False
    skipped: bool = False


class GitUpdater:
    def __init__(self, root: Path) -> None:
        self.root = self.discover_root(root)

    @staticmethod
    def discover_root(start: Path) -> Path:
        path = start.resolve()
        if path.is_file():
            path = path.parent
        for candidate in (path, *path.parents):
            if (candidate / ".git").exists():
                return candidate
        return path

    def is_git_install(self) -> bool:
        return (self.root / ".git").exists()

    def check(self) -> UpdateStatus:
        if not self.is_git_install():
            return UpdateStatus(False, "", "", "Not a Git install; automatic update is unavailable.", skipped=True)
        local = self._git(["rev-parse", "HEAD"])
        try:
            self._git(["fetch", "--quiet", "origin", "main"])
        except RuntimeError as exc:
            return UpdateStatus(False, local[:7], "", str(exc), offline=True)
        remote = self._git(["rev-parse", "origin/main"])
        return UpdateStatus(local != remote, local[:7], remote[:7])

    def update(self) -> str:
        self._git(["pull", "--ff-only", "origin", "main"])
        venv_python = self.root / ".venv" / "Scripts" / "python.exe"
        python_executable = str(venv_python) if venv_python.exists() else sys.executable
        completed = self._run_process(
            [python_executable, "-m", "pip", "install", "-e", ".", "--no-build-isolation"],
            timeout=300,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "pip install failed")
        return completed.stdout.strip()

    def _git(self, args: list) -> str:
        completed = self._run_process(
            ["git"] + args,
            timeout=120,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "git command failed")
        return completed.stdout.strip()

    def _run_process(self, command: list, timeout: int) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
