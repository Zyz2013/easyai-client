from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
        self.root = root.resolve()

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
        completed = subprocess.run(
            [str(self.root / ".venv" / "Scripts" / "python.exe"), "-m", "pip", "install", "-e", "."],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "pip install failed")
        return completed.stdout.strip()

    def _git(self, args: list) -> str:
        completed = subprocess.run(
            ["git"] + args,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "git command failed")
        return completed.stdout.strip()
