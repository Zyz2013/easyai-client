from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


SOFTWARE_ALIASES = {
    "chrome": "Google.Chrome",
    "google chrome": "Google.Chrome",
    "edge": "Microsoft.Edge",
    "vscode": "Microsoft.VisualStudioCode",
    "vs code": "Microsoft.VisualStudioCode",
    "visual studio code": "Microsoft.VisualStudioCode",
    "git": "Git.Git",
    "node": "OpenJS.NodeJS.LTS",
    "nodejs": "OpenJS.NodeJS.LTS",
    "python": "Python.Python.3.12",
    "7zip": "7zip.7zip",
    "7-zip": "7zip.7zip",
    "wechat": "Tencent.WeChat",
    "qq": "Tencent.QQ",
}


@dataclass
class DownloadRequest:
    query: str
    action: str = "download"
    install: bool = False
    elevated: bool = False
    install_dir: Optional[str] = None


@dataclass
class DownloadResult:
    message: str
    command: List[str]
    path: Optional[Path] = None
    already_installed: bool = False


def looks_like_download_request(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    return (
        normalized.startswith("download ")
        or normalized.startswith("install ")
        or normalized.startswith("uninstall ")
        or normalized.startswith("remove ")
        or normalized.startswith("下载")
        or normalized.startswith("安装")
        or normalized.startswith("卸载")
        or normalized.startswith("删除")
        or "帮我下载" in normalized
        or "帮我安装" in normalized
        or "帮我卸载" in normalized
        or "帮我删除" in normalized
    )


def parse_download_request(text: str) -> DownloadRequest:
    normalized = text.strip()
    lowered = normalized.lower()

    action = "download"
    if lowered.startswith("install ") or lowered.startswith("安装") or "帮我安装" in lowered:
        action = "install"
    elif lowered.startswith("uninstall ") or lowered.startswith("remove ") or lowered.startswith("卸载") or lowered.startswith("删除") or "帮我卸载" in lowered or "帮我删除" in lowered:
        action = "uninstall"

    elevated = any(token in lowered for token in ["--admin", "--elevated", "administrator", "管理员"])

    install_dir = None
    if action == "install":
        english_match = re.search(r"\s+to\s+(.+)$", normalized, flags=re.I)
        chinese_match = re.search(r"到\s*(.+)$", normalized)
        target_match = english_match or chinese_match
        if target_match:
            install_dir = target_match.group(1).strip().strip("\"'")
            normalized = normalized[: target_match.start()].strip()

    query = re.sub(r"^(please\s+)?(download|install|uninstall|remove)\s+", "", normalized, flags=re.I)
    query = re.sub(r"^(帮我(下载|安装|卸载|删除))", "", query)
    query = re.sub(r"^(下载|安装|卸载|删除)", "", query)
    query = query.replace("--admin", "").replace("--elevated", "").replace("管理员", "")
    return DownloadRequest(
        query=query.strip(),
        action=action,
        install=(action == "install"),
        elevated=elevated,
        install_dir=install_dir,
    )


class SoftwareDownloader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.download_dir = self.root / "downloads"

    def is_url(self, query: str) -> bool:
        parsed = urllib.parse.urlparse(query)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def download_url(self, url: str) -> DownloadResult:
        if not self.is_url(url):
            raise ValueError("Only http/https URLs can be downloaded directly.")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        filename = self._filename_from_url(url)
        target = (self.download_dir / filename).resolve()
        if self.download_dir not in target.parents and target != self.download_dir:
            raise ValueError("Resolved download path is outside the workspace.")
        urllib.request.urlretrieve(url, target)
        return DownloadResult(message="Downloaded file.", command=["download", url], path=target)

    def resolve_package_id(self, query: str) -> str:
        key = query.strip().lower()
        return SOFTWARE_ALIASES.get(key, query.strip())

    def winget_search(self, query: str) -> DownloadResult:
        command = ["winget", "search", query]
        completed = self._run_process(command, timeout=60)
        output = self._process_output(completed)
        if completed.returncode != 0:
            raise RuntimeError(output or "winget search failed.")
        return DownloadResult(message=output, command=command)

    def is_installed(self, query: str) -> bool:
        package_id = self.resolve_package_id(query)
        command = ["winget", "list", "--id", package_id, "--exact"]
        completed = self._run_process(command, timeout=60)
        output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).lower()
        if completed.returncode == 0 and package_id.lower() in output:
            return True
        return False

    def winget_install(self, query: str, elevated: bool = False, install_dir: Optional[str] = None) -> DownloadResult:
        package_id = self.resolve_package_id(query)
        if self.is_installed(query):
            return DownloadResult(
                message="Software is already installed.",
                command=["winget", "list", "--id", package_id, "--exact"],
                already_installed=True,
            )
        command = [
            "winget",
            "install",
            "--id",
            package_id,
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        target_dir = self._resolve_install_dir(install_dir) if install_dir else None
        if target_dir:
            command.extend(["--location", str(target_dir)])
        if elevated:
            argument_list = "install --id %s --accept-package-agreements --accept-source-agreements" % package_id
            if target_dir:
                argument_list += ' --location "%s"' % str(target_dir)
            powershell_command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Start-Process",
                "winget",
                "-ArgumentList",
                "'%s'" % argument_list,
                "-Verb",
                "RunAs",
                "-Wait",
            ]
            subprocess.run(powershell_command, timeout=600)
            return DownloadResult(message="Installer launched with administrator privileges.", command=powershell_command)

        completed = self._run_process(command, timeout=600)
        output = self._process_output(completed)
        if completed.returncode != 0:
            raise RuntimeError(output or "winget install failed.")
        return DownloadResult(message=output or "Install completed.", command=command)

    def winget_uninstall(self, query: str, elevated: bool = False) -> DownloadResult:
        package_id = self.resolve_package_id(query)
        if not self.is_installed(query):
            return DownloadResult(message="Software is not installed.", command=["winget", "list", "--id", package_id, "--exact"])
        command = ["winget", "uninstall", "--id", package_id, "--exact", "--accept-source-agreements"]
        if elevated:
            argument_list = "uninstall --id %s --exact --accept-source-agreements" % package_id
            powershell_command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Start-Process",
                "winget",
                "-ArgumentList",
                "'%s'" % argument_list,
                "-Verb",
                "RunAs",
                "-Wait",
            ]
            subprocess.run(powershell_command, timeout=600)
            return DownloadResult(message="Uninstaller launched with administrator privileges.", command=powershell_command)

        completed = self._run_process(command, timeout=600)
        output = self._process_output(completed)
        if completed.returncode != 0:
            raise RuntimeError(output or "winget uninstall failed.")
        return DownloadResult(message=output or "Uninstall completed.", command=command)

    def cleanup_residual_files(self, query: str) -> List[Path]:
        cleaned: List[Path] = []
        package_id = self.resolve_package_id(query)
        for root in self._cleanup_roots():
            for name in self._candidate_names(query, package_id):
                target = root / name
                if not target.exists():
                    continue
                if target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)
                cleaned.append(target)
        return cleaned

    def _resolve_install_dir(self, raw_path: str) -> Path:
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            target = (self.root / target).resolve()
        else:
            target = target.resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _filename_from_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        name = Path(urllib.parse.unquote(parsed.path)).name
        return name or "download.bin"

    def _cleanup_roots(self) -> List[Path]:
        candidates = {
            os.environ.get("APPDATA"),
            os.environ.get("LOCALAPPDATA"),
            os.environ.get("PROGRAMDATA"),
            str(Path.home() / "AppData" / "Roaming"),
            str(Path.home() / "AppData" / "Local"),
        }
        return [Path(item) for item in candidates if item and Path(item).exists()]

    def _candidate_names(self, query: str, package_id: str) -> List[str]:
        raw = {query.strip(), package_id.strip()}
        expanded = set()
        for item in raw:
            if not item:
                continue
            expanded.add(item)
            expanded.add(item.replace(".", ""))
            expanded.add(item.replace(".", " "))
            expanded.add(item.split(".")[-1])
        return sorted({item.strip().strip(".") for item in expanded if item.strip().strip(".")}, key=lambda value: (len(value), value.lower()), reverse=True)

    def _run_process(self, command: List[str], timeout: int) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def _process_output(self, completed: subprocess.CompletedProcess) -> str:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return stdout.strip() or stderr.strip()
