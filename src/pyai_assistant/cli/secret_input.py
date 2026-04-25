from __future__ import annotations

import sys
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt


def prompt_secret(console: Console, label: str, default: str = "", allow_empty: bool = False) -> str:
    if sys.platform != "win32":
        value = Prompt.ask(label, password=True, default=default or None)
        value = value.strip()
        if not value and not allow_empty:
            raise ValueError("%s is required." % label)
        return value or default

    import msvcrt

    prompt = "%s%s: " % (label, (" (%s)" % ("*" * len(default))) if default else "")
    while True:
        console.print(prompt, end="")
        chars = []
        while True:
            key = msvcrt.getwch()
            if key in ("\r", "\n"):
                console.print()
                break
            if key == "\003":
                raise KeyboardInterrupt()
            if key in ("\b", "\x08", "\x7f"):
                if chars:
                    chars.pop()
                    console.print("\b \b", end="")
                continue
            if key == "\x15":
                while chars:
                    chars.pop()
                    console.print("\b \b", end="")
                continue
            if key in ("\x00", "\xe0"):
                special = msvcrt.getwch()
                if special == "S":
                    if chars:
                        chars.pop()
                        console.print("\b \b", end="")
                continue
            if ord(key) < 32:
                continue
            chars.append(key)
            console.print("*", end="")

        value = "".join(chars).strip()
        if value:
            return value
        if default:
            return default
        if allow_empty:
            return ""
        console.print("[yellow]%s[/]" % ("%s is required." % label))
