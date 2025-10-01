"""
Main entry point for the Multi Auto Clicker application.

Clean Code principles:
- Minimal main file
- Dependency injection at the root
- Clear program flow
"""

import tkinter as tk
from gui import AutoClickerGUI


def main() -> None:
    """
    Application entry point.
    
    Clean Code: Simple, clear main function that just starts the app.
    """
    root = tk.Tk()
    app = AutoClickerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
