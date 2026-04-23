from __future__ import annotations

import json
from typing import Dict, Optional
from urllib import error, request


class HttpError(RuntimeError):
    pass


def post_json(url: str, payload: Dict[str, object], headers: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    raw_headers = {"Content-Type": "application/json"}
    if headers:
        raw_headers.update(headers)

    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=raw_headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpError("HTTP %s: %s" % (exc.code, body))
    except error.URLError as exc:
        raise HttpError("Network error: %s" % exc.reason)

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HttpError("Invalid JSON response: %s" % exc)
    if not isinstance(decoded, dict):
        raise HttpError("Expected a JSON object response")
    return decoded
