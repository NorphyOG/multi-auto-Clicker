"""
Automation actions: small, composable building blocks.

Supported actions (type field in JSON):
- launch_process: start an application in background
- wait: sleep for milliseconds
- send_keys: send key combinations to OS (background when possible)
- type_text: type literal text (no cursor movement)
- window_activate: bring a window to foreground by title (best-effort)
 - mouse_click: click mouse at (x,y) or current position
 - scroll: mouse wheel scroll (vertical or horizontal)

Notes
-----
- On Windows, we use pywinauto for reliable background key dispatch and
  window activation. On other platforms, we fallback to pynput to send
  keystrokes to the currently focused window (true background control is
  limited by the OS without accessibility permissions).
"""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Callable


class ActionError(Exception):
    pass


@dataclass
class BaseAction:
    """Common interface for all actions."""

    def run(self, ctx: "RunContext") -> None:  # pragma: no cover - runtime behavior
        raise NotImplementedError

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BaseAction":
        action_type = str(data.get("type", "")).strip().lower()
        if action_type == "launch_process":
            return LaunchProcessAction(
                command=str(data.get("command")),
                args=list(data.get("args", [])),
                cwd=data.get("cwd"),
                wait=float(data.get("wait", 0.0) or 0.0),
            )
        if action_type == "wait":
            return WaitAction(milliseconds=int(data.get("milliseconds", 0) or 0))
        if action_type == "send_keys":
            return SendKeysAction(sequence=str(data.get("sequence", "")))
        if action_type == "type_text":
            return TypeTextAction(text=str(data.get("text", "")))
        if action_type == "window_activate":
            return WindowActivateAction(title=str(data.get("title", "")))
        if action_type == "mouse_click":
            return MouseClickAction(
                x=data.get("x"),
                y=data.get("y"),
                button=str(data.get("button", "left") or "left"),
                clicks=int(data.get("clicks", 1) or 1),
            )
        if action_type == "scroll":
            return ScrollAction(
                amount=int(data.get("amount", 0) or 0),
                horizontal=bool(data.get("horizontal", False)),
            )
        raise ActionError(f"Unknown action type: {action_type}")


@dataclass
class LaunchProcessAction(BaseAction):
    command: str
    args: List[str]
    cwd: Optional[str] = None
    wait: float = 0.0

    def run(self, ctx: "RunContext") -> None:
        if not self.command:
            raise ActionError("launch_process: 'command' is required")
        try:
            subprocess.Popen([self.command, *self.args], cwd=self.cwd)
        except Exception as e:  # pragma: no cover
            raise ActionError(f"Failed to start process '{self.command}': {e}")
        if self.wait > 0:
            ctx.sleep(self.wait)


@dataclass
class WaitAction(BaseAction):
    milliseconds: int

    def run(self, ctx: "RunContext") -> None:
        ctx.sleep_ms(self.milliseconds)


@dataclass
class SendKeysAction(BaseAction):
    sequence: str

    def run(self, ctx: "RunContext") -> None:
        if not self.sequence:
            return
        # Try Windows backend first
        if sys.platform.startswith("win"):
            pw_ok = _try_pywinauto_send_keys(self.sequence, ctx, pause=0.02)
            if pw_ok:
                # Small stabilization delay so next action doesn't start too early
                ctx.sleep(0.05)
                return
        # Fallback to pynput
        kb_cls, key_mod = _get_pynput()
        if kb_cls is None or key_mod is None:
            raise ActionError("No keyboard backend available (install pynput)")
        kb = kb_cls()
        token_map = {
            "<ENTER>": getattr(key_mod, "enter", None),
            "<TAB>": getattr(key_mod, "tab", None),
            "<ESC>": getattr(key_mod, "esc", None),
            "<BACKSPACE>": getattr(key_mod, "backspace", None),
            "<DELETE>": getattr(key_mod, "delete", None),
            "<HOME>": getattr(key_mod, "home", None),
            "<END>": getattr(key_mod, "end", None),
            "<PAGE_UP>": getattr(key_mod, "page_up", None),
            "<PAGE_DOWN>": getattr(key_mod, "page_down", None),
            "<UP>": getattr(key_mod, "up", None),
            "<DOWN>": getattr(key_mod, "down", None),
            "<LEFT>": getattr(key_mod, "left", None),
            "<RIGHT>": getattr(key_mod, "right", None),
            "<SPACE>": " ",
        }
        for token in _tokenize_keys(self.sequence):
            mapped = token_map.get(token)
            if mapped is None:
                # Type literal characters
                for ch in token:
                    kb.press(ch); kb.release(ch)
            else:
                if isinstance(mapped, str) and mapped == " ":
                    kb.press(" "); kb.release(" ")
                else:
                    kb.press(mapped); kb.release(mapped)
        # Give the target app a moment to process
        ctx.sleep(0.05)


def _tokenize_keys(sequence: str) -> List[str]:
    # Very small helper: treat bracketed tokens like <ENTER> as single units
    out: List[str] = []
    buf = ""
    in_tag = False
    for ch in sequence:
        if ch == "<":
            if buf:
                out.append(buf)
                buf = ""
            in_tag = True
            buf += ch
        elif ch == ">" and in_tag:
            buf += ch
            out.append(buf)
            buf = ""
            in_tag = False
        else:
            buf += ch
    if buf:
        out.append(buf)
    # split on spaces except tokens like <ENTER>
    flat: List[str] = []
    for part in out:
        if part.startswith("<") and part.endswith(">"):
            flat.append(part)
        else:
            flat.extend([p for p in part.split(" ") if p])
    return flat


