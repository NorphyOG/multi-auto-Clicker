"""
Automation engine that executes an AutomationScript in a worker thread.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from .actions import RunContext
from .script_model import AutomationScript


class AutomationEngine:
    def __init__(self, script: AutomationScript):
        self._script = script
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_log: Optional[Callable[[str], None]] = None
        self._on_done: Optional[Callable[[bool, str], None]] = None

    def on_log(self, cb: Callable[[str], None]) -> None:
        self._on_log = cb

    def on_done(self, cb: Callable[[bool, str], None]) -> None:
        self._on_done = cb

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _log(self, msg: str) -> None:
        if self._on_log:
            try:
                self._on_log(msg)
            except Exception:
                pass

    def _worker(self) -> None:
        ctx = RunContext(logger=self._log)
        try:
            for idx, action in enumerate(self._script.actions):
                if self._stop.is_set():
                    self._finish(False, "Aborted")
                    return
                self._log(f"[{idx+1}/{len(self._script.actions)}] {action.__class__.__name__}")
                action.run(ctx)
            self._finish(True, "Completed")
        except Exception as e:  # pragma: no cover - runtime path
            self._finish(False, f"Error: {e}")

    def _finish(self, ok: bool, msg: str) -> None:
        if self._on_done:
            try:
                self._on_done(ok, msg)
            except Exception:
                pass
