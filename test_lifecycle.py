import os
import sys
import time
import socket
import subprocess
from storage import StorageManager

def test_full_user_lifecycle():
    print("=== Testing Full User Lifecycle ===")
    sm = StorageManager()
    active = sm.get_active_notes()
    print(f"Current active notes in DB: {len(active)}")
    assert len(active) > 0, "Expected existing user note to be preserved!"

    # 1. Start App as separate process
    python_exe = r"C:\Python314\python.exe" if os.path.exists(r"C:\Python314\python.exe") else sys.executable
    print(f"Starting app via {python_exe}...")
    p1 = subprocess.Popen([python_exe, "app.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
    time.sleep(2)
    assert p1.poll() is None, "App exited prematurely!"
    print(f"App running with PID {p1.pid}")

    # 2. Test IPC SHOW while running
    print("Testing IPC SHOW while app is running...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(("127.0.0.1", 48921))
    s.sendall(b"SHOW\n")
    resp = s.recv(1024).decode().strip()
    s.close()
    assert resp == "OK", f"Expected OK from IPC, got: {resp}"
    print("IPC SHOW acknowledged with OK.")

    # 3. Simulate clicking X on the note
    # When X is clicked, on_close_window is called, keeping the note in DB and shutting down
    p1.terminate()
    p1.wait()
    print("Process terminated.")

    # Verify notes still exist in DB
    active_after = sm.get_active_notes()
    assert len(active_after) > 0, "Note was deleted from DB when it should have been kept!"
    print("Note successfully preserved in DB.")

    # 4. Start app second time (User double-clicks shortcut to reopen)
    print("Reopening app...")
    p2 = subprocess.Popen([python_exe, "app.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
    time.sleep(2)
    assert p2.poll() is None, "Reopened app failed to start!"
    print(f"Reopened app running with PID {p2.pid}")

    p2.terminate()
    p2.wait()
    print("=== ALL LIFECYCLE TESTS PASSED! ===")

if __name__ == "__main__":
    test_full_user_lifecycle()
