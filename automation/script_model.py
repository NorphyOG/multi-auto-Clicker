"""
Automation script data model and JSON parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any

from .actions import BaseAction


@dataclass
class AutomationScript:
    name: str
    actions: List[BaseAction] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AutomationScript":
        name = str(data.get("name", "Unnamed Script"))
        actions_data = data.get("actions", []) or []
        actions: List[BaseAction] = []
        if isinstance(actions_data, list):
            for raw in actions_data:
                if isinstance(raw, dict):
                    actions.append(BaseAction.from_dict(raw))
        return AutomationScript(name=name, actions=actions)
