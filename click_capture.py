"""Utility to capture the next mouse click globally."""

from __future__ import annotations

import threading
from typing import Callable, Optional

try:
    from pynput import mouse  # type: ignore
except Exception:  # pragma: no cover - environment dependent
    mouse = None  # type: ignore
import tkinter as tk


CapturedCallback = Callable[[int, int], None]
ErrorCallback = Callable[[Exception], None]


class ClickCaptureService:
    """Listens for the next mouse click and reports it back to the Tkinter thread."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._listener: Optional[object] = None
        self._lock = threading.Lock()
        self._on_captured: Optional[CapturedCallback] = None
        self._on_error: Optional[ErrorCallback] = None

    def capture_next_click(
        self,
        on_captured: CapturedCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> bool:
        """Start listening for the next click.

        Returns True if the capture started successfully, or False if a capture is already in progress.
        """
        with self._lock:
            if self._listener is not None:
                return False

            self._on_captured = on_captured
            self._on_error = on_error

            try:
                if mouse is None:
                    raise RuntimeError("pynput/mouse backend not available; Mausaufzeichnung ist deaktiviert.")
                self._listener = mouse.Listener(on_click=self._handle_click)
                self._listener.start()
                return True
            except Exception as exc:  # pragma: no cover - hardware dependent
                self._listener = None
                if on_error:
                    self._notify_error(exc)
                return False

    def cancel(self) -> None:
        """Cancel a pending capture if present."""
        with self._lock:
            self._stop_listener()

    # Internal helpers -------------------------------------------------

    def _handle_click(self, x: float, y: float, _button, pressed: bool) -> bool:
        if not pressed:
            return True

        self._stop_listener()

        # Normalize coordinates using pyautogui to match the coordinate system
        # used later for clicking. This avoids DPI scaling issues on multi‑monitor
        # setups (e.g., 4K secondary display with scaling).
        nx, ny = None, None
        try:
            import pyautogui  # type: ignore
            cx, cy = pyautogui.position()
            nx, ny = int(cx), int(cy)
        except Exception:
            # Fallback to pynput-provided coordinates
            nx, ny = int(x), int(y)

        if self._on_captured:
            self._notify_capture(nx, ny)
        return False

    def _stop_listener(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()  # type: ignore[attr-defined]
            except Exception:
                pass

    def _notify_capture(self, x: int, y: int) -> None:
        self._root.after(0, lambda: self._safe_invoke(self._on_captured, x, y))

    def _notify_error(self, exc: Exception) -> None:
        self._root.after(0, lambda: self._safe_invoke(self._on_error, exc))

    @staticmethod
    def _safe_invoke(callback: Optional[Callable], *args) -> None:
        if callback:
            try:
                callback(*args)
            except Exception:
                # Suppress callback errors; they should be handled by caller logging.
                pass
