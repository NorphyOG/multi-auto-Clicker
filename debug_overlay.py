"""Debug overlay that renders markers on screen for click positions."""

from __future__ import annotations

import tkinter as tk
from typing import Iterable, List

from models import ClickPosition


class DebugOverlayManager:
    """Manages small overlay windows to visualise click targets."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._overlays: List[tk.Toplevel] = []
        self._enabled = False
        self._positions: List[ClickPosition] = []

    def enable(self) -> None:
        """Display overlays for all known positions."""
        if not self._enabled:
            self._enabled = True
            self._rebuild_overlays()

    def disable(self) -> None:
        """Hide all overlays and prevent further rendering."""
        if self._enabled:
            self._enabled = False
            self._clear()

    def set_positions(self, positions: Iterable[ClickPosition]) -> None:
        """Update overlay positions and refresh display when enabled."""
        self._positions = list(positions)
        if self._enabled:
            self._rebuild_overlays()

    def toggle(self, enabled: bool) -> None:
        """Convenience method to switch overlay visibility."""
        if enabled:
            self.enable()
        else:
            self.disable()

    def _rebuild_overlays(self) -> None:
        self._clear()
        if not self._enabled:
            return

        for index, position in enumerate(self._positions, start=1):
            overlay = tk.Toplevel(self._root)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", 0.65)
            overlay.configure(bg="yellow")

            marker_text = position.label or f"#{index}"
            label = tk.Label(
                overlay,
                text=f"✕ {marker_text}",
                font=("Arial", 12, "bold"),
                fg="red",
                bg="yellow",
            )
            label.pack(ipadx=4, ipady=2)

            overlay.geometry(f"+{position.x}+{position.y}")
            overlay.update_idletasks()
            self._overlays.append(overlay)

    def _clear(self) -> None:
        while self._overlays:
            window = self._overlays.pop()
            try:
                window.destroy()
            except Exception:
                pass
