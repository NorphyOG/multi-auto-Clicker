"""
Main entry point for the Multi Auto Clicker application.

Clean Code principles:
- Minimal main file
- Dependency injection at the root
- Clear program flow
"""

import sys
import tkinter as tk
from gui import AutoClickerGUI


def _enable_high_dpi_awareness() -> None:
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except AttributeError:
            pass

        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except AttributeError:
            pass
    except Exception:
        # Ignore DPI awareness errors; Tk will fallback to default behaviour.
        pass


def main() -> None:
    """
    Application entry point.
    
    Clean Code: Simple, clear main function that just starts the app.
    """
    _enable_high_dpi_awareness()
    root = tk.Tk()
    app = AutoClickerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
