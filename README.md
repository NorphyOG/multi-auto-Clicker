# Multi Auto Clicker

A professional, well-architected auto-clicker application built with Clean Code principles and SOLID design patterns.

## Features

✅ **Start/Stop Auto-Clicking** – Start and stop automatic clicking with buttons or hotkeys  
✅ **Flexible Positioning** – Capture live positions, add manual coordinates, or follow the cursor  
✅ **Multi-Monitor Ready** – Negative coordinates supported for extended desktops  
✅ **Configurable Click Rate** – Set clicks per second (0.1 to 1000+ CPS)  
✅ **Click Count Control** – Set total clicks or run infinitely  
✅ **Multiple Click Types** – Left, right, or double click  
✅ **Configurable Hotkeys** – Choose your own start/stop shortcuts (defaults: F6/F7)  
✅ **Persistent Settings** – Last-used configuration saved automatically  
✅ **Automation Tab** – Background automation with optional minimize & infinite mode  
✅ **Debug Overlay** – Visual ✕ markers for every target (toggle anytime)  
✅ **Live CPS Monitor** – Separate statistics for manual and automation sessions  
✅ **Real-time Status & Logs** – Live counters plus exportable activity log  
✅ **Clean GUI** – Intuitive Tkinter interface built with SOLID principles

## Installation

### Prerequisites

- Python 3.10 or higher

### Setup

1. **Clone or download** this repository

2. **Install dependencies**:

```powershell
pip install -r requirements.txt
```

## Usage

### Starting the Application

```powershell
python main.py
```

### Using the Application

1. **Add Click Positions**:
   - Click "Aktuelle Position" to capture your current mouse position
   - Click "Benutzerdefiniert" to manually enter coordinates (supports negative values for multi-monitor setups)
   - Use "Nächsten Klick aufnehmen" to capture the next mouse click globally via `pynput`
   - Add labels to keep target lists organized

2. **Configure Settings**:
   - **Clicks per second**: How fast to click (default: 5, supports triple-digit CPS)
   - **Total clicks**: Number of clicks (0 = infinite)
   - **Click type**: Choose left, right, or double click
   - **Modus**: Select fixed positions or follow the cursor dynamically
   - **Debug-Modus**: Toggle ✕ overlay to verify targets across monitors

3. **Start Clicking**:
   - Click "Start" or press the configured hotkey
   - In positions mode, the clicker iterates through the list
   - In follow-cursor mode, clicks track the live cursor position

4. **Stop Clicking**:
   - Click "Stop" or press the configured hotkey
   - PyAutoGUI failsafe: move mouse to screen corner to abort instantly

5. **Monitor Live Stats**:
   - The section "Live-Statistiken" shows executed clicks and measured CPS in real time
   - Automation runs display corresponding counters in their control panel

### Automatisierungs-Tab

1. Configure whether to minimize the window automatically and whether to ignore the total click count (infinite mode)
2. Press "Start (Hintergrund)" to run the engine without bringing the GUI to front
3. Monitor dedicated status, click counters, and CPS; press "Stop" to end the run

All automation runs reuse the settings from the manual tab, including target lists, speed, and click type.

### Hotkeys

- **F6** - Start auto-clicking
- **F7** - Stop auto-clicking

## Architecture

This application follows **Clean Code** principles and **SOLID** design patterns:

### Project Structure

```text
multi auto Clicker/
│
├── main.py              # Application entry point
├── models.py            # Domain models (ClickPosition, ClickConfiguration, etc.)
├── clicker_engine.py    # Core clicking logic (business layer)
├── gui.py               # User interface (presentation layer)
├── hotkey_manager.py    # Global hotkey management
├── logger.py            # Status and logging system
├── settings_manager.py  # JSON persistence for application settings
├── debug_overlay.py     # ✕ overlay for visualising targets
├── click_capture.py     # Global mouse capture for adding positions
└── requirements.txt     # Python dependencies
```

### Design Principles Applied

#### 1. **Single Responsibility Principle (SRP)**

Each class has one clear responsibility:

- `ClickPosition` - Represents a screen coordinate
- `ClickConfiguration` - Encapsulates click settings
- `AutoClickerEngine` - Handles clicking logic
- `HotkeyManager` - Manages keyboard shortcuts
- `StatusLogger` - Tracks status and logs
- `SettingsManager` - Persists and restores user preferences
- `DebugOverlayManager` - Renders ✕ markers on every monitor
- `ClickCaptureService` - Captures the next global mouse click
- `AutoClickerGUI` - Presents the user interface

#### 2. **Open/Closed Principle (OCP)**

Classes are open for extension but closed for modification:

- Callbacks allow extending functionality without modifying core classes
- Configuration objects allow new parameters without breaking existing code

#### 3. **Dependency Inversion Principle (DIP)**

High-level modules don't depend on low-level details:

- GUI depends on abstractions (Engine, Logger) not implementations
- Engine uses callbacks instead of direct UI coupling

#### 4. **Clean Code Practices**

- **Descriptive names**: `get_delay_between_clicks()`, `is_infinite_mode()`
- **Small functions**: Each method does one thing well
- **No magic numbers**: Configuration values are named and validated
- **Clear comments**: Explain *why*, not *what*
- **Minimal nesting**: Early returns and guard clauses

#### 5. **DRY (Don't Repeat Yourself)**

- Position list refresh logic centralized
- Logging logic unified in StatusLogger
- Click execution in single method

#### 6. **YAGNI (You Aren't Gonna Need It)**

- No over-engineering
- Features implemented only as needed
- Simple, elegant solutions

## Code Quality Features

### Type Hints

All functions have proper type hints for better IDE support and error detection.

### Data Validation

- Coordinates are validated and support negative values for extended displays
- Click rate must be positive (safeguarded with lower bound)
- Configuration validated before starting the engine

### Error Handling

- Try-catch blocks for I/O operations
- User-friendly error messages
- Graceful degradation

### Thread Safety

- Engine runs in separate thread
- Thread-safe stop mechanism
- Proper cleanup on exit

### Resource Management

- Proper cleanup in `_on_closing()`
- Hotkeys disabled on exit
- Settings persisted before shutdown
- Threads properly joined

## Safety Features

1. **PyAutoGUI Failsafe**: Move mouse to screen corner to emergency stop
2. **Thread Management**: Clean thread shutdown
3. **Input Validation**: All user inputs validated
4. **Error Recovery**: Graceful error handling

## Troubleshooting

### "Import could not be resolved"

This is normal before installing dependencies. Run:

```powershell
pip install -r requirements.txt
```

### Hotkeys not working

- Ensure you're running with appropriate permissions
- Check if another app is using the same keys
- Try running as administrator
- Use the Hotkeys section in the GUI to select different combinations

### Clicks not registering

- Check that positions are visible on screen (overlay can help)
- Ensure target application accepts simulated clicks
- Verify click positions are correct
- Try enabling "Cursor folgen" for moving targets

## Future Enhancements (YAGNI applied - not implemented)

Potential features for future versions:

- Click patterns (circles, squares)
- Random click delays
- Multiple click profiles
- Record and playback
- Click intervals per position

## License

MIT License - Feel free to use and modify

## Contributing

When contributing, please maintain:

- Clean Code principles
- SOLID design patterns
- Comprehensive type hints
- Descriptive variable/function names
- Single Responsibility per class/method
- Regression-safe documentation updates when adding features

---

**Built with Clean Code in mind** 🎯
