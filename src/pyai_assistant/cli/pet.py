from __future__ import annotations

from dataclasses import dataclass

from rich.panel import Panel


PET_ART = {
    "idle": r"""
 /\_/\\
( o.o )
 > ^ <
""".strip("\n"),
    "thinking": r"""
 /\_/\\
( -.- )
 / >? 
""".strip("\n"),
    "waiting": r"""
 /\_/\\
( 0.0 )
 / >  
""".strip("\n"),
    "success": r"""
 /\_/\\
( ^.^ )
 / >  
""".strip("\n"),
    "error": r"""
 /\_/\\
( x.x )
 / >  
""".strip("\n"),
}


PET_LABEL = {
    "idle": "空闲中",
    "thinking": "思考中",
    "waiting": "等你确认",
    "success": "完成了",
    "error": "出错了",
}


PET_COLOR = {
    "idle": "cyan",
    "thinking": "blue",
    "waiting": "yellow",
    "success": "green",
    "error": "red",
}


@dataclass
class TerminalPet:
    name: str = "Mochi"
    enabled: bool = True
    mood: str = "idle"
    note: str = "随时可以开始。"

    def set_state(self, mood: str, note: str) -> None:
        self.mood = mood
        self.note = note

    def render(self) -> Panel:
        title = "%s 宠物" % self.name
        body = "%s\n\n状态: %s\n%s" % (
            PET_ART[self.mood],
            PET_LABEL[self.mood],
            self.note,
        )
        return Panel(body, title=title, border_style=PET_COLOR[self.mood], width=28)
