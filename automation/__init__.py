"""
Automation package: scriptable background automation without moving the cursor.

This package introduces a minimal, extensible automation engine intended for
"Hintergrund" control of other programs via actions described in JSON.

Key parts
---------
- actions:     Small action classes (launch, wait, send_keys, type_text, activate)
- script_model:Data classes & parser for JSON scripts
- engine:      Runner that executes actions with cancel support

Only the automation area is new. Existing GUI/Clicker code remains untouched.
"""

from .engine import AutomationEngine
from .script_model import AutomationScript

__all__ = ["AutomationEngine", "AutomationScript"]
