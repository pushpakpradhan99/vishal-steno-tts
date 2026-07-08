import os
import sys
import json
import urllib.request
import urllib.error

# Add current folder to path so it can import gui.py
app_dir = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
sys.path.insert(0, app_dir)

# Add local ffmpeg to path
ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
if os.path.exists(ffmpeg_dir):
    os.environ["PATH"] += os.pathsep + ffmpeg_dir

# Configuration URLs - The user can edit these values once their repo is set up!
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/pushpakpradhan99/vishal-steno-tts/main/version.json"
GITHUB_GUI_URL = "https://raw.githubusercontent.com/pushpakpradhan99/vishal-steno-tts/main/gui.py"

LOCAL_VERSION_FILE = os.path.join(app_dir, "version.json")
LOCAL_GUI_FILE = os.path.join(app_dir, "gui.py")

# ==============================================================================
# STATIC ANALYZER DEPENDENCY IMPORT TRICK
# ==============================================================================
if False:
    # These imports are never executed but force PyInstaller to bundle them.
    import PySide6.QtCore
    import PySide6.QtGui
    import PySide6.QtWidgets
    import PySide6.QtMultimedia
    import edge_tts
    import aiohttp
    import certifi
    import shutil
    import PIL
    import PIL.Image
    import PIL.ImageOps
    import PIL.ImageDraw

def get_local_version():
    if os.path.exists(LOCAL_VERSION_FILE):
        try:
            with open(LOCAL_VERSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version", "0.0.0")
        except Exception:
            pass
    return "0.0.0"

def save_local_version(version):
    try:
        with open(LOCAL_VERSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"version": version}, f, indent=4)
    except Exception:
        pass

def check_for_updates():
    local_ver = get_local_version()
    print(f"Local version: {local_ver}")
    print("Checking for updates from GitHub...")
    
    try:
        # Check remote version with a timeout of 3 seconds
        with urllib.request.urlopen(GITHUB_VERSION_URL, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                remote_ver = data.get("version", "0.0.0")
                print(f"Remote version: {remote_ver}")
                
                if remote_ver > local_ver:
                    print("Updating application layout...")
                    # Download the updated gui.py
                    with urllib.request.urlopen(GITHUB_GUI_URL, timeout=5) as gui_resp:
                        if gui_resp.status == 200:
                            gui_code = gui_resp.read()
                            with open(LOCAL_GUI_FILE, "wb") as f_gui:
                                f_gui.write(gui_code)
                            save_local_version(remote_ver)
                            print("Application updated successfully!")
                            return True
                else:
                    print("Application is up-to-date.")
    except Exception as e:
        print(f"Update check skipped/failed: {e} (Offline mode or connection error)")
    return False

if __name__ == "__main__":
    # Perform update check (non-blocking errors)
    check_for_updates()
    
    # Import and run gui.py
    try:
        import gui
        gui.run_app()
    except Exception as e:
        # Fallback error message if app failed to launch
        import traceback
        err_msg = traceback.format_exc()
        print(err_msg)
        
        # If GUI launcher failed, show a Windows message box (since PySide6 itself might fail to load)
        try:
            from PySide6.QtWidgets import QMessageBox, QApplication
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "Application Error", f"Failed to launch the application:\n{e}\n\nTraceback:\n{err_msg}")
        except Exception:
            # Fallback to standard ctypes message box on Windows
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Critical launcher error:\n{e}", "Launcher Error", 0x10 | 0x0)
