"""
Domain models for the Multi Auto Clicker application.
Each class follows the Single Responsibility Principle (SRP).
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Any


class ClickType(Enum):
    """Enumeration of supported click types."""
    LEFT = "left"
    RIGHT = "right"
    DOUBLE = "double"


class ClickMode(Enum):
    """Defines how the engine determines click targets."""
    STATIC_SEQUENCE = "static_sequence"
    FOLLOW_CURSOR = "follow_cursor"


@dataclass
class ClickPosition:
    """Represents a screen position where a click should occur."""
    x: int
    y: int
    label: str | None = None

    def to_tuple(self) -> Tuple[int, int]:
        """Returns position as a tuple for compatibility with mouse libraries."""
        return (self.x, self.y)
    
    def __str__(self) -> str:
        base = f"({self.x}, {self.y})"
        return f"{self.label} {base}" if self.label else base

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the position for JSON storage."""
        return {"x": self.x, "y": self.y, "label": self.label}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ClickPosition":
        """Create a ClickPosition from a dictionary."""
        x_raw = data.get("x", 0)
        y_raw = data.get("y", 0)
        label_raw = data.get("label")

        return ClickPosition(
            x=int(x_raw) if x_raw is not None else 0,
            y=int(y_raw) if y_raw is not None else 0,
            label=str(label_raw) if label_raw not in (None, "") else None,
        )


@dataclass
class ClickConfiguration:
    """
    Configuration settings for the auto-clicker.
    
    SRP: This class encapsulates all configuration-related logic
    and validation. Clean Code principle: descriptive name that
    clearly indicates what this class represents.
    """
    click_positions: List[ClickPosition]
    click_rate_per_second: float
    total_clicks: int
    click_type: ClickType
    click_mode: ClickMode = ClickMode.STATIC_SEQUENCE
    run_in_background: bool = False
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.click_mode == ClickMode.STATIC_SEQUENCE and not self.click_positions:
            raise ValueError("At least one click position is required for static mode")
        
        if self.click_rate_per_second <= 0:
            raise ValueError("Click rate must be positive")
        
        if self.total_clicks < 0:
            raise ValueError("Total clicks cannot be negative")
    
    def get_delay_between_clicks(self) -> float:
        """
        Calculate delay between clicks in seconds.
        
        Clean Code: Method name clearly describes what it returns.
        """
        return 1.0 / self.click_rate_per_second if self.click_rate_per_second > 0 else 0.1
    
    def is_infinite_mode(self) -> bool:
        """Check if clicker should run indefinitely."""
        return self.total_clicks == 0


class ClickerState(Enum):
    """Enumeration of auto-clicker states."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class ApplicationSettings:
    """Persisted application preferences."""

    click_positions: List[ClickPosition] = field(default_factory=list)
    click_rate_per_second: float = 5.0
    total_clicks: int = 0
    click_type: ClickType = ClickType.LEFT
    click_mode: ClickMode = ClickMode.STATIC_SEQUENCE
    run_in_background: bool = False
    debug_overlay_enabled: bool = False
    start_hotkey: str = "F6"
    stop_hotkey: str = "F7"
    dark_mode_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize settings to primitive types for JSON storage."""
        return {
            "click_positions": [pos.to_dict() for pos in self.click_positions],
            "click_rate_per_second": self.click_rate_per_second,
            "total_clicks": self.total_clicks,
            "click_type": self.click_type.value,
            "click_mode": self.click_mode.value,
            "run_in_background": self.run_in_background,
            "debug_overlay_enabled": self.debug_overlay_enabled,
            "start_hotkey": self.start_hotkey,
            "stop_hotkey": self.stop_hotkey,
            "dark_mode_enabled": self.dark_mode_enabled,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ApplicationSettings":
        """Create settings instance from JSON dictionary."""
        positions_data = data.get("click_positions", []) or []
        positions: List[ClickPosition] = []
        if isinstance(positions_data, list):
            for raw in positions_data:
                if isinstance(raw, dict):
                    positions.append(ClickPosition.from_dict(raw))

        return ApplicationSettings(
            click_positions=positions,
            click_rate_per_second=float(data.get("click_rate_per_second", 5.0) or 5.0),
            total_clicks=int(data.get("total_clicks", 0) or 0),
            click_type=ClickType(str(data.get("click_type", ClickType.LEFT.value))),
            click_mode=ClickMode(str(data.get("click_mode", ClickMode.STATIC_SEQUENCE.value))),
            run_in_background=bool(data.get("run_in_background", False)),
            debug_overlay_enabled=bool(data.get("debug_overlay_enabled", False)),
            start_hotkey=str(data.get("start_hotkey", "F6")),
            stop_hotkey=str(data.get("stop_hotkey", "F7")),
            dark_mode_enabled=bool(data.get("dark_mode_enabled", False)),
        )
