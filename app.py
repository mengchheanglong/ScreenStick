"""
ScreenStick - Main Application Controller
Sticky notes desktop application designed to stick directly onto your laptop screen.
"""

import sys
import os
import ctypes
from ctypes import wintypes
import tkinter as tk
from typing import Dict, Optional

# Ensure safe streams when launched via pythonw without a console
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from styles import enable_high_dpi
from storage import StorageManager
from note_window import NoteWindow
from notes_hub import NotesHub

MUTEX_NAME = "ScreenStick_Application_Mutex_v2"
TRIGGER_FILENAME = ".new_note_trigger"

def get_trigger_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), TRIGGER_FILENAME)

def bring_all_sticky_notes_to_front() -> int:
    """Find all ScreenStick windows currently on the screen and bring them to front."""
    if sys.platform != "win32":
        return 0
    try:
        user32 = ctypes.windll.user32
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        
        found = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if buf.value in ["ScreenStick", "Sticky Note"]:
                        found.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        
        for hwnd in found:
            user32.ShowWindow(hwnd, 9) # SW_RESTORE
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            user32.SetForegroundWindow(hwnd)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        return len(found)
    except Exception:
        return 0

def cleanup_zombie_instances():
    """If another pythonw instance is running app.py with ZERO visible windows, terminate it."""
    my_pid = os.getpid()
    try:
        import psutil
        current_script = os.path.abspath(__file__).lower()
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if p.pid == my_pid:
                    continue
                name = (p.info['name'] or '').lower()
                if 'python' in name:
                    cmdline = [str(arg).lower() for arg in (p.info['cmdline'] or [])]
                    if any(current_script in arg or 'app.py' in arg for arg in cmdline):
                        p.kill()
            except Exception:
                pass
    except Exception:
        pass

