# Installation Guide

## 1. Verify Python Installation

Open PowerShell (or your preferred terminal) and run:

```powershell
python --version
```

You should see Python 3.10 or higher.

## 2. Install Dependencies

Navigate to the project folder and install the Python packages:

```powershell
pip install -r requirements.txt
```

### Linux prerequisites (Fix for evdev build error)

On Linux, `pynput` pulls in `evdev`, which may need kernel header files and build tools. If you see an error like:

> The 'linux/input.h' and 'linux/input-event-codes.h' include files are missing.

install the headers and build essentials, then re-run pip. Use the command for your distro:

Debian/Ubuntu (apt):

```bash
sudo apt update
sudo apt install build-essential python3-dev linux-headers-"$(uname -r)" python3-tk scrot xclip
```

Fedora (dnf):

```bash
sudo dnf install @development-tools python3-devel kernel-headers kernel-devel python3-tkinter scrot xclip
```

Arch/Manjaro (pacman):

```bash
sudo pacman -S --needed base-devel python linux-headers tk scrot xclip
```

openSUSE (zypper):

```bash
sudo zypper install -t pattern devel_basis
sudo zypper install python3-devel kernel-default-devel python3-tk scrot xclip
```

Then run:

```bash
pip install -r requirements.txt --user
```

Notes:

- If you're on Wayland and global hooks don't work, try an Xorg session.
- Some distros package tkinter as a separate `python3-tk`/`python3-tkinter` package.

## 3. Run the Application

```powershell
python main.py
```

## 4. First Use

1. Click **Add Current Position** to capture your current mouse position, or choose **Add Custom Position** and enter the coordinates manually.
2. Configure your settings:
   - **Clicks per second** – How fast to click (1–100).
   - **Total clicks** – How many clicks to execute (0 = infinite).
   - **Click type** – Left, Right, or Double click.
3. Press **Start** or the start hotkey (default: F6) to begin.
4. Press **Stop** or the stop hotkey (default: F7) to end the session.

## Default Hotkeys

- `<F6>` — Start clicking
- `<F7>` — Stop clicking
- Move the mouse to a corner — Emergency stop (failsafe from PyAutoGUI)

## Troubleshooting

### "pip is not recognized"

Add Python to your PATH or run:

```powershell
python -m pip install -r requirements.txt
```

### "Permission denied" when using hotkeys (Windows)

Run the shell as Administrator and restart the app.

### Clicks not working in some applications

Some programs block simulated input. Try running the app as Administrator or test with a simple target like Notepad first.

### `ModuleNotFoundError`

Ensure you are in the project directory and run:

```powershell
pip install -r requirements.txt
```

On Linux, double-check that the prerequisite system packages listed above are installed if `pyautogui` or `pynput` cannot be imported.

## Tips for Best Results

1. Test with a handful of clicks to confirm the targets are correct.
2. Remember the screen corners for the emergency stop.
3. Start with a low click rate (1–5 CPS) and increase gradually.
4. Add positions in the exact order you want them executed.
5. Use the log export feature if you need to diagnose issues.

## Support

1. Review `README.md` for more detailed documentation.
2. Explore code comments for technical insights.
3. Confirm that you have installed all Python and system prerequisites.

---
Built with Clean Code principles.
