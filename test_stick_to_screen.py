import tkinter as tk
import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32

# Window A (Chrome simulation)
win_a = tk.Tk()
win_a.title("Google Chrome (Foreground App)")
win_a.geometry("400x300+100+100")
win_a.update()

# Window B (ScreenStick Note, overlapping win_a)
win_b = tk.Toplevel(win_a)
win_b.title("ScreenStick Note")
win_b.geometry("300x200+200+150") # Overlaps with Chrome!

txt = tk.Text(win_b)
txt.pack(fill="both", expand=True)
txt.insert("1.0", "Stick to Screen note.\nTry clicking here.")
win_b.update()

hwnd_b = user32.GetParent(win_b.winfo_id())
if not hwnd_b:
    hwnd_b = win_b.winfo_id()

hwnd_a = win_a.winfo_id()

HWND_BOTTOM = 1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

def keep_at_bottom(event=None):
    user32.SetWindowPos(hwnd_b, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

# Initially place at bottom
keep_at_bottom()

# Bind events to enforce sticking to wallpaper
for ev in ["<Button-1>", "<ButtonRelease-1>", "<FocusIn>", "<KeyRelease>", "<Configure>"]:
    win_b.bind(ev, keep_at_bottom, add="+")
    txt.bind(ev, keep_at_bottom, add="+")

# Test clicking text widget
txt.focus_set()
txt.insert("end", " typing test...")
keep_at_bottom()

# Verify Z-order: win_a must be higher in Z-order than win_b
# In Windows, GetWindow(hwnd, GW_HWNDPREV) gets the window above in Z-order
GW_HWNDPREV = 3
GW_HWNDNEXT = 2

# Check if hwnd_a is above hwnd_b
# Walking down from top of desktop:
curr = user32.GetTopWindow(user32.GetDesktopWindow())
found_a = False
found_b = False
order = []
while curr:
    if curr == hwnd_a or curr == user32.GetParent(hwnd_a):
        order.append("A")
    elif curr == hwnd_b or curr == win_b.winfo_id():
        order.append("B")
    curr = user32.GetWindow(curr, GW_HWNDNEXT)

print("Z-order from top to bottom (A should be before B):", order)
assert "A" in order and "B" in order, "Windows not found in z-order"
assert order.index("A") < order.index("B"), f"A is not above B! Order: {order}"
print("SUCCESS: Chrome (A) is completely on top of Sticky Note (B)!")

win_a.destroy()
