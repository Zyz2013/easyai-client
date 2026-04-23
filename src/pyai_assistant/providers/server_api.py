from __future__ import annotations

import json
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


class ServerApiClient:
    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def login(self, username: str, password: str, device_name: str) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/login",
            {"username": username, "password": password, "device_name": device_name},
            authenticated=False,
        )

    def heartbeat(self, uid: str, name: str) -> Dict[str, Any]:
        return self._request("POST", "/api/computers/heartbeat", {"uid": uid, "name": name})

    def next_task(self, computer_uid: str) -> Dict[str, Any]:
        return self._request("GET", "/api/tasks/next?computer_uid=%s" % urllib.parse.quote(computer_uid), None)

    def complete_task(self, task_id: int, response: str = "", error: str = "") -> Dict[str, Any]:
        return self._request("POST", "/api/tasks/%s/complete" % task_id, {"response": response, "error": error})

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]],
        authenticated: bool = True,
    ) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if authenticated:
            if not self.token:
                raise ValueError("Missing server token.")
            headers["Authorization"] = "Bearer %s" % self.token
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError("Server API error %s: %s" % (exc.code, message)) from exc


def load_client_session(root: Path) -> Dict[str, Any]:
    path = root / "easyai-data" / "client_session.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_client_session(root: Path, payload: Dict[str, Any]) -> None:
    path = root / "easyai-data" / "client_session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_client_session(root: Path) -> None:
    path = root / "easyai-data" / "client_session.json"
    if path.exists():
        path.unlink()


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
