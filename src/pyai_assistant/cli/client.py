from __future__ import annotations

import json
import shlex
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from pyai_assistant.agent.session import AssistantAgent
from pyai_assistant.cli.pet import TerminalPet
from pyai_assistant.config import load_config
from pyai_assistant.providers.factory import build_provider
from pyai_assistant.providers.server_api import (
    ServerApiClient,
    clear_client_session,
    load_client_session,
    save_client_session,
    utc_now,
)
from pyai_assistant.runtime.computer import load_computer_identity
from pyai_assistant.runtime.downloader import SoftwareDownloader, looks_like_download_request, parse_download_request
from pyai_assistant.runtime.executor import PythonRunner
from pyai_assistant.runtime.updater import GitUpdater
from pyai_assistant.types import AssistantResult, RunRequest
from pyai_assistant.workspace.manager import WorkspaceManager


PERMISSION_LEVELS = {"safe", "files", "downloads", "elevated"}
LANGUAGES = {"zh", "en"}

TEXT = {
    "zh": {
        "first_login": "首次登录必须通过服务器验证。",
        "saved_account": "使用本地保存账号:",
        "username": "用户名",
        "password": "密码",
        "login_failed": "服务器登录失败:",
        "login_hint": "如果包含 Cloudflare 1010/403，请确认客户端已更新，或在 Cloudflare 放行 /api/*。",
        "login_saved": "服务器登录验证成功。本地账号已保存，下次启动不需要再次输入密码。",
        "client_stopped": "客户端已停止。",
        "sync_error": "服务端同步错误:",
        "task_received": "收到网页任务",
        "task_completed": "网页任务完成",
        "task_failed": "网页任务失败:",
        "preparing": "正在准备回答。",
        "request_failed": "请求失败。",
        "ready": "已就绪。",
        "command_failed": "命令执行失败:",
        "logout_cleared": "本地保存账号已清除。下次启动需要重新通过服务器登录。",
        "stopped": "客户端已停止。",
        "unknown": "未知命令。输入 /help 查看帮助。",
        "provider_set": "Provider 已设置为",
        "model_set": "模型已设置为",
        "mode_set": "模式已设置为",
        "session_reset": "会话已重置。",
        "permission_current": "当前权限:",
        "permission_confirm": "确认启用高权限模式？管理员操作仍会再次确认。",
        "permission_set": "权限已设置为",
        "permission_error": "当前权限是 {current}。请先运行 /permission {required}。",
        "pet_enabled": "宠物已开启。",
        "pet_disabled": "宠物已关闭。",
        "download_empty": "请指定软件名或 URL。",
        "download_url": "确认下载 URL 到当前工作区 downloads/？",
        "downloaded": "下载完成:",
        "install_confirm": "确认使用 winget 安装 {query}？",
        "admin_confirm": "确认对 {query} 使用管理员权限？",
        "search_confirm": "确认用 winget 搜索 {query}？",
        "no_pending": "没有待应用修改。",
        "no_run": "没有建议运行的验证命令。可用 /run demo.py 或 /run pytest tests。",
        "language_set": "语言已切换为中文。",
        "server": "服务器",
        "user": "用户",
        "computer": "电脑",
        "provider": "模型来源",
        "model": "模型",
        "mode": "模式",
        "permission": "权限",
        "help": "帮助",
        "client_title": "EasyAI 客户端",
        "help_title": "帮助",
        "update_check": "正在检查更新...",
        "update_unavailable": "无法自动检查更新:",
        "update_available": "发现新版本 {local} -> {remote}，是否现在更新？",
        "update_done": "更新完成。请重新打开 EasyAI。",
        "update_failed": "更新失败:",
        "update_none": "已是最新版本。",
    },
    "en": {
        "first_login": "First login requires server verification.",
        "saved_account": "Using saved local account:",
        "username": "Username",
        "password": "Password",
        "login_failed": "Server login failed:",
        "login_hint": "If it contains Cloudflare 1010/403, make sure the client is updated or allow /api/* in Cloudflare.",
        "login_saved": "Server login verified. Local account saved for next startup.",
        "client_stopped": "Client stopped.",
        "sync_error": "Server sync error:",
        "task_received": "Web task received",
        "task_completed": "Web task completed",
        "task_failed": "Web task failed:",
        "preparing": "Preparing answer.",
        "request_failed": "Request failed.",
        "ready": "Ready.",
        "command_failed": "Command failed:",
        "logout_cleared": "Local saved account cleared. Next startup will require server login.",
        "stopped": "Client stopped.",
        "unknown": "Unknown command. Type /help.",
        "provider_set": "Provider set to",
        "model_set": "Model set to",
        "mode_set": "Mode set to",
        "session_reset": "Session reset.",
        "permission_current": "Current permission:",
        "permission_confirm": "Enable elevated mode? Admin actions will still ask again.",
        "permission_set": "Permission set to",
        "permission_error": "Current permission is {current}. Run /permission {required} first.",
        "pet_enabled": "Pet enabled.",
        "pet_disabled": "Pet disabled.",
        "download_empty": "Specify software name or URL.",
        "download_url": "Download URL into workspace downloads/?",
        "downloaded": "Downloaded:",
        "install_confirm": "Install {query} with winget?",
        "admin_confirm": "Use administrator permission for {query}?",
        "search_confirm": "Search {query} with winget?",
        "no_pending": "No pending changes.",
        "no_run": "No suggested run. Use /run demo.py or /run pytest tests.",
        "language_set": "Language switched to English.",
        "server": "Server",
        "user": "User",
        "computer": "Computer",
        "provider": "Provider",
        "model": "Model",
        "mode": "Mode",
        "permission": "Permission",
        "help": "Help",
        "client_title": "EasyAI Client",
        "help_title": "Help",
        "update_check": "Checking for updates...",
        "update_unavailable": "Automatic update check unavailable:",
        "update_available": "Update available {local} -> {remote}. Update now?",
        "update_done": "Update complete. Please restart EasyAI.",
        "update_failed": "Update failed:",
        "update_none": "Already up to date.",
    },
}

