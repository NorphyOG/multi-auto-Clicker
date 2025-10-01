"""
Status Logger - tracks and displays the status of the auto-clicker.

SRP: This class has one responsibility - logging and status management.
"""

from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class LogEntry:
    """
    Represents a single log entry.
    
    Clean Code: Simple data class with descriptive name and fields.
    """
    timestamp: datetime
    message: str
    level: str = "INFO"
    
    def __str__(self) -> str:
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] {self.level}: {self.message}"


class StatusLogger:
    """
    Manages status updates and maintains a log history.
    
    Clean Code principles:
    - Small, focused methods
    - Clear naming
    - No side effects on external state
    """
    
    def __init__(self, max_entries: int = 100):
        """
        Initialize the logger.
        
        Args:
            max_entries: Maximum number of log entries to keep in memory
        """
        self._log_entries: List[LogEntry] = []
        self._max_entries = max_entries
        self._current_status = "Ready"
    
    def log_info(self, message: str) -> None:
        """
        Log an informational message.
        
        Clean Code: Method name clearly describes what it does.
        """
        self._add_entry(message, "INFO")
    
    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self._add_entry(message, "WARNING")
    
    def log_error(self, message: str) -> None:
        """Log an error message."""
        self._add_entry(message, "ERROR")
    
    def update_status(self, status: str) -> None:
        """
        Update the current status.
        
        Args:
            status: The new status message
        """
        self._current_status = status
        self.log_info(status)
    
    def get_current_status(self) -> str:
        """Returns the current status message."""
        return self._current_status
    
    def get_recent_logs(self, count: int = 10) -> List[LogEntry]:
        """
        Get the most recent log entries.
        
        Args:
            count: Number of recent entries to return
        
        Returns:
            List of recent log entries
        """
        return self._log_entries[-count:]
    
    def get_all_logs(self) -> List[LogEntry]:
        """Returns all log entries."""
        return self._log_entries.copy()
    
    def clear_logs(self) -> None:
        """Clear all log entries."""
        self._log_entries.clear()
        self.log_info("Log history cleared")
    
    def _add_entry(self, message: str, level: str) -> None:
        """
        Add a new log entry.
        
        Clean Code: Private method for internal use only.
        DRY: Centralized logic for adding entries.
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            message=message,
            level=level
        )
        
        self._log_entries.append(entry)
        
        # Trim old entries if we exceed max
        if len(self._log_entries) > self._max_entries:
            self._log_entries = self._log_entries[-self._max_entries:]
    
    def export_logs_to_file(self, filepath: str) -> bool:
        """
        Export all logs to a text file.
        
        Args:
            filepath: Path where the log file should be saved
        
        Returns:
            bool: True if export was successful
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("Multi Auto Clicker - Log Export\n")
                f.write(f"Generated: {datetime.now()}\n")
                f.write("=" * 50 + "\n\n")
                
                for entry in self._log_entries:
                    time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{time_str}] {entry.level}: {entry.message}\n")
            
            return True
        except Exception as e:
            print(f"Failed to export logs: {e}")
            return False
