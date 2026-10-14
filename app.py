import sys
import os
import socket
import threading
import tkinter as tk

# Ensure safe streams when launched via pythonw without a console
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from typing import Dict, Optional
from styles import enable_high_dpi
from storage import StorageManager
from note_window import NoteWindow
from notes_hub import NotesHub

IPC_PORT = 47892

def bring_all_sticky_notes_to_front() -> int:
    """Find all Sticky Note windows currently on the screen and bring them to front."""
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        from ctypes import wintypes
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
            user32.ShowWindow(hwnd, 9)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            user32.SetForegroundWindow(hwnd)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        return len(found)
    except Exception:
        return 0

def try_send_ipc_message(message: str = "NEW") -> bool:
    """Send command to an already running instance and require acknowledgement."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect(("127.0.0.1", IPC_PORT))
        s.sendall(message.encode("utf-8"))
        resp = s.recv(1024).decode("utf-8").strip()
        s.close()
        return resp.startswith("OK")
    except Exception:
        return False

class StickyApp:
    def __init__(self, check_single_instance: bool = True):
        is_startup_mode = "--startup" in sys.argv

        # Check if an instance is already running
        if check_single_instance:
            if try_send_ipc_message("STARTUP" if is_startup_mode else "NEW"):
                bring_all_sticky_notes_to_front()
                sys.exit(0)

        self.storage = StorageManager()
        active_notes = self.storage.get_active_notes()

        # If launched on Windows boot and user has NO notes on desktop, exit quietly
        if is_startup_mode and not active_notes:
            sys.exit(0)

        # High DPI awareness for crisp Windows laptop displays
        enable_high_dpi()

        # Hidden Tk root to anchor all Toplevel sticky windows
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("ScreenStick")

        self.windows: Dict[str, NoteWindow] = {}
        self.hub: Optional[NotesHub] = None

        # Start IPC server to listen for new clicks on desktop shortcut
        self._start_ipc_server()

        # Ensure auto-start with Windows is enabled
        try:
            from autostart import set_autostart
            set_autostart(True)
        except Exception:
            pass

        self._init_notes(active_notes, is_startup_mode)

    def _start_ipc_server(self):
        """Listen on local port so subsequent shortcut clicks create notes in this process."""
        def listener():
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("127.0.0.1", IPC_PORT))
                srv.listen(5)
                srv.settimeout(1.0)
                while True:
                    try:
                        conn, _ = srv.accept()
                        data = conn.recv(1024).decode("utf-8").strip()
                        conn.sendall(b"OK\n")
                        conn.close()
                        if data == "NEW":
                            self.root.after(10, self._on_ipc_new)
                        elif data == "STARTUP":
                            self.root.after(10, self._on_ipc_startup)
                    except socket.timeout:
                        continue
                    except Exception:
                        break
            except Exception:
                pass

        t = threading.Thread(target=listener, daemon=True)
        t.start()

    def _on_ipc_new(self):
        """User clicked desktop shortcut while app is running -> spawn or focus note."""
        if not self.windows:
            self._handle_new_note(320, 160)
        else:
            for win in self.windows.values():
                win.focus()
            empty_notes = [w for w in self.windows.values() if not w.text_widget.get("1.0", "end-1c").strip() or w._is_placeholder_active]
            if empty_notes:
                empty_notes[0].focus()
            else:
                self._handle_new_note()

    def _on_ipc_startup(self):
        """Startup triggered while already running."""
        for win in self.windows.values():
            win.focus()

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
            self.windows[note_id].focus()
            return self.windows[note_id]

        win = NoteWindow(
            master=self.root,
            note_data=note_data,
            on_update=self._handle_update,
            on_delete=self._handle_delete,
            on_new_note=self._handle_new_note,
            on_open_hub=self.open_notes_hub
        )
        self.windows[note_id] = win
        win.focus()
        return win

    def _handle_update(self, note_id: str, updates: dict):
        """Save updates to SQLite disk database."""
        self.storage.update_note(note_id, **updates)
        if self.hub and self.hub.win.winfo_exists():
            self.hub.refresh_notes()

    def _handle_delete(self, note_id: str):
        """Handle closing/deleting a note."""
        if note_id in self.windows:
            self.windows[note_id].destroy()
            del self.windows[note_id]

        self.storage.soft_delete_note(note_id)

        if self.hub and self.hub.win.winfo_exists():
            self.hub.refresh_notes()

        # When the last note is deleted:
        # Exit cleanly! DO NOT respawn any note!
        # The desktop screen is now completely clean.
        if not self.windows:
            if not (self.hub and self.hub.win.winfo_exists()):
                self.root.destroy()
                sys.exit(0)

    def _handle_new_note(self, x: Optional[int] = None, y: Optional[int] = None):
        """Create a new note with automatic position cascade (unpinned by default)."""
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
        if note_id in self.windows:
            self.windows[note_id].focus()
        else:
            note_data = self.storage.get_note(note_id)
            if note_data:
                win = self._open_note_window(note_data)
                win.focus()

    def _handle_delete_permanently(self, note_id: str):
        """Permanently delete note from storage and screen."""
        if note_id in self.windows:
            self.windows[note_id].destroy()
            del self.windows[note_id]
        self.storage.permanently_delete_note(note_id)
        if not self.windows:
            if not (self.hub and self.hub.win.winfo_exists()):
                self.root.destroy()
                sys.exit(0)

    def run(self):
        """Run the main GUI loop."""
        self.root.mainloop()

if __name__ == "__main__":
    app = StickyApp()
    app.run()
