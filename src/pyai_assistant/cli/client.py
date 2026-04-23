from __future__ import annotations

import shlex
import threading
import time
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
from pyai_assistant.types import AssistantResult, RunRequest
from pyai_assistant.workspace.manager import WorkspaceManager


PERMISSION_LEVELS = {"safe", "files", "downloads", "elevated"}

HELP_SHORT = """\
Help topics
  /help files       Files/context: list, open, add/remove context, reset
  /help run         Validation: Python, pytest, Node, npm/pnpm/yarn/bun test
  /help pet         Pet: status, on, off
  /help download    Download/install: URL, winget search, confirmed install
  /help account     Server account, provider, model, mode, logout
  /help permission  Permission modes and switching

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
        self.pet = TerminalPet()
        self.stop_event = threading.Event()
        self.poller: Optional[threading.Thread] = None
        self.permission = "safe"

    def run(self) -> None:
        self._ensure_login()
        self._start_background_client()
        self._render_header()
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]%s@easyai[/] " % self.session.get("username", "user"))
            except (EOFError, KeyboardInterrupt):
                self.stop_event.set()
                self.console.print("\nClient stopped.")
                return

            if not user_input.strip():
                continue
            if user_input.startswith("/"):
                try:
                    if self._handle_command(user_input):
                        self.stop_event.set()
                        return
                except Exception as exc:
                    self.console.print("[red]Command failed:[/] %s" % exc)
                continue
            if looks_like_download_request(user_input):
                self._handle_download_text(user_input)
                continue
            self._ask_local_ai(user_input)

    def _ensure_login(self) -> None:
        if self.session.get("token"):
            self.api.token = self.session["token"]
            self.console.print("[green]Using saved local account:[/] %s" % self.session.get("username", "user"))
            return
        self.console.print("First login requires server verification.")
        username = Prompt.ask("Username")
        password = Prompt.ask("Password", password=True)
        payload = self.api.login(username, password, self.computer.name)
        self.session = {
            "token": payload["token"],
            "username": username,
            "verified_at": utc_now(),
            "server": self.config.app_base_url,
        }
        save_client_session(self.root, self.session)
        self.api.token = payload["token"]
        self.console.print("[green]Server login verified. Local account saved for next startup.[/]")

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
                self.console.print("[red]Server sync error:[/] %s" % exc)
            self.stop_event.wait(5)

    def _handle_server_task(self, task: dict) -> None:
        prompt = str(task["prompt"])
        task_id = int(task["id"])
        self.console.print("[cyan]Web task %s received.[/] %s" % (task_id, prompt))
        try:
            result = self.agent.ask(prompt)
            self.api.complete_task(task_id, response=result.message)
            self.console.print("[green]Web task %s completed.[/]" % task_id)
        except Exception as exc:
            self.api.complete_task(task_id, error=str(exc))
            self.console.print("[red]Web task failed:[/] %s" % exc)

    def _render_header(self) -> None:
        summary = (
            "Server: {server}\nUser: {user}\nComputer: {computer}\nProvider: {provider}\n"
            "Model: {model}\nMode: {mode}\nPermission: {permission}\nHelp: /help"
        ).format(
            server=self.config.app_base_url,
            user=self.session.get("username", "-"),
            computer=self.computer.name,
            provider=self.config.provider,
            model=self.config.model,
            mode=self.agent.state.mode,
            permission=self.permission,
        )
        panel = Panel(summary, title="EasyAI Client", border_style="blue")
        self.console.print(Columns([panel, self.pet.render()], equal=False, expand=False) if self.pet.enabled else panel)

    def _ask_local_ai(self, prompt: str) -> None:
        try:
            self.pet.set_state("thinking", "Preparing answer.")
            self._render_pet()
            result = self.agent.ask(prompt)
        except Exception as exc:
            self.pet.set_state("error", "Request failed.")
            self._render_pet()
            self.console.print("[red]Error:[/] %s" % exc)
            return
        self._render_result(result)

    def _render_pet(self) -> None:
        if self.pet.enabled:
            self.console.print(self.pet.render())

    def _render_result(self, result: AssistantResult) -> None:
        self.pet.set_state("waiting" if result.proposed_changes else "success", "Ready.")
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
                self.console.print("Local saved account cleared. Next startup will require server login.")
            else:
                self.console.print("Client stopped.")
            return True
        if command == "/help":
            self._show_help(parts[1] if len(parts) > 1 else "")
            return False
        if command == "/permission":
            self._handle_permission(parts[1:])
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
            self.console.print("[green]Provider set to[/] %s" % self.config.provider)
            return False
        if command == "/model" and len(parts) >= 2:
            self.config.model = " ".join(parts[1:])
            self.console.print("[green]Model set to[/] %s" % self.config.model)
            return False
        if command == "/mode" and len(parts) == 2:
            self.agent.set_mode(parts[1])  # type: ignore[arg-type]
            self.console.print("[green]Mode set to[/] %s" % self.agent.state.mode)
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
            self.console.print("[green]Session reset.[/]")
            return False
        if command == "/files":
            self._require_permission("files")
            self._list_files()
            return False
        self.console.print("[yellow]Unknown command. Type /help.[/]")
        return False

    def _show_help(self, topic: str = "") -> None:
        text = HELP_TOPICS.get(topic.lower().strip(), HELP_SHORT) if topic else HELP_SHORT
        self.console.print(Panel(text.rstrip(), title="Help", border_style="cyan"))

    def _handle_permission(self, args: List[str]) -> None:
        if not args:
            self.console.print(Panel("Current permission: %s" % self.permission, title="Permission", border_style="cyan"))
            return
        requested = args[0].lower()
        if requested not in PERMISSION_LEVELS:
            raise ValueError("Unsupported permission mode: %s" % requested)
        if requested == "elevated" and not Confirm.ask("Enable elevated mode? Admin actions will still ask again.", default=False):
            return
        self.permission = requested
        self.console.print("[green]Permission set to[/] %s" % self.permission)

    def _require_permission(self, required: str) -> None:
        order = {"safe": 0, "files": 1, "downloads": 2, "elevated": 3}
        if order[self.permission] < order[required]:
            raise PermissionError("Current permission is %s. Run /permission %s first." % (self.permission, required))

    def _handle_pet(self, args: List[str]) -> None:
        if not args or args[0] == "status":
            self._render_pet()
            return
        if args[0] == "on":
            self.pet.enabled = True
            self.pet.set_state("idle", "Pet enabled.")
            self._render_pet()
            return
        if args[0] == "off":
            self.pet.enabled = False
            self.console.print("[yellow]Pet disabled.[/]")
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
            raise ValueError("Specify software name or URL.")
        if self.downloader.is_url(query):
            if Confirm.ask("Download URL into workspace downloads/?", default=False):
                result = self.downloader.download_url(query)
                self.console.print("[green]Downloaded:[/] %s" % result.path)
            return
        if install:
            if elevated:
                self._require_permission("elevated")
            if not Confirm.ask("Install %s with winget?" % query, default=False):
                return
            if elevated and not Confirm.ask("Use administrator permission for %s?" % query, default=False):
                return
            result = self.downloader.winget_install(query, elevated=elevated)
            self.console.print(Panel(result.message, title="Install", border_style="green"))
            return
        if Confirm.ask("Search %s with winget?" % query, default=True):
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
            self.console.print("[yellow]No pending changes.[/]")
            return
        for change in pending.proposed_changes:
            self.console.print(Syntax(change.diff_text, "diff", theme="ansi_dark"))
            if Confirm.ask("Apply changes to %s?" % change.path, default=False):
                self.workspace.apply_change(change)
                self.agent.state.applied_changes.append(change)
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
        self.console.print("[yellow]No suggested run. Use /run demo.py or /run pytest tests[/]")

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


def main() -> None:
    EasyAIClient(Path.cwd()).run()
