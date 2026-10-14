"""
Creates a convenient Windows Desktop Shortcut for ScreenStick.
"""

import os
import sys

def create_shortcut():
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        desktop = shell.SpecialFolders("Desktop")
        shortcut_path = os.path.join(desktop, "ScreenStick.lnk")
        old_shortcut_path = os.path.join(desktop, "Quick Sticky Notes.lnk")

        # Clean up legacy shortcut if present
        if os.path.exists(old_shortcut_path):
            try:
                os.remove(old_shortcut_path)
            except Exception:
                pass
        
        workspace_dir = os.path.dirname(os.path.abspath(__file__))
        target = sys.executable.replace("python.exe", "pythonw.exe")
        arguments = f'"{os.path.join(workspace_dir, "app.py")}"'
        
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = workspace_dir
        shortcut.Description = "ScreenStick - Sticky notes designed to stick directly onto your laptop screen"
        
        ico_path = os.path.join(workspace_dir, "assets", "icon.ico")
        if os.path.exists(ico_path):
            shortcut.IconLocation = f"{ico_path},0"
            
        shortcut.save()
        print(f"Created shortcut at: {shortcut_path}")
        return True
    except Exception as e:
        print(f"Failed to create shortcut: {e}")
        return False

if __name__ == "__main__":
    create_shortcut()
