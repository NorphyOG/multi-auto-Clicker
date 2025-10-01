"""
Small CLI to run an automation script JSON file without the GUI.

Usage (PowerShell):
    python run_script.py .\\automation\\examples\\example_notepad.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from automation import AutomationEngine
from automation.script_model import AutomationScript


def main() -> int:
    if len(sys.argv) < 2:
        print("Provide path to a JSON script.")
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    script = AutomationScript.from_dict(data)
    engine = AutomationEngine(script)
    engine.on_log(lambda m: print(m))
    engine.on_done(lambda ok, msg: print(f"DONE: {ok} - {msg}"))
    engine.start()
    # Wait until thread finishes
    if engine._thread:  # type: ignore[attr-defined]
        engine._thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
