"""
Auto-Clicker Engine - the core business logic.

SRP: This class has one responsibility - executing automated clicks.
It doesn't know about UI, hotkeys, or logging (Dependency Inversion Principle).
"""

import time
import threading
from typing import Optional, Callable
import pyautogui

from models import ClickConfiguration, ClickerState, ClickType, ClickPosition, ClickMode


class AutoClickerEngine:
    """
    Core engine for automated clicking.
    
    Clean Code principles applied:
    - Descriptive name that clearly indicates purpose
    - Small, focused methods with single responsibilities
    - Clear separation of concerns
    """
    
    def __init__(self, configuration: ClickConfiguration):
        """
        Initialize the engine with a configuration.
        
        DIP: Depends on abstraction (ClickConfiguration) not concrete details.
        """
        self._config = configuration
        self._state = ClickerState.STOPPED
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._clicks_executed = 0
        self._status_callback: Optional[Callable[[str], None]] = None
        
        # Configure pyautogui for safety
    pyautogui.FAILSAFE = True  # Move mouse to corner to stop
    pyautogui.PAUSE = 0.0  # Allow CPS above 100 without artificial delay
    
    def register_status_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for status updates.
        
        OCP: Open for extension (can add callbacks) without modifying core logic.
        """
        self._status_callback = callback
    
    def start(self) -> bool:
        """
        Start the auto-clicker in a separate thread.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self._state == ClickerState.RUNNING:
            self._notify_status("Already running")
            return False
        
        self._stop_flag.clear()
        self._clicks_executed = 0
        self._state = ClickerState.RUNNING
        
        self._worker_thread = threading.Thread(target=self._click_worker, daemon=True)
        self._worker_thread.start()
        
        self._notify_status("Auto-clicker started")
        return True
    
    def stop(self) -> None:
        """
        Stop the auto-clicker gracefully.
        
        Clean Code: Method name is clear and unambiguous.
        """
        if self._state != ClickerState.RUNNING:
            return
        
        self._stop_flag.set()
        self._state = ClickerState.STOPPED
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        
        self._notify_status(f"Auto-clicker stopped. Total clicks: {self._clicks_executed}")
    
    def get_state(self) -> ClickerState:
        """Returns the current state of the clicker."""
        return self._state
    
    def get_clicks_executed(self) -> int:
        """Returns the number of clicks executed in current session."""
        return self._clicks_executed
    
    def is_running(self) -> bool:
        """Check if the clicker is currently running."""
        return self._state == ClickerState.RUNNING
    
    def _click_worker(self) -> None:
        """
        Worker thread that performs the actual clicking.
        
        Clean Code: Private method (indicated by _prefix) that's only
        called internally. Keeps implementation details hidden.
        """
        try:
            delay = self._config.get_delay_between_clicks()

            if self._config.click_mode == ClickMode.FOLLOW_CURSOR:
                self._run_follow_cursor_loop(delay)
            else:
                self._run_static_sequence_loop(delay)

            self._state = ClickerState.STOPPED
            self._notify_status(f"Completed. Total clicks: {self._clicks_executed}")

        except Exception as e:
            self._state = ClickerState.ERROR
            self._notify_status(f"Error: {str(e)}")
    
    def _run_static_sequence_loop(self, delay: float) -> None:
        """Execute clicking loop for static sequence mode."""
        position_count = len(self._config.click_positions)
        current_position_index = 0

        while not self._stop_flag.is_set():
            if not self._config.is_infinite_mode() and \
               self._clicks_executed >= self._config.total_clicks:
                break

            position = self._config.click_positions[current_position_index]
            self._perform_click(position)

            self._clicks_executed += 1
            current_position_index = (current_position_index + 1) % position_count

            if self._clicks_executed % 10 == 0:
                self._notify_status(f"Clicks executed: {self._clicks_executed}")

            time.sleep(delay)

    def _run_follow_cursor_loop(self, delay: float) -> None:
        """Execute clicking loop that follows the live cursor position."""
        while not self._stop_flag.is_set():
            if not self._config.is_infinite_mode() and \
               self._clicks_executed >= self._config.total_clicks:
                break

            self._perform_click(position=None)
            self._clicks_executed += 1

            if self._clicks_executed % 10 == 0:
                self._notify_status(f"Clicks executed: {self._clicks_executed}")

            time.sleep(delay)

    def _perform_click(self, position: Optional[ClickPosition]) -> None:
        """Perform a click either at a fixed position or at the current cursor."""
        button = 'left'
        if self._config.click_type == ClickType.RIGHT:
            button = 'right'

        if self._config.click_type == ClickType.DOUBLE:
            if position:
                x, y = position.to_tuple()
                pyautogui.doubleClick(x=x, y=y, button=button)
            else:
                pyautogui.doubleClick(button=button)
            return

        if position:
            x, y = position.to_tuple()
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
    
    def _notify_status(self, message: str) -> None:
        """
        Notify registered callbacks about status changes.
        
        DRY: Centralized status notification logic.
        """
        if self._status_callback:
            self._status_callback(message)
