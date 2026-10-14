"""
ScreenStick - Main Application Controller
Sticky notes desktop application designed to stick directly onto your laptop screen.
"""

import sys
import os
import ctypes
import socket
import threading
import tkinter as tk
import traceback
from typing import Dict, Optional

# Ensure safe streams when launched via pythonw without a console
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from styles import enable_high_dpi, force_foreground_window
from storage import StorageManager
from note_window import NoteWindow
from notes_hub import NotesHub

IPC_PORT = 48921

def try_activate_existing_instance(command: str = "SHOW") -> bool:
    """
    Attempt to connect to an existing running instance on localhost.
    Returns True if an existing instance acknowledged with 'OK'.
    Returns False if no active instance responded (in which case we must take over).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", IPC_PORT))
        s.sendall(f"{command}\n".encode("utf-8"))
        resp = s.recv(1024).decode("utf-8", errors="ignore").strip()
        s.close()
        return "OK" in resp
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass

def cleanup_zombie_instances():
    """Terminate any orphaned pythonw processes running app.py from this directory."""
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
            sys.exit(0)

        self._server_socket = None
        if check_single_instance:
            self._start_ipc_server()

        # High DPI awareness for crisp Windows laptop displays
        enable_high_dpi()

        # Hidden Tk root to anchor all Toplevel sticky windows
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("ScreenStick")

        self.windows: Dict[str, NoteWindow] = {}
        self.hub: Optional[NotesHub] = None

        # Ensure auto-start with Windows is enabled
        try:
            from autostart import set_autostart
            set_autostart(True)
        except Exception:
            pass

        self._init_notes(active_notes, is_startup_mode)

    def _start_ipc_server(self):
        """Run background TCP server on 127.0.0.1:48921 to listen for shortcut clicks."""
        def server_thread():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind(("127.0.0.1", IPC_PORT))
                server.listen(5)
                self._server_socket = server
            except Exception:
                return

            while True:
                try:
                    conn, _ = server.accept()
                    conn.settimeout(1.0)
                    data = conn.recv(1024).decode("utf-8", errors="ignore").strip()
                    if data == "SHOW":
                        self.root.after(0, self.bring_all_notes_to_front)
                    elif data == "NEW":
                        self.root.after(0, self._handle_new_note)
                    conn.sendall(b"OK\n")
                    conn.close()
                except Exception:
                    pass

        t = threading.Thread(target=server_thread, daemon=True)
        t.start()

    def bring_all_notes_to_front(self):
        """Restore and bring all note windows to the front with keyboard focus."""
        self._clean_dead_windows()
        if not self.windows:
            active_notes = self.storage.get_active_notes()
            self._init_notes(active_notes, False)
        else:
            for win in self.windows.values():
                win.lift_to_front()

    def _clean_dead_windows(self):
        """Remove references to any destroyed Tk windows. Shut down if all closed."""
        dead = []
        for nid, w in self.windows.items():
            try:
                if not w.win.winfo_exists():
                    dead.append(nid)
            except Exception:
                dead.append(nid)
        for nid in dead:
            del self.windows[nid]
        if not self.windows and not (self.hub and self.hub.win.winfo_exists()):
            self._shutdown()

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
                self._open_note_window(note, lift=True)
        else:
            for note_data in active_notes:
                self._open_note_window(note_data, lift=not is_startup_mode)

    def _open_note_window(self, note_data: dict, lift: bool = True) -> NoteWindow:
        """Create and display a NoteWindow for the given note data."""
        note_id = note_data["id"]
        if note_id in self.windows:
            try:
                if self.windows[note_id].win.winfo_exists():
                    if lift:
                        self.windows[note_id].lift_to_front()
                    else:
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
        if lift:
            win.lift_to_front()
        else:
            win.focus()
        return win

    def _handle_window_close(self, note_id: str):
        """Called when a note window is closed via ✕, Taskbar or Alt+F4 (keeps note in DB)."""
        win = self.windows.pop(note_id, None)
        if win:
            win.destroy()
        self._clean_dead_windows()

    def _handle_update(self, note_id: str, updates: dict):
        """Save updates to SQLite disk database."""
        self.storage.update_note(note_id, **updates)
        if self.hub and self.hub.win.winfo_exists():
            self.hub.refresh_notes()

    def _handle_delete(self, note_id: str):
        """Handle deleting/removing a note when user clicks ✕."""
        win = self.windows.pop(note_id, None)
        if win:
            win.destroy()

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
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass
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
        win = self._open_note_window(note, lift=True)

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
            self.windows[note_id].lift_to_front()
        else:
            note_data = self.storage.get_note(note_id)
            if note_data:
                self._open_note_window(note_data, lift=True)

    def _handle_delete_permanently(self, note_id: str):
        """Permanently delete note from storage and screen."""
        win = self.windows.pop(note_id, None)
        if win:
            win.destroy()
        self.storage.permanently_delete_note(note_id)
        self._clean_dead_windows()
        if not self.windows:
            if not (self.hub and self.hub.win.winfo_exists()):
                self._shutdown()

    def run(self):
        """Run the main GUI loop."""
        self.root.mainloop()

if __name__ == "__main__":
    is_startup = "--startup" in sys.argv
    if not is_startup:
        if try_activate_existing_instance("SHOW"):
            sys.exit(0)
        cleanup_zombie_instances()

    app = StickyApp()
    app.run()