@dataclass
class TypeTextAction(BaseAction):
    text: str

    def run(self, ctx: "RunContext") -> None:
        if not self.text:
            return
        # Prefer pywinauto on Windows with a tiny pause to prevent dropped chars
        if sys.platform.startswith("win"):
            if _try_pywinauto_send_keys(self.text, ctx, pause=0.015):
                ctx.sleep(0.1)
                return
        kb_cls, _key_mod = _get_pynput()
        if kb_cls is None or _key_mod is None:
            raise ActionError("No keyboard backend available (install pynput)")
        kb = kb_cls()
        # Type per character with a very small delay to increase reliability
        for ch in self.text:
            kb.press(ch); kb.release(ch)
            # 10ms is enough for most apps; keep it tiny to stay fast
            ctx.sleep(0.01)
        # Stabilize before next action
        ctx.sleep(0.1)


@dataclass
class WindowActivateAction(BaseAction):
    title: str

    def run(self, ctx: "RunContext") -> None:
        if not self.title:
            return
        if sys.platform.startswith("win"):
            try:
                from pywinauto import Application  # type: ignore
                app = Application(backend="uia").connect(title_re=self.title)
                win = app.top_window()
                win.set_focus()
                return
            except Exception as e:  # pragma: no cover
                ctx.log(f"window_activate failed: {e}")
        # Best-effort only on non-Windows: nothing to do
        ctx.log("window_activate is only fully supported on Windows")


@dataclass
class MouseClickAction(BaseAction):
    x: Optional[int] = None
    y: Optional[int] = None
    button: str = "left"  # left|right|middle
    clicks: int = 1

    def run(self, ctx: "RunContext") -> None:
        # Prefer pynput for mouse where available; fallback to pyautogui
        m_ctrl_cls, m_btn_mod = _get_pynput_mouse()
        btn_name = self.button if self.button in ("left", "right", "middle") else "left"
        count = max(1, int(self.clicks or 1))
        ctx.log(f"mouse_click: x={self.x}, y={self.y}, button={btn_name}, clicks={count}")
        if m_ctrl_cls is not None and m_btn_mod is not None:
            try:
                controller = m_ctrl_cls()
                btn = getattr(m_btn_mod, btn_name)
                if self.x is not None and self.y is not None:
                    # This will move the cursor (OS limitation for targeted clicks)
                    controller.position = (int(self.x), int(self.y))
                for _ in range(count):
                    controller.click(btn)
                return
            except Exception as e:  # pragma: no cover
                ctx.log(f"pynput mouse_click failed, fallback to pyautogui: {e}")
        # Fallback: pyautogui
        try:
            import pyautogui  # local import to avoid hard dep at import time
            if self.x is not None and self.y is not None:
                for _ in range(count):
                    pyautogui.click(x=int(self.x), y=int(self.y), button=btn_name)
            else:
                for _ in range(count):
                    pyautogui.click(button=btn_name)
        except Exception as e:  # pragma: no cover
            raise ActionError(f"mouse_click failed: {e}")


@dataclass
class ScrollAction(BaseAction):
    amount: int = 0
    horizontal: bool = False

    def run(self, ctx: "RunContext") -> None:
        amt = int(self.amount or 0)
        ctx.log(f"scroll: amount={amt}, horizontal={self.horizontal}")
        # Prefer pynput where available
        m_ctrl_cls, _m_btn_mod = _get_pynput_mouse()
        if m_ctrl_cls is not None:
            try:
                controller = m_ctrl_cls()
                if self.horizontal:
                    controller.scroll(amt, 0)
                else:
                    controller.scroll(0, amt)
                return
            except Exception as e:  # pragma: no cover
                ctx.log(f"pynput scroll failed, fallback to pyautogui: {e}")
        # Fallback to pyautogui
        try:
            import pyautogui  # local import
            if self.horizontal:
                pyautogui.hscroll(amt)
            else:
                pyautogui.scroll(amt)
        except Exception as e:  # pragma: no cover
            raise ActionError(f"scroll failed: {e}")


class RunContext:
    """Small helper object passed to actions at runtime."""

    def __init__(self, logger: Optional[Callable[[str], None]] = None, sleep_hook: Optional[Callable[[float], None]] = None):
        self._logger = logger
        self._sleep = sleep_hook

    def log(self, msg: str) -> None:
        if self._logger:
            try:
                self._logger(msg)
            except Exception:
                pass

    def sleep(self, seconds: float) -> None:
        if self._sleep:
            self._sleep(seconds)
        else:
            time.sleep(seconds)

    def sleep_ms(self, ms: int) -> None:
        self.sleep(max(ms, 0) / 1000.0)


def _get_pynput() -> Tuple[Optional[Any], Optional[Any]]:
    """Import pynput lazily and return (KeyboardControllerClass, KeyModule)."""
    try:
        from pynput.keyboard import Controller as KeyboardController, Key as KeyModule  # type: ignore
        return KeyboardController, KeyModule
    except Exception:
        return None, None


def _get_pynput_mouse() -> Tuple[Optional[Any], Optional[Any]]:
    """Import pynput.mouse lazily and return (MouseControllerClass, ButtonModule)."""
    try:
        from pynput.mouse import Controller as MouseController, Button as MouseButton  # type: ignore
        return MouseController, MouseButton
    except Exception:
        return None, None


def _try_pywinauto_send_keys(text: str, ctx: "RunContext", *, pause: float = 0.0) -> bool:
    """Try to send keys via pywinauto on Windows; return True on success.

    pause: small delay (seconds) between characters to improve reliability.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        from pywinauto.keyboard import send_keys as pw_send_keys  # type: ignore
        # Use a tiny non-zero pause to avoid dropped characters in some apps
        pw_send_keys(text, with_spaces=True, pause=max(0.0, float(pause)))
        return True
    except Exception as e:  # pragma: no cover
        ctx.log(f"pywinauto send_keys failed: {e}")
        return False
