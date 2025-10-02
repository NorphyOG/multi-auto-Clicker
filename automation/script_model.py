"""
Automation script data model and JSON parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .actions import BaseAction


@dataclass
class AutomationScript:
    name: str
    actions: List[BaseAction] = field(default_factory=list)
    # Optional loop configuration
    repeat_count: Optional[int] = None  # None means run once; >=1 run that many times
    repeat_until_stopped: bool = False  # when True, ignore repeat_count and run until cancel

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AutomationScript":
        name = str(data.get("name", "Unnamed Script"))
        actions_data = data.get("actions", []) or []
        actions: List[BaseAction] = []
        if isinstance(actions_data, list):
            for raw in actions_data:
                if isinstance(raw, dict):
                    actions.append(BaseAction.from_dict(raw))
        # Loop config: accept either top-level keys or a "loop" object
        repeat_count: Optional[int] = None
        repeat_until_stopped = False
        loop_cfg = data.get("loop") or {}
        if isinstance(loop_cfg, dict):
            rc = loop_cfg.get("repeat")
            if rc is not None:
                try:
                    repeat_count = max(1, int(rc))
                except Exception:
                    repeat_count = None
            repeat_until_stopped = bool(loop_cfg.get("until_stopped", False))
        # Also allow top-level shortcuts
        if repeat_count is None and "repeat" in data:
            try:
                raw = data.get("repeat", 0) or 0
                repeat_count = max(1, int(raw))
            except Exception:
                repeat_count = None
        if not repeat_until_stopped and bool(data.get("until_stopped", False)):
            repeat_until_stopped = True

        return AutomationScript(
            name=name,
            actions=actions,
            repeat_count=repeat_count,
            repeat_until_stopped=repeat_until_stopped,
        )
