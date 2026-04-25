from __future__ import annotations

import json
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


class ServerApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
        retry_after: Optional[int] = None,
    ) -> None:
        super().__init__("Server API error %s: %s" % (status_code, message))
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable
        self.retry_after = retry_after


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
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 EasyAI-Client/0.1 (+https://xingkongtech.top)",
        }
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
            details: Optional[Dict[str, Any]] = None
            try:
                parsed = json.loads(message)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                details = parsed
                message = str(parsed.get("detail") or parsed.get("error") or message)
            retry_after: Optional[int] = None
            header_retry_after = exc.headers.get("Retry-After")
            if header_retry_after and header_retry_after.isdigit():
                retry_after = int(header_retry_after)
            if details and isinstance(details.get("retry_after"), int):
                retry_after = int(details["retry_after"])
            retryable = bool(details.get("retryable")) if details else exc.code in {429, 502, 503, 504}
            raise ServerApiError(
                exc.code,
                message,
                details=details,
                retryable=retryable,
                retry_after=retry_after,
            ) from exc


def load_client_session(root: Path) -> Dict[str, Any]:
    path = root / "easyai-data" / "client_session.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
