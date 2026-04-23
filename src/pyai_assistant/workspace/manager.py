from __future__ import annotations

import difflib
from pathlib import Path
from typing import Iterable, List

from pyai_assistant.types import WorkspaceChange


SUPPORTED_TEXT_SUFFIXES = {
    ".bat",
    ".c",
    ".cc",
    ".cfg",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".lua",
    ".md",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SUPPORTED_TEXT_NAMES = {
    ".env",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "Makefile",
    "README",
}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "node_modules",
}
MAX_TEXT_FILE_BYTES = 300_000


class WorkspaceManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve_path(self, raw_path: str) -> Path:
        path = (self.root / raw_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Path is outside the workspace.")
        return path

    def list_python_files(self) -> List[Path]:
        return sorted(path for path in self.root.rglob("*.py") if path.is_file())

    def list_code_files(self) -> List[Path]:
        files = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORED_DIRS for part in path.relative_to(self.root).parts):
                continue
            if self.is_supported_text_file(path):
                files.append(path)
        return sorted(files)

    def read_file(self, raw_path: str) -> str:
        path = self.resolve_path(raw_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        self._ensure_supported_text_file(path)
        return path.read_text(encoding="utf-8")

    def build_change(self, raw_path: str, updated_text: str, intent: str = "") -> WorkspaceChange:
        path = self.resolve_path(raw_path)
        self._ensure_supported_text_file(path)
        original_text = path.read_text(encoding="utf-8") if path.exists() else ""
        diff_text = self._diff(path, original_text, updated_text)
        return WorkspaceChange(
            path=str(path.relative_to(self.root)),
            original_text=original_text,
            updated_text=updated_text,
            diff_text=diff_text,
            intent=intent,
        )

    def apply_change(self, change: WorkspaceChange) -> Path:
        path = self.resolve_path(change.path)
        self._ensure_supported_text_file(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(change.updated_text, encoding="utf-8")
        return path

    def snapshot_context(self, files: Iterable[Path]) -> str:
        blocks = []
        for path in files:
            relative = path.relative_to(self.root)
            language = self.language_hint(path)
            blocks.append(
                "FILE: %s\n```%s\n%s\n```"
                % (relative.as_posix(), language, path.read_text(encoding="utf-8"))
            )
        return "\n\n".join(blocks)

    def is_supported_text_file(self, path: Path) -> bool:
        name = path.name
        return name in SUPPORTED_TEXT_NAMES or path.suffix.lower() in SUPPORTED_TEXT_SUFFIXES

    def language_hint(self, path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".")
        if suffix in {"yml", "yaml"}:
            return "yaml"
        if suffix == "ps1":
            return "powershell"
        if suffix == "sh":
            return "bash"
        if suffix:
            return suffix
        return "text"

    def _ensure_supported_text_file(self, path: Path) -> None:
        if not self.is_supported_text_file(path):
            raise ValueError("Only supported text/code files can be used.")
        if path.exists() and path.stat().st_size > MAX_TEXT_FILE_BYTES:
            raise ValueError("File is too large for context or editing.")

    def _diff(self, path: Path, original_text: str, updated_text: str) -> str:
        return "".join(
            difflib.unified_diff(
                original_text.splitlines(keepends=True),
                updated_text.splitlines(keepends=True),
                fromfile=str(path.relative_to(self.root)),
                tofile=str(path.relative_to(self.root)),
            )
        )