class StickyApp:
    def __init__(self, check_single_instance: bool = True):
        is_startup_mode = "--startup" in sys.argv

        self.storage = StorageManager()
        active_notes = self.storage.get_active_notes()

        # If launched on Windows boot and user has NO notes on desktop, exit quietly
        if is_startup_mode and not active_notes:
            os._exit(0)

        self._mutex = None
        if check_single_instance and sys.platform == "win32":
            vis_count = bring_all_sticky_notes_to_front()
            if vis_count > 0:
                # Visible ScreenStick notes are already on the user's screen!
                # Drop trigger file to spawn a new note or focus an empty one
                try:
                    with open(get_trigger_path(), "w") as f:
                        f.write("NEW")
                except Exception:
                    pass
                os._exit(0)
            else:
                # ZERO visible notes on screen! Kill any headless ghost processes
                cleanup_zombie_instances()
                # Acquire fresh mutex
                kernel32 = ctypes.windll.kernel32
                self._mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)

        # High DPI awareness for crisp Windows laptop displays
        enable_high_dpi()

        # Hidden Tk root to anchor all Toplevel sticky windows
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("ScreenStick")

        self.windows: Dict[str, NoteWindow] = {}
        self.hub: Optional[NotesHub] = None

        # Watch for triggers from subsequent shortcut clicks
        self._check_trigger_file()

        # Ensure auto-start with Windows is enabled
        try:
            from autostart import set_autostart
            set_autostart(True)
        except Exception:
            pass

        self._init_notes(active_notes, is_startup_mode)

    def _clean_dead_windows(self):
        """Remove references to any destroyed Tk windows."""
        dead = []
        for nid, w in self.windows.items():
            try:
                if not w.win.winfo_exists():
                    dead.append(nid)
            except Exception:
                dead.append(nid)
        for nid in dead:
            del self.windows[nid]

    def _check_trigger_file(self):
        """Poll for trigger file created when user clicks shortcut while app is running."""
        self._clean_dead_windows()
        trigger_path = get_trigger_path()
        if os.path.exists(trigger_path):
            try:
                os.remove(trigger_path)
            except Exception:
                pass
            # Focus existing notes or spawn new note
            if not self.windows:
                active_notes = self.storage.get_active_notes()
                self._init_notes(active_notes, False)
            else:
                for win in self.windows.values():
                    win.focus()
                empty_notes = [w for w in self.windows.values() if not w.text_widget.get("1.0", "end-1c").strip() or w._is_placeholder_active]
                if empty_notes:
                    empty_notes[0].focus()
                else:
                    self._handle_new_note()

        self.root.after(350, self._check_trigger_file)

    def _init_notes(self, active_notes, is_startup_mode: bool):
        """Open existing active notes, or create one clean starter note on manual launch."""
        if not active_notes:
            if not is_startup_mode:
                note = self.storage.create_note(
                    text="",
                    x=320,
                    y=160,
                    width=280,
                    height=240,
                    color="yellow",
                    is_pinned=False
                )
                self._open_note_window(note)
        else:
            for note_data in active_notes:
                self._open_note_window(note_data)

    def _open_note_window(self, note_data: dict) -> NoteWindow:
        """Create and display a NoteWindow for the given note data."""
        note_id = note_data["id"]
        if note_id in self.windows:
            try:
                if self.windows[note_id].win.winfo_exists():
                    self.windows[note_id].focus()
                    return self.windows[note_id]
            except Exception:
                pass

        win = NoteWindow(
            master=self.root,
            note_data=note_data,
            on_update=self._handle_update,
            on_delete=self._handle_delete,
            on_new_note=self._handle_new_note,
            on_open_hub=self.open_notes_hub,
            on_close_window=self._handle_window_close
        )
        self.windows[note_id] = win
        win.focus()
        return win

    def _handle_window_close(self, note_id: str):
        """Called when a note window is closed via Taskbar or Alt+F4 (keeps note in DB)."""
        if note_id in self.windows:
            del self.windows[note_id]
        self._clean_dead_windows()
        if not self.windows:
            if not (self.hub and self.hub.win.winfo_exists()):
                self._shutdown()

    def _handle_update(self, note_id: str, updates: dict):
        """Save updates to SQLite disk database."""
        self.storage.update_note(note_id, **updates)
        if self.hub and self.hub.win.winfo_exists():
            self.hub.refresh_notes()

    def _handle_delete(self, note_id: str):
        """Handle deleting/removing a note when user clicks ✕."""
        if note_id in self.windows:
            try:
                self.windows[note_id].destroy()
            except Exception:
                pass
            if note_id in self.windows:
                del self.windows[note_id]

        self.storage.soft_delete_note(note_id)

        if self.hub and self.hub.win.winfo_exists():
            self.hub.refresh_notes()

        self._clean_dead_windows()
        # When all notes are closed, exit cleanly and terminate the process completely!
        if not self.windows:
            if not (self.hub and self.hub.win.winfo_exists()):
                self._shutdown()

    def _shutdown(self):
        """Cleanly terminate the application and release all OS resources."""
        try:
            self.root.destroy()
        except Exception:
            pass
        if self._mutex and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex)
            except Exception:
                pass
        # os._exit immediately terminates all threads and releases all kernel handles
        os._exit(0)

    def _handle_new_note(self, x: Optional[int] = None, y: Optional[int] = None):
        """Create a new note with automatic cascade placement (unpinned by default)."""
        self._clean_dead_windows()
        if x is None or y is None:
            count = len(self.windows)
            x = 220 + (count % 6) * 35
            y = 160 + (count % 6) * 35

        colors = ["yellow", "green", "blue", "pink", "purple", "orange"]
        chosen_color = colors[len(self.windows) % len(colors)]

        note = self.storage.create_note(
            text="",
            x=x,
            y=y,
            width=280,
            height=240,
            color=chosen_color,
            is_pinned=False
        )
        win = self._open_note_window(note)
        win.focus()

        if self.hub and self.hub.win.winfo_exists():
            self.hub.refresh_notes()

    def open_notes_hub(self):
        """Open or focus the central Notes Hub."""
        if self.hub is None or not self.hub.win.winfo_exists():
            self.hub = NotesHub(
                master=self.root,
                storage=self.storage,
                on_open_note=self._open_existing_note,
                on_create_note=lambda: self._handle_new_note(),
                on_delete_permanently=self._handle_delete_permanently
            )
        else:
            self.hub.show()

    def _open_existing_note(self, note_id: str):
        """Open or focus a note by ID."""
        if note_id in self.windows and self.windows[note_id].win.winfo_exists():
            self.windows[note_id].focus()
        else:
            note_data = self.storage.get_note(note_id)
            if note_data:
                win = self._open_note_window(note_data)
                win.focus()

    def _handle_delete_permanently(self, note_id: str):
        """Permanently delete note from storage and screen."""
        if note_id in self.windows:
            try:
                self.windows[note_id].destroy()
            except Exception:
                pass
            if note_id in self.windows:
                del self.windows[note_id]
        self.storage.permanently_delete_note(note_id)
        self._clean_dead_windows()
        if not self.windows:
            if not (self.hub and self.hub.win.winfo_exists()):
                self._shutdown()

    def run(self):
        """Run the main GUI loop."""
        self.root.mainloop()

if __name__ == "__main__":
    app = StickyApp()
    app.run()
