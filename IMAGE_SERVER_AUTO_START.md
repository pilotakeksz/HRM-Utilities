# Image Server Auto-Start Setup

## What Was Added to bot.py

The bot now automatically manages the image server lifecycle:

### 1. **Auto-Start on Bot Startup**
- When the bot connects and is ready (`on_ready` event), it automatically starts `image_server.py`
- Image server runs as a subprocess alongside the bot

### 2. **Auto-Stop on Bot Shutdown**
- When bot stops normally: image server stops gracefully
- On Ctrl+C: image server terminates and bot exits cleanly
- On system shutdown: cleanup handlers ensure proper termination

### 3. **Imports Added**
```python
import subprocess  # For process management
import atexit      # For cleanup on exit
import signal      # For handling Ctrl+C
```

### 4. **Functions Added**
- `start_image_server()` - Starts image_server.py as subprocess
- `stop_image_server()` - Gracefully terminates the image server
- `signal_handler()` - Catches Ctrl+C and shutdown signals

## How It Works

```
Bot Starts
    ↓
on_ready() Event Fires
    ↓
start_image_server() Called
    ↓
image_server.py Starts on Port 8889
    ↓
Images Available at http://<your-ip>:8889
    ↓
Bot Stops / Shutdown Signal
    ↓
stop_image_server() Called
    ↓
Image Server Terminates Cleanly
```

## Output When Starting

You'll see:
```
🖼️  Starting image server...
✅ Image server started
```

## Output When Stopping

You'll see:
```
🛑 Stopping image server...
✅ Image server stopped
```

## No Manual Management Needed

- ✅ No need to run `python image_server.py` separately
- ✅ No need to manage process manually
- ✅ Automatic cleanup on bot restart
- ✅ Proper handling of shutdown signals (Ctrl+C)
- ✅ Works on normal shutdown, reboot, and crash recovery

## Accessing Images

Same as before:
- **Local browser**: http://localhost:8889
- **Network/Discord embeds**: http://192.168.178.63:8889

The URLs shown on the image server page are the ones you copy for your embed code!

## Error Handling

If `image_server.py` is not found or fails to start:
- ⚠️ Warning message is printed
- Bot continues running normally
- You can manually start the image server later if needed
