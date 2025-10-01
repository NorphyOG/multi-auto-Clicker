"""
Hotkey Manager - handles keyboard shortcuts for starting/stopping the clicker.

SRP: This class has one responsibility - managing keyboard shortcuts.
It doesn't know about clicking logic or UI details.
"""

import keyboard
from typing import Callable, Optional


class HotkeyManager:
    """
    Manages global hotkeys for the application.
    
    Clean Code principles:
    - Clear, descriptive class name
    - Single responsibility (hotkey management only)
    - Minimal dependencies
    """
    
    def __init__(self, start_hotkey: str = 'F6', stop_hotkey: str = 'F7'):
        """
        Initialize the hotkey manager.
        
        Args:
            start_hotkey: Key combination to start the clicker (default: F6)
            stop_hotkey: Key combination to stop the clicker (default: F7)
        """
        self._start_hotkey = start_hotkey
        self._stop_hotkey = stop_hotkey
        self._start_callback: Optional[Callable[[], None]] = None
        self._stop_callback: Optional[Callable[[], None]] = None
        self._is_registered = False
    
    def register_start_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback to be called when start hotkey is pressed.
        
        OCP: Open for extension through callbacks without modifying class.
        """
        self._start_callback = callback
    
    def register_stop_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback to be called when stop hotkey is pressed.
        
        OCP: Open for extension through callbacks without modifying class.
        """
        self._stop_callback = callback
    
    def enable_hotkeys(self) -> bool:
        """
        Enable global hotkeys.
        
        Returns:
            bool: True if hotkeys were successfully registered
        """
        if self._is_registered:
            return True
        
        try:
            if self._start_callback:
                keyboard.add_hotkey(self._start_hotkey, self._start_callback)
            
            if self._stop_callback:
                keyboard.add_hotkey(self._stop_hotkey, self._stop_callback)
            
            self._is_registered = True
            return True
        except Exception as e:
            print(f"Failed to register hotkeys: {e}")
            return False
    
    def disable_hotkeys(self) -> None:
        """
        Disable all registered hotkeys.
        
        Clean Code: Method name clearly describes what it does.
        """
        if not self._is_registered:
            return
        
        try:
            if self._start_callback:
                keyboard.remove_hotkey(self._start_hotkey)
            
            if self._stop_callback:
                keyboard.remove_hotkey(self._stop_hotkey)
            
            self._is_registered = False
        except Exception as e:
            print(f"Error disabling hotkeys: {e}")
    
    def get_start_hotkey(self) -> str:
        """Returns the current start hotkey."""
        return self._start_hotkey
    
    def get_stop_hotkey(self) -> str:
        """Returns the current stop hotkey."""
        return self._stop_hotkey
    
    def update_hotkeys(self, start_hotkey: str, stop_hotkey: str) -> bool:
        """
        Update hotkey bindings.
        
        Args:
            start_hotkey: New start hotkey
            stop_hotkey: New stop hotkey
        
        Returns:
            bool: True if hotkeys were successfully updated
        """
        # Disable current hotkeys
        was_registered = self._is_registered
        if was_registered:
            self.disable_hotkeys()
        
        # Update hotkey bindings
        self._start_hotkey = start_hotkey
        self._stop_hotkey = stop_hotkey
        
        # Re-enable if they were previously enabled
        if was_registered:
            return self.enable_hotkeys()
        
        return True
