from __future__ import annotations

import re
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
    install: bool = False
    elevated: bool = False


@dataclass
class DownloadResult:
    message: str
    command: List[str]
    path: Optional[Path] = None


def looks_like_download_request(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    return (
        normalized.startswith("download ")
        or normalized.startswith("install ")
        or normalized.startswith("下载")
        or normalized.startswith("安装")
        or "帮我下载" in normalized
        or "帮我安装" in normalized
    )


def parse_download_request(text: str) -> DownloadRequest:
    normalized = text.strip()
    lowered = normalized.lower()
    install = "安装" in normalized or lowered.startswith("install ")
    elevated = any(token in lowered for token in ["--admin", "--elevated", "administrator", "管理员"])
    query = re.sub(r"^(please\s+)?(download|install)\s+", "", normalized, flags=re.I)
    query = re.sub(r"^(请)?帮我(下载|安装)", "", query)
    query = re.sub(r"^(下载|安装)", "", query)
    query = query.replace("--admin", "").replace("--elevated", "").replace("管理员", "")
    return DownloadRequest(query=query.strip(), install=install, elevated=elevated)


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
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        output = completed.stdout.strip() or completed.stderr.strip()
        if completed.returncode != 0:
            raise RuntimeError(output or "winget search failed.")
        return DownloadResult(message=output, command=command)

    def winget_install(self, query: str, elevated: bool = False) -> DownloadResult:
        package_id = self.resolve_package_id(query)
        command = [
            "winget",
            "install",
            "--id",
            package_id,
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        if elevated:
            powershell_command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Start-Process",
                "winget",
                "-ArgumentList",
                "'install --id %s --accept-package-agreements --accept-source-agreements'" % package_id,
                "-Verb",
                "RunAs",
                "-Wait",
            ]
            subprocess.run(powershell_command, timeout=600)
            return DownloadResult(message="Installer launched with administrator privileges.", command=powershell_command)

        completed = subprocess.run(command, capture_output=True, text=True, timeout=600)
        output = completed.stdout.strip() or completed.stderr.strip()
        if completed.returncode != 0:
            raise RuntimeError(output or "winget install failed.")
        return DownloadResult(message=output or "Install completed.", command=command)

    def _filename_from_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        name = Path(urllib.parse.unquote(parsed.path)).name
        return name or "download.bin"
