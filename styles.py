"""
Styles and Windows-specific system integrations for Sticky Notes.
Provides modern pastel color palettes, typography, DPI scaling, and DWM window enhancements.
"""

import sys
import ctypes
from ctypes import wintypes

# Modern pastel color palette inspired by modern UI design
THEMES = {
    "yellow": {
        "name": "Butter Yellow",
        "bg": "#FFFBEB",
        "header_bg": "#FEF3C7",
        "btn_hover": "#FDE68A",
        "border": "#FCD34D",
        "fg": "#1C1917",
        "muted_fg": "#78716C",
        "toolbar_bg": "#FEF3C7",
        "accent": "#D97706",
        "placeholder": "#A8A29E"
    },
    "green": {
        "name": "Sage Mint",
        "bg": "#F0FDF4",
        "header_bg": "#DCFCE7",
        "btn_hover": "#BBF7D0",
        "border": "#86EFAC",
        "fg": "#14532D",
        "muted_fg": "#15803D",
        "toolbar_bg": "#DCFCE7",
        "accent": "#16A34A",
        "placeholder": "#86EFAC"
    },
    "blue": {
        "name": "Sky Breeze",
        "bg": "#F0F9FF",
        "header_bg": "#E0F2FE",
        "btn_hover": "#BAE6FD",
        "border": "#7DD3FC",
        "fg": "#0C4A6E",
        "muted_fg": "#0369A1",
        "toolbar_bg": "#E0F2FE",
        "accent": "#0284C7",
        "placeholder": "#7DD3FC"
    },
    "pink": {
        "name": "Blush Rose",
        "bg": "#FDF2F8",
        "header_bg": "#FCE7F3",
        "btn_hover": "#FBCFE8",
        "border": "#F472B6",
        "fg": "#701A75",
        "muted_fg": "#9D174D",
        "toolbar_bg": "#FCE7F3",
        "accent": "#DB2777",
        "placeholder": "#F472B6"
    },
    "purple": {
        "name": "Soft Lavender",
        "bg": "#FAF5FF",
        "header_bg": "#F3E8FF",
        "btn_hover": "#E9D5FF",
        "border": "#D8B4FE",
        "fg": "#4C1D95",
        "muted_fg": "#6D28D9",
        "toolbar_bg": "#F3E8FF",
        "accent": "#9333EA",
        "placeholder": "#D8B4FE"
    },
    "orange": {
        "name": "Warm Peach",
        "bg": "#FFF7ED",
        "header_bg": "#FFEDD5",
        "btn_hover": "#FED7AA",
        "border": "#FDBA74",
        "fg": "#7C2D12",
        "muted_fg": "#C2410C",
        "toolbar_bg": "#FFEDD5",
        "accent": "#EA580C",
        "placeholder": "#FDBA74"
    },
    "dark": {
        "name": "Velvet Charcoal",
        "bg": "#18181B",
        "header_bg": "#27272A",
        "btn_hover": "#3F3F46",
        "border": "#52525B",
        "fg": "#FAFAFA",
        "muted_fg": "#A1A1AA",
        "toolbar_bg": "#27272A",
        "accent": "#60A5FA",
        "placeholder": "#71717A"
    }
}

FONT_FAMILY = "Segoe UI"
BASE_FONT_SIZE = 11

class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int)
    ]

def enable_high_dpi():
    """Enable Windows Per-Monitor High DPI awareness for ultra-crisp fonts."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def apply_drop_shadow(window):
    """Extend DWM frame to draw native modern drop shadows around frameless windows."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        margins = MARGINS(1, 1, 1, 1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    except Exception:
        pass

def make_taskbar_friendly(window, is_pinned=False):
    """Ensure frameless window has clean desktop window styles and taskbar representation."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass

def stick_window_to_desktop(window):
    """Enforce window staying at HWND_BOTTOM (desktop wallpaper level behind all other apps)."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        HWND_BOTTOM = 1
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        ctypes.windll.user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except Exception:
        pass

def set_window_z_order(window, is_pinned: bool):
    """Set window z-order: topmost if pinned, desktop wallpaper level if unpinned (sticks to screen)."""
    try:
        window.wm_attributes("-topmost", bool(is_pinned))
        if not is_pinned:
            stick_window_to_desktop(window)
    except Exception:
        pass

def force_foreground_window(hwnd: int):
    """Reliably activate and bring hwnd to foreground on Windows 10/11."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Restore if minimized
        user32.ShowWindow(hwnd, 9) # SW_RESTORE
        
        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
        cur_thread = kernel32.GetCurrentThreadId()
        
        if fore_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, fore_thread, True)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(cur_thread, fore_thread, False)
        else:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            
        HWND_TOPMOST = -1
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception:
        pass

