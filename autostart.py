"""
Autostart Manager for ScreenStick.
Registers or unregisters the app in Windows Startup folder so notes persist
like a wallpaper whenever the computer boots or restarts.
"""

import os
import sys

def get_startup_shortcut_path() -> str:
    """Return path to shortcut in Windows Startup directory."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser(r"~\AppData\Roaming")
    startup_dir = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
    os.makedirs(startup_dir, exist_ok=True)
    return os.path.join(startup_dir, "ScreenStick.lnk")

def is_autostart_enabled() -> bool:
    """Check if startup shortcut currently exists."""
    return os.path.exists(get_startup_shortcut_path())

def set_autostart(enable: bool = True) -> bool:
    """Create or remove Windows startup shortcut."""
    shortcut_path = get_startup_shortcut_path()
    legacy_path = os.path.join(os.path.dirname(shortcut_path), "Quick Sticky Notes.lnk")

    # Clean up legacy startup shortcut if present
    if os.path.exists(legacy_path):
        try:
            os.remove(legacy_path)
        except Exception:
            pass

    if not enable:
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                return True
            except Exception:
                return False
        return True

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)

        workspace_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(workspace_dir, "app.py")

        pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw_path):
            pythonw_path = r"C:\Python314\pythonw.exe"

        shortcut.TargetPath = pythonw_path
        shortcut.Arguments = f'"{app_path}" --startup'
        shortcut.WorkingDirectory = workspace_dir
        shortcut.Description = "ScreenStick - Sticky notes designed to stick directly onto your laptop screen"

        ico_path = os.path.join(workspace_dir, "assets", "icon.ico")
        if os.path.exists(ico_path):
            shortcut.IconLocation = f"{ico_path},0"

        shortcut.save()
        return True
    except Exception as e:
        print(f"Error creating startup shortcut: {e}")
        return False

if __name__ == "__main__":
    success = set_autostart(True)
    print(f"Autostart enabled: {success}")
    print(f"Shortcut location: {get_startup_shortcut_path()}")
    print(f"Exists on disk: {is_autostart_enabled()}")
