"""Persistence utilities for Multi Auto Clicker settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from models import ApplicationSettings


class SettingsManager:
    """Handles loading and saving application settings to disk."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        package_root = Path(__file__).resolve().parent
        self._storage_path = storage_path or package_root / "settings.json"

    @property
    def storage_path(self) -> Path:
        """Absolute path to the settings file."""
        return self._storage_path

    def load(self) -> ApplicationSettings:
        """Load settings from disk, returning defaults if the file is missing or corrupt."""
        path = self.storage_path
        if not path.exists():
            return ApplicationSettings()

        try:
            content = path.read_text(encoding="utf-8")
            raw_data = json.loads(content)
            if not isinstance(raw_data, dict):
                raise ValueError("Settings file has invalid structure")
            return ApplicationSettings.from_dict(raw_data)
        except Exception:
            # Corrupt or unreadable file; fall back to defaults but keep backup for inspection.
            backup_path = path.with_suffix(".bak")
            try:
                path.replace(backup_path)
            except Exception:
                # Ignore backup failures; we still return defaults.
                pass
            return ApplicationSettings()

    def save(self, settings: ApplicationSettings) -> None:
        """Persist settings atomically to disk."""
        path = self.storage_path
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_suffix(".tmp")
        payload = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(path)
