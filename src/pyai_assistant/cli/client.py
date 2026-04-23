from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from pyai_assistant.config import load_config
from pyai_assistant.client_services import ChatService
from pyai_assistant.providers.server_api import ServerApiClient, load_client_session, save_client_session
from pyai_assistant.runtime.computer import load_computer_identity


class EasyAIClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.console = Console()
        self.config = load_config(root)
        self.computer = load_computer_identity(root)
        self.session = load_client_session(root)
        self.api = ServerApiClient(self.config.app_base_url, self.session.get("token"))
        self.chat_service = ChatService(self.config)

    def run(self) -> None:
        self._ensure_login()
        self.console.print(
            Panel(
                "Server: %s\nComputer: %s\nProvider: %s\nModel: %s"
                % (self.config.app_base_url, self.computer.name, self.config.provider, self.config.model),
                title="EasyAI Client",
                border_style="blue",
            )
        )
        while True:
            try:
                self.api.heartbeat(self.computer.uid, self.computer.name)
                payload = self.api.next_task(self.computer.uid)
                task = payload.get("task")
                if task:
                    self._handle_task(task)
                time.sleep(5)
            except KeyboardInterrupt:
                self.console.print("\nClient stopped.")
                return
            except Exception as exc:
                self.console.print("[red]Client error:[/] %s" % exc)
                time.sleep(10)

    def _ensure_login(self) -> None:
        if self.session.get("token"):
            return
        self.console.print("Log in with your EasyAI server account.")
        username = Prompt.ask("Username")
        password = Prompt.ask("Password", password=True)
        payload = self.api.login(username, password, self.computer.name)
        self.session = {"token": payload["token"], "username": username}
        save_client_session(self.root, self.session)
        self.api.token = payload["token"]

    def _handle_task(self, task: dict) -> None:
        prompt = str(task["prompt"])
        task_id = int(task["id"])
        self.console.print("[cyan]Task %s received.[/] %s" % (task_id, prompt))
        try:
            response = self.chat_service.generate_reply([], prompt)
        except Exception as exc:
            self.api.complete_task(task_id, error=str(exc))
            self.console.print("[red]Task failed:[/] %s" % exc)
            return
        self.api.complete_task(task_id, response=response)
        self.console.print("[green]Task %s completed.[/]" % task_id)


def main() -> None:
    EasyAIClient(Path.cwd()).run()