HELP_SHORT = """\
Help topics
  /help files       Files/context: list, open, add/remove context, reset
  /help run         Validation: Python, pytest, Node, npm/pnpm/yarn/bun test
  /help pet         Pet: status, on, off
  /help download    Download/install: URL, winget search, confirmed install
  /help account     Server account, provider, model, mode, logout
  /help permission  Permission modes and switching
  /help agent       Status, doctor, init, memory, compact, review, custom commands
  /language zh|en   Switch CLI language

Common flow
  /open <file>
  /mode edit
  /apply
"""

HELP_TOPICS: Dict[str, str] = {
    "files": """\
Files and context
  /files                         List readable code/text files
  /open <file>                   Open and add file context
  /context add <file>            Add context file
  /context remove <file>         Remove context file
  /reset                         Clear session, context, pending changes
""",
    "run": """\
Validation commands
  /run demo.py
  /run python demo.py arg
  /run pytest tests
  /run node index.js
  /run npm test

Safety: no arbitrary shell. Package managers block risky install/add/remove/publish/exec by default.
""",
    "pet": """\
Pet
  /pet
  /pet status
  /pet on
  /pet off
""",
    "download": """\
Download/install
  download Chrome
  install VS Code
  /download chrome
  /download https://example.com/file.exe
  /download chrome --install
  /download chrome --install --admin

Default only downloads into workspace downloads/ or searches winget. Install and admin require confirmation.
""",
    "account": """\
Account/model
  /language zh|en                Switch CLI language
  /permission                    Show current permission mode
  /permission safe               Safe mode: chat + server sync only
  /permission files              Allow file context/edit after confirmation
  /permission downloads          Allow files + downloads/install after confirmation
  /permission elevated           Allow downloads + admin actions after extra confirmation
  /provider openai_compatible
  /provider ollama
  /model <name>
  /mode chat|code|edit
  /logout
  /quit
""",
    "permission": """\
Permission modes
  /permission                    Show current mode
  /permission safe               Chat and server sync only
  /permission files              Allow file read/edit/apply and validation
  /permission downloads          Allow files plus download/install flows
  /permission elevated           Allow admin install prompts after extra confirmation

Default mode is safe. High-risk actions still ask for confirmation.
""",
    "agent": """\
Agent workspace features
  /status                        Show session, context, account, permission, and server state
  /doctor                        Check Git, config, API key, Ollama hint, and workspace files
  /init                          Create AGENTS.md, .easyai/memory.md, and example custom commands
  /plan <task>                   Ask for an implementation plan without applying changes
  /memory                        Show project memory
  /memory add <text>             Append project memory
  # <text>                       Quick memory append, same as /memory add
  /compact                       Summarize old chat turns and keep recent context
  /review [focus]                Ask for a code-review style pass over loaded context
  /commands                      List .easyai/commands/*.md custom commands
  /<custom> [args]               Run a custom command prompt from .easyai/commands/<custom>.md

Project rule files loaded automatically: AGENTS.md, CLAUDE.md, EASYAI.md, .easyai/memory.md.
""",
}


class EasyAIClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.console = Console()
        self.config = load_config(root)
        self.computer = load_computer_identity(root)
        self.session = load_client_session(root)
        self.api = ServerApiClient(self.config.app_base_url, self.session.get("token"))
        self.workspace = WorkspaceManager(root)
        self.agent = AssistantAgent(build_provider(self.config.provider), self.config, self.workspace)
        self.runner = PythonRunner(self.workspace)
        self.downloader = SoftwareDownloader(root)
        self.updater = GitUpdater(Path(__file__))
        self.pet = TerminalPet()
        self.stop_event = threading.Event()
        self.poller: Optional[threading.Thread] = None
        self.permission = "safe"
        self.language = "zh"
        self.easyai_dir = self.root / ".easyai"
        self.memory_path = self.easyai_dir / "memory.md"
        self.commands_dir = self.easyai_dir / "commands"
        self.audit_path = self.easyai_dir / "audit.log"

    def run(self) -> None:
        self._choose_language()
        self._check_update()
        self._ensure_login()
        self._start_background_client()
        self._render_header()
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]%s@easyai[/] " % self.session.get("username", "user"))
            except (EOFError, KeyboardInterrupt):
                self.stop_event.set()
                self.console.print("\n%s" % self._t("client_stopped"))
                return

            if not user_input.strip():
                continue
            if user_input.lstrip().startswith("#"):
                self._quick_memory(user_input.lstrip()[1:].strip())
                continue
            if user_input.startswith("/"):
                try:
                    if self._handle_command(user_input):
                        self.stop_event.set()
                        return
                except Exception as exc:
                    self.console.print("[red]%s[/] %s" % (self._t("command_failed"), exc))
                continue
            if looks_like_download_request(user_input):
                self._handle_download_text(user_input)
                continue
            self._ask_local_ai(user_input)

    def _choose_language(self) -> None:
        saved = str(self.session.get("language", "")).lower()
        if saved in LANGUAGES:
            self.language = saved
            return
        choice = Prompt.ask("Language / 语言", choices=["zh", "en"], default="zh")
        self.language = choice
        self.session["language"] = choice
        save_client_session(self.root, self.session)

    def _t(self, key: str, **kwargs: object) -> str:
        value = TEXT[self.language][key]
        return value.format(**kwargs) if kwargs else value

    def _check_update(self) -> None:
        self.console.print(self._t("update_check"))
        try:
            status = self.updater.check()
        except Exception as exc:
            self.console.print("[yellow]%s[/] %s" % (self._t("update_unavailable"), exc))
            return
        if status.offline:
            return
        if status.message:
            self.console.print("[yellow]%s[/] %s" % (self._t("update_unavailable"), status.message))
            return
        if not status.available:
            self.console.print("[green]%s[/]" % self._t("update_none"))
            return
        if Confirm.ask(self._t("update_available", local=status.local_revision, remote=status.remote_revision), default=True):
            try:
                self.updater.update()
            except Exception as exc:
                self.console.print("[red]%s[/] %s" % (self._t("update_failed"), exc))
                return
            self.console.print("[green]%s[/]" % self._t("update_done"))
            raise SystemExit(0)

    def _ensure_login(self) -> None:
        if self.session.get("token"):
            self.api.token = self.session["token"]
            self.console.print("[green]%s[/] %s" % (self._t("saved_account"), self.session.get("username", "user")))
            return
        self.console.print(self._t("first_login"))
        username = Prompt.ask(self._t("username"))
        password = Prompt.ask(self._t("password"), password=True)
        try:
            payload = self.api.login(username, password, self.computer.name)
        except Exception as exc:
            self.console.print("[red]%s[/] %s" % (self._t("login_failed"), exc))
            self.console.print("[yellow]%s[/]" % self._t("login_hint"))
            raise SystemExit(1)
        self.session = {
            "token": payload["token"],
            "username": username,
            "verified_at": utc_now(),
            "server": self.config.app_base_url,
            "language": self.language,
        }
        save_client_session(self.root, self.session)
        self.api.token = payload["token"]
        self.console.print("[green]%s[/]" % self._t("login_saved"))

    def _start_background_client(self) -> None:
        self.poller = threading.Thread(target=self._poll_server_tasks, daemon=True)
        self.poller.start()

    def _poll_server_tasks(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.api.heartbeat(self.computer.uid, self.computer.name)
                payload = self.api.next_task(self.computer.uid)
                task = payload.get("task")
                if task:
                    self._handle_server_task(task)
            except Exception as exc:
                self.console.print("[red]%s[/] %s" % (self._t("sync_error"), exc))
            self.stop_event.wait(5)

    def _handle_server_task(self, task: dict) -> None:
        prompt = str(task["prompt"])
        task_id = int(task["id"])
        self.console.print("[cyan]%s %s.[/] %s" % (self._t("task_received"), task_id, prompt))
        try:
            result = self.agent.ask(prompt)
            self.api.complete_task(task_id, response=result.message)
            self.console.print("[green]%s %s.[/]" % (self._t("task_completed"), task_id))
        except Exception as exc:
            self.api.complete_task(task_id, error=str(exc))
            self.console.print("[red]%s[/] %s" % (self._t("task_failed"), exc))

    def _render_header(self) -> None:
        summary = (
            "{server_label}: {server}\n{user_label}: {user}\n{computer_label}: {computer}\n"
            "{provider_label}: {provider}\n{model_label}: {model}\n{mode_label}: {mode}\n"
            "{permission_label}: {permission}\n{help_label}: /help"
        ).format(
            server_label=self._t("server"),
            server=self.config.app_base_url,
            user_label=self._t("user"),
            user=self.session.get("username", "-"),
            computer_label=self._t("computer"),
            computer=self.computer.name,
            provider_label=self._t("provider"),
            provider=self.config.provider,
            model_label=self._t("model"),
            model=self.config.model,
            mode_label=self._t("mode"),
            mode=self.agent.state.mode,
            permission_label=self._t("permission"),
            permission=self.permission,
            help_label=self._t("help"),
        )
        panel = Panel(summary, title=self._t("client_title"), border_style="blue")
        self.console.print(Columns([panel, self.pet.render()], equal=False, expand=False) if self.pet.enabled else panel)

    def _ask_local_ai(self, prompt: str) -> None:
        try:
            self.pet.set_state("thinking", self._t("preparing"))
            self._render_pet()
            result = self.agent.ask(prompt)
        except Exception as exc:
            self.pet.set_state("error", self._t("request_failed"))
            self._render_pet()
            self.console.print("[red]Error:[/] %s" % exc)
            return
        self._render_result(result)

    def _render_pet(self) -> None:
        if self.pet.enabled:
            self.console.print(self.pet.render())

    def _render_result(self, result: AssistantResult) -> None:
        self.pet.set_state("waiting" if result.proposed_changes else "success", self._t("ready"))
        self._render_pet()
        self.console.print(Panel(result.message or "(no message)", title="Assistant", border_style="green"))
        for change in result.proposed_changes:
            self.console.print(Panel(change.intent or "Proposed change", title=change.path, border_style="yellow"))
            self.console.print(Syntax(change.diff_text or "(no diff)", "diff", theme="ansi_dark"))
        if result.suggested_run:
            self.console.print(
                "[cyan]Suggested run:[/] %s %s %s"
                % (result.suggested_run.command_type, result.suggested_run.target, " ".join(result.suggested_run.args))
            )

    def _handle_command(self, raw_command: str) -> bool:
        parts = shlex.split(raw_command)
        command = parts[0].lower()
        if command in {"/quit", "/exit", "/logout"}:
            if command == "/logout":
                clear_client_session(self.root)
                self.console.print(self._t("logout_cleared"))
            else:
                self.console.print(self._t("stopped"))
            return True
        if command == "/help":
            self._show_help(parts[1] if len(parts) > 1 else "")
            return False
        if command == "/permission":
            self._handle_permission(parts[1:])
            return False
        if command == "/status":
            self._show_status()
            return False
        if command == "/doctor":
            self._show_doctor()
            return False
        if command == "/init":
            self._init_workspace()
            return False
        if command == "/plan":
            self._plan_task(" ".join(parts[1:]).strip())
            return False
        if command == "/memory":
            self._handle_memory(parts[1:])
            return False
        if command == "/compact":
            self._compact_conversation()
            return False
        if command == "/review":
            self._review_context(" ".join(parts[1:]).strip())
            return False
        if command == "/commands":
            self._list_custom_commands()
            return False
        if command == "/language" and len(parts) == 2:
            requested = parts[1].lower()
            if requested not in LANGUAGES:
                raise ValueError("Unsupported language: %s" % requested)
            self.language = requested
            self.session["language"] = requested
            save_client_session(self.root, self.session)
            self.console.print("[green]%s[/]" % self._t("language_set"))
            return False
        if command == "/download":
            self._handle_download_parts(parts[1:])
            return False
        if command == "/pet":
            self._handle_pet(parts[1:])
            return False
        if command == "/provider" and len(parts) == 2:
            self.config.provider = parts[1]  # type: ignore[assignment]
            self.agent.provider = build_provider(self.config.provider)
            self.console.print("[green]%s[/] %s" % (self._t("provider_set"), self.config.provider))
            return False
        if command == "/model" and len(parts) >= 2:
            self.config.model = " ".join(parts[1:])
            self.console.print("[green]%s[/] %s" % (self._t("model_set"), self.config.model))
            return False
        if command == "/mode" and len(parts) == 2:
            self.agent.set_mode(parts[1])  # type: ignore[arg-type]
            self.console.print("[green]%s[/] %s" % (self._t("mode_set"), self.agent.state.mode))
            return False
        if command == "/open" and len(parts) == 2:
            self._require_permission("files")
            self._open_file(parts[1])
            return False
        if command == "/context" and len(parts) >= 3:
            self._require_permission("files")
            self._handle_context(parts[1], parts[2])
            return False
        if command == "/apply":
            self._require_permission("files")
            self._apply_pending()
            return False
        if command == "/run":
            self._require_permission("files")
            self._run_command(parts[1:])
            return False
        if command == "/reset":
            self.agent.reset()
            self.console.print("[green]%s[/]" % self._t("session_reset"))
            return False
        if command == "/files":
            self._require_permission("files")
            self._list_files()
            return False
        if self._handle_custom_command(command, parts[1:]):
            return False
        self.console.print("[yellow]%s[/]" % self._t("unknown"))
        return False

    def _show_help(self, topic: str = "") -> None:
        text = HELP_TOPICS.get(topic.lower().strip(), HELP_SHORT) if topic else HELP_SHORT
        self.console.print(Panel(text.rstrip(), title=self._t("help_title"), border_style="cyan"))

    def _handle_permission(self, args: List[str]) -> None:
        if not args:
            self.console.print(Panel("%s %s" % (self._t("permission_current"), self.permission), title="Permission", border_style="cyan"))
            return
        requested = args[0].lower()
        if requested not in PERMISSION_LEVELS:
            raise ValueError("Unsupported permission mode: %s" % requested)
        if requested == "elevated" and not Confirm.ask(self._t("permission_confirm"), default=False):
            return
        self.permission = requested
        self._audit("permission", {"mode": self.permission})
        self.console.print("[green]%s[/] %s" % (self._t("permission_set"), self.permission))

    def _require_permission(self, required: str) -> None:
        order = {"safe": 0, "files": 1, "downloads": 2, "elevated": 3}
        if order[self.permission] < order[required]:
            raise PermissionError(self._t("permission_error", current=self.permission, required=required))

    def _handle_pet(self, args: List[str]) -> None:
        if not args or args[0] == "status":
            self._render_pet()
            return
        if args[0] == "on":
            self.pet.enabled = True
            self.pet.set_state("idle", self._t("pet_enabled"))
            self._render_pet()
            return
        if args[0] == "off":
            self.pet.enabled = False
            self.console.print("[yellow]%s[/]" % self._t("pet_disabled"))
            return
        raise ValueError("Unsupported pet command: %s" % args[0])

    def _handle_download_text(self, text: str) -> None:
        self._require_permission("downloads")
        request = parse_download_request(text)
        self._perform_download(request.query, request.install, request.elevated)

    def _handle_download_parts(self, args: List[str]) -> None:
        self._require_permission("downloads")
        install = "--install" in args
        elevated = "--admin" in args or "--elevated" in args
        query = " ".join(item for item in args if item not in {"--install", "--admin", "--elevated"}).strip()
        self._perform_download(query, install, elevated)

    def _perform_download(self, query: str, install: bool, elevated: bool) -> None:
        if not query:
            raise ValueError(self._t("download_empty"))
        if self.downloader.is_url(query):
            if Confirm.ask(self._t("download_url"), default=False):
                result = self.downloader.download_url(query)
                self._audit("download", {"query": query, "path": str(result.path)})
                self.console.print("[green]%s[/] %s" % (self._t("downloaded"), result.path))
            return
        if install:
            if elevated:
                self._require_permission("elevated")
            if not Confirm.ask(self._t("install_confirm", query=query), default=False):
                return
            if elevated and not Confirm.ask(self._t("admin_confirm", query=query), default=False):
                return
            result = self.downloader.winget_install(query, elevated=elevated)
            self._audit("install", {"query": query, "elevated": elevated})
            self.console.print(Panel(result.message, title="Install", border_style="green"))
            return
        if Confirm.ask(self._t("search_confirm", query=query), default=True):
            result = self.downloader.winget_search(query)
            self.console.print(Panel(result.message, title="winget Search", border_style="cyan"))

    def _open_file(self, raw_path: str) -> None:
        path = self.agent.add_context_file(raw_path)
        content = path.read_text(encoding="utf-8")
        self.console.print(Panel(str(path.relative_to(self.root)), title="Loaded Context", border_style="cyan"))
        self.console.print(Syntax(content, self.workspace.language_hint(path), theme="ansi_dark", line_numbers=True))

    def _handle_context(self, action: str, raw_path: str) -> None:
        if action == "add":
            path = self.agent.add_context_file(raw_path)
            self.console.print("[green]Added context:[/] %s" % path.relative_to(self.root))
            return
        if action == "remove":
            self.agent.remove_context_file(raw_path)
            self.console.print("[green]Removed context:[/] %s" % raw_path)
            return
        raise ValueError("Unsupported context action: %s" % action)

    def _apply_pending(self) -> None:
        pending = self.agent.state.pending_result
        if not pending or not pending.proposed_changes:
            self.console.print("[yellow]%s[/]" % self._t("no_pending"))
            return
        for change in pending.proposed_changes:
            self.console.print(Syntax(change.diff_text, "diff", theme="ansi_dark"))
            if Confirm.ask("Apply changes to %s?" % change.path, default=False):
                self.workspace.apply_change(change)
                self.agent.state.applied_changes.append(change)
                self._audit("apply", {"path": change.path})
                self.console.print("[green]Applied[/] %s" % change.path)
        if pending.suggested_run and Confirm.ask("Run suggested validation now?", default=False):
            self._execute_run(pending.suggested_run)

    def _run_command(self, args: List[str]) -> None:
        if args:
            self._execute_run(self._parse_run_args(args))
            return
        pending = self.agent.state.pending_result
        if pending and pending.suggested_run and Confirm.ask("Run suggested validation command?", default=False):
            self._execute_run(pending.suggested_run)
            return
        self.console.print("[yellow]%s[/]" % self._t("no_run"))

    def _parse_run_args(self, args: List[str]) -> RunRequest:
        command = args[0].lower()
        if command in {"python", "py"}:
            return RunRequest(command_type="python", target=args[1], args=args[2:])
        if command == "pytest":
            target = args[1] if len(args) >= 2 and not args[1].startswith("-") else ""
            remaining = args[2:] if target else args[1:]
            return RunRequest(command_type="pytest", target=target, args=remaining)
        if command == "node":
            return RunRequest(command_type="node", target=args[1], args=args[2:])
        if command in {"npm", "pnpm", "yarn", "bun"}:
            return RunRequest(command_type=command, target=args[1], args=args[2:])  # type: ignore[arg-type]
        return RunRequest(command_type="python", target=args[0], args=args[1:])

    def _execute_run(self, request: RunRequest) -> None:
        result = self.runner.run(request)
        self._audit("run", {"command": result.command, "exit_code": result.exit_code})
        summary = "Exit code: %s\nCommand: %s" % (result.exit_code, " ".join(result.command))
        self.console.print(Panel(summary, title="Run Result", border_style="magenta"))
        if result.stdout:
            self.console.print(Panel(result.stdout, title="stdout", border_style="green"))
        if result.stderr:
            self.console.print(Panel(result.stderr, title="stderr", border_style="red"))

    def _list_files(self) -> None:
        table = Table(title="Workspace Files")
        table.add_column("Path")
        for path in self.workspace.list_code_files():
            table.add_row(path.relative_to(self.root).as_posix())
        self.console.print(table)

    def _show_status(self) -> None:
        table = Table(title="EasyAI Status")
        table.add_column("Item")
        table.add_column("Value")
        table.add_row("Server", self.config.app_base_url)
        table.add_row("User", str(self.session.get("username", "")))
        table.add_row("Computer", self.computer.name)
        table.add_row("Provider", self.config.provider)
        table.add_row("Model", self.config.model)
        table.add_row("Mode", self.agent.state.mode)
        table.add_row("Permission", self.permission)
        table.add_row("Language", self.language)
        table.add_row("Context files", str(len(self.agent.state.context_files)))
        table.add_row("Pending changes", str(len(self.agent.state.pending_result.proposed_changes) if self.agent.state.pending_result else 0))
        table.add_row("Project memory", "yes" if self.memory_path.exists() else "no")
        self.console.print(table)

    def _show_doctor(self) -> None:
        table = Table(title="EasyAI Doctor")
        table.add_column("Check")
        table.add_column("Result")
        table.add_row("Workspace", str(self.root))
        table.add_row("Git install", "yes" if self.updater.is_git_install() else "no")
        table.add_row("Config file", "yes" if (self.root / "config.yaml").exists() else "no")
        table.add_row("Server URL", self.config.app_base_url)
        table.add_row("API key", "set" if self.config.api_key or self.config.provider == "ollama" else "missing")
        table.add_row("Ollama", self.config.ollama_base_url)
        table.add_row("Files visible", str(len(self.workspace.list_code_files())))
        table.add_row("Rule files", ", ".join(self._existing_rule_files()) or "none")
        self.console.print(table)

    def _init_workspace(self) -> None:
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        agents_path = self.root / "AGENTS.md"
        if not agents_path.exists():
            agents_path.write_text(
                "# Project Instructions\n\n"
                "- Prefer small, maintainable changes.\n"
                "- Explain tradeoffs briefly.\n"
                "- Ask before destructive operations.\n"
                "- Run focused validation after edits when possible.\n",
                encoding="utf-8",
            )
        if not self.memory_path.exists():
            self.memory_path.write_text("# EasyAI Memory\n\n", encoding="utf-8")
        review_command = self.commands_dir / "review.md"
        if not review_command.exists():
            review_command.write_text(
                "Review the loaded context like a senior engineer. Focus on bugs, security, regressions, and missing tests. Args: {{args}}\n",
                encoding="utf-8",
            )
        self._audit("init", {"path": str(self.easyai_dir)})
        self.console.print("[green]Initialized EasyAI workspace files.[/]")

    def _plan_task(self, task: str) -> None:
        if not task:
            raise ValueError("Plan task is empty.")
        prompt = (
            "Create a concise implementation plan for this task. "
            "Do not propose file writes yet. Include risks, validation, and required context. Task: %s" % task
        )
        self._ask_local_ai(prompt)

    def _handle_memory(self, args: List[str]) -> None:
        if not args:
            text = self.memory_path.read_text(encoding="utf-8") if self.memory_path.exists() else "(empty)"
            self.console.print(Panel(text.strip() or "(empty)", title="Project Memory", border_style="cyan"))
            return
        action = args[0].lower()
        if action == "add":
            self._append_memory(" ".join(args[1:]).strip())
            return
        if action == "clear":
            if Confirm.ask("Clear project memory?", default=False):
                self.easyai_dir.mkdir(parents=True, exist_ok=True)
                self.memory_path.write_text("# EasyAI Memory\n\n", encoding="utf-8")
                self._audit("memory.clear", {})
            return
        raise ValueError("Unsupported memory command.")

    def _quick_memory(self, text: str) -> None:
        if not text:
            self.console.print("[yellow]Memory text is empty.[/]")
            return
        self._append_memory(text)

    def _append_memory(self, text: str) -> None:
        if not text:
            raise ValueError("Memory text is empty.")
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_path.exists():
            self.memory_path.write_text("# EasyAI Memory\n\n", encoding="utf-8")
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with self.memory_path.open("a", encoding="utf-8") as handle:
            handle.write("- %s %s\n" % (timestamp, text))
        self._audit("memory.add", {"text": text})
        self.console.print("[green]Memory saved.[/]")

    def _compact_conversation(self) -> None:
        messages = self.agent.state.messages
        if len(messages) <= 6:
            self.console.print("[yellow]Not enough conversation to compact.[/]")
            return
        old_messages = messages[:-4]
        summary_lines = []
        for message in old_messages[-12:]:
            content = message.content.replace("\n", " ").strip()
            summary_lines.append("%s: %s" % (message.role, content[:220]))
        previous = str(self.agent.state.metadata.get("conversation_summary", "")).strip()
        combined = (previous + "\n" if previous else "") + "\n".join(summary_lines)
        self.agent.state.metadata["conversation_summary"] = combined[-5000:]
        self.agent.state.messages = messages[-4:]
        self._audit("compact", {"remaining_messages": len(self.agent.state.messages)})
        self.console.print("[green]Conversation compacted.[/]")

    def _review_context(self, focus: str) -> None:
        self._require_permission("files")
        if not self.agent.state.context_files:
            raise ValueError("Load context first with /open or /context add.")
        prompt = (
            "Review the loaded context. Prioritize concrete bugs, security risks, regressions, and missing tests. "
            "Give file/line references when possible. Focus: %s" % (focus or "general")
        )
        self._ask_local_ai(prompt)

    def _list_custom_commands(self) -> None:
        table = Table(title="Custom Commands")
        table.add_column("Command")
        table.add_column("File")
        for path in sorted(self.commands_dir.glob("*.md")) if self.commands_dir.exists() else []:
            table.add_row("/" + path.stem, path.relative_to(self.root).as_posix())
        if not table.rows:
            table.add_row("(none)", ".easyai/commands/*.md")
        self.console.print(table)

    def _handle_custom_command(self, command: str, args: List[str]) -> bool:
        name = command.lstrip("/")
        if not name or name in {"help", "quit", "exit"}:
            return False
        path = self.commands_dir / ("%s.md" % name)
        if not path.exists():
            return False
        prompt = path.read_text(encoding="utf-8")
        prompt = prompt.replace("{{args}}", " ".join(args))
        self._ask_local_ai(prompt)
        return True

    def _existing_rule_files(self) -> List[str]:
        return [name for name in ("AGENTS.md", "CLAUDE.md", "EASYAI.md", ".easyai/memory.md") if (self.root / name).exists()]

    def _audit(self, action: str, payload: dict) -> None:
        self.easyai_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "action": action,
            "payload": payload,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> None:
    EasyAIClient(Path.cwd()).run()
