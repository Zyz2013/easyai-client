from __future__ import annotations

import socket
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ComputerIdentity:
    uid: str
    name: str


def load_computer_identity(root: Path) -> ComputerIdentity:
    data_dir = root / "easyai-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    identity_file = data_dir / "computer_id"
    if identity_file.exists():
        uid = identity_file.read_text(encoding="utf-8").strip()
    else:
        uid = str(uuid.uuid4())
        identity_file.write_text(uid, encoding="utf-8")
    return ComputerIdentity(uid=uid, name=socket.gethostname() or "EasyAI Computer")
