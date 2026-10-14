"""
Automated validation test for Sticky Notes application.
Tests multi-note creation, persistence, color switching, formatting tags, and Notes Hub.
"""

import os
import shutil
import tkinter as tk
from app import StickyApp
from storage import StorageManager

def run_tests():
    test_storage_path = os.path.join(os.path.dirname(__file__), "test_notes.db")
    if os.path.exists(test_storage_path):
        os.remove(test_storage_path)

    print("--- 1. Testing StorageManager ---")
    storage = StorageManager(test_storage_path)
    n1 = storage.create_note(text="Note 1", x=100, y=100, color="yellow")
    n2 = storage.create_note(text="Note 2", x=200, y=200, color="pink")
    assert len(storage.get_active_notes()) == 2, "Expected 2 active notes"

    storage.update_note(n1["id"], text="Updated Note 1")
    reloaded = StorageManager(test_storage_path)
    assert reloaded.get_note(n1["id"])["text"] == "Updated Note 1", "Persistence failed!"
    print("StorageManager tests passed!")

    print("--- 2. Testing StickyApp & Windows ---")
    app = StickyApp(check_single_instance=False)
    # Force use of test storage
    app.storage = storage

    # Test creating additional notes
    app._handle_new_note(x=350, y=250)
    assert len(app.windows) >= 2, "Multiple notes window creation failed!"

    # Test color update
    note_id = list(app.windows.keys())[0]
    win = app.windows[note_id]
    win._select_color("purple", tk.Toplevel(app.root))
    assert win.color_key == "purple", "Color change failed"

    # Test text editing & formatting tags
    win.text_widget.insert("end", "\nImportant task")
    win._apply_tag("bold")
    win._do_save()

    # Test collapse
    win.toggle_collapse()
    assert win.is_collapsed == True, "Collapse failed"
    win.toggle_collapse()
    assert win.is_collapsed == False, "Expand failed"

    # Test pin toggle
    prev_pin = win.is_pinned
    win.toggle_pin()
    assert win.is_pinned != prev_pin, "Pin toggle failed"

    # Test Notes Hub
    app.open_notes_hub()
    assert app.hub is not None, "Notes Hub failed to open"
    app.hub.search_var.set("task")
    app.hub.refresh_notes()

    app.root.destroy()
    if os.path.exists(test_storage_path):
        try:
            os.remove(test_storage_path)
        except Exception:
            pass

    print("--- ALL TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    run_tests()
