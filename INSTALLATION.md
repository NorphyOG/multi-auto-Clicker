"""
INSTALLATION GUIDE
Multi Auto Clicker
"""

# Quick Start Guide

## Step 1: Verify Python Installation
Open PowerShell and run:
```
python --version
```
You should see Python 3.10 or higher.

## Step 2: Install Dependencies
Navigate to the project folder and run:
```
pip install -r requirements.txt
```

## Step 3: Run the Application
```
python main.py
```

## Step 4: First Use

1. Click "Add Current Position" to add your current mouse position
   - Or use "Add Custom Position" to enter coordinates manually
   
2. Configure your settings:
   - Clicks per second: How fast to click (1-100)
   - Total clicks: How many clicks total (0 = infinite)
   - Click type: Left, Right, or Double click
   
3. Press "Start" or F6 to begin clicking

4. Press "Stop" or F7 to stop clicking

## Hotkeys

- F6: Start clicking
- F7: Stop clicking
- Move mouse to corner: Emergency stop (failsafe)

## Troubleshooting

### Issue: "pip is not recognized"
Solution: Add Python to your PATH or use:
```
python -m pip install -r requirements.txt
```

### Issue: "Permission denied" when using hotkeys
Solution: Run PowerShell as Administrator

### Issue: Clicks not working in some applications
Solution: Some applications block simulated input. Try:
- Running the app as administrator
- Testing with a simple application like Notepad first

### Issue: ModuleNotFoundError
Solution: Ensure you're in the correct directory and have run:
```
pip install -r requirements.txt
```

## Tips for Best Results

1. **Test First**: Start with 1-2 clicks to verify positions are correct
2. **Safety First**: Know where the screen corners are for emergency stop
3. **Start Slow**: Begin with low click rates (1-5 CPS) then increase
4. **Multiple Positions**: Add positions in the order you want them clicked
5. **Check Logs**: Export logs if you encounter issues

## Support

For issues or questions:
1. Check the README.md for detailed documentation
2. Review the code comments for technical details
3. Ensure all requirements are installed correctly

---
Built with Clean Code principles
