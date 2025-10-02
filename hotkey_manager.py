"""Platform-agnostic hotkey manager built on top of pynput."""

from __future__ import annotations

from typing import Callable, Dict, Optional

try:
    from pynput import keyboard  # type: ignore
except Exception as _e:  # pragma: no cover - environment dependent
    keyboard = None  # type: ignore


class HotkeyManager:
    """Manages global hotkeys across Windows, macOS, and Linux."""

    _SPECIAL_KEY_ALIASES: Dict[str, str] = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "shift": "shift",
        "win": "cmd",
        "cmd": "cmd",
        "command": "cmd",
        "option": "alt",
        "super": "cmd",
    }

    def __init__(self, start_hotkey: str = "F6", stop_hotkey: str = "F7") -> None:
        self._start_hotkey = start_hotkey
        self._stop_hotkey = stop_hotkey
        self._start_callback: Optional[Callable[[], None]] = None
        self._stop_callback: Optional[Callable[[], None]] = None
        self._listener: Optional[object] = None
        self._is_registered = False

    def register_start_callback(self, callback: Callable[[], None]) -> None:
        self._start_callback = callback

    def register_stop_callback(self, callback: Callable[[], None]) -> None:
        self._stop_callback = callback

    def enable_hotkeys(self) -> bool:
        if self._is_registered:
            return True

        hotkey_map: Dict[str, Callable[[], None]] = {}

        try:
            if self._start_callback:
                hotkey = self._to_pynput_hotkey(self._start_hotkey)
                if hotkey:
                    hotkey_map[hotkey] = self._start_callback

            if self._stop_callback:
                hotkey = self._to_pynput_hotkey(self._stop_hotkey)
                if hotkey:
                    hotkey_map[hotkey] = self._stop_callback
        except ValueError as exc:
            print(f"Invalid hotkey definition: {exc}")
            return False

        if not hotkey_map:
            return False

        if keyboard is None:
            print("pynput/keyboard backend not available; global hotkeys disabled")
            self._listener = None
            self._is_registered = False
            return False
        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
            self._is_registered = True
            return True
        except Exception as exc:  # pragma: no cover - system specific
            print(f"Failed to register hotkeys: {exc}")
            self._listener = None
            self._is_registered = False
            return False

    def disable_hotkeys(self) -> None:
        if not self._is_registered:
            return

        if self._listener is not None:
            try:
                self._listener.stop()  # type: ignore[attr-defined]
            except Exception:
                pass
            self._listener = None

        self._is_registered = False

    def get_start_hotkey(self) -> str:
        return self._start_hotkey

    def get_stop_hotkey(self) -> str:
        return self._stop_hotkey

    def update_hotkeys(self, start_hotkey: str, stop_hotkey: str) -> bool:
        was_registered = self._is_registered
        if was_registered:
            self.disable_hotkeys()

        self._start_hotkey = start_hotkey
        self._stop_hotkey = stop_hotkey

        if was_registered:
            return self.enable_hotkeys()
        return True

    def _to_pynput_hotkey(self, hotkey: str) -> str:
        if not hotkey:
            raise ValueError("Empty hotkey string")

        tokens = [token.strip() for token in hotkey.replace("+", " ").split() if token.strip()]
        if not tokens:
            raise ValueError("Hotkey contains no tokens")

        parsed: list[str] = []
        for token in tokens:
            lower_token = token.lower()

            if lower_token in self._SPECIAL_KEY_ALIASES:
                parsed.append(f"<{self._SPECIAL_KEY_ALIASES[lower_token]}>")
                continue

            if lower_token.startswith("f") and lower_token[1:].isdigit():
                parsed.append(f"<{lower_token}>")
                continue

            if len(lower_token) == 1:
                parsed.append(lower_token)
                continue

            parsed.append(lower_token)

        return "+".join(parsed)
