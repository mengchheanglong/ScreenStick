"""
Sticky Note Window Implementation.
Header bar layout: + tools ... x
- '+' creates a new sticky note.
- 'tools' contains rich text formatting (B, I, U, S, •, ☑).
- '...' menu opens color palette (7 pastel themes), pin/desktop stick toggle, font size, and notes hub.
- 'x' deletes/closes the note.
- Bottom of the note has zero toolbar or wasted space.
- When unhovered, surrounding detail disappears and only note text exists.
- Sticking to desktop: default is unpinned (other apps naturally come on top).
"""

import sys
import os
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Callable, Dict, Any
from styles import THEMES, FONT_FAMILY, BASE_FONT_SIZE, apply_drop_shadow, make_taskbar_friendly, set_window_z_order, stick_window_to_desktop

class NoteWindow:
    def __init__(
        self,
        master: tk.Tk,
        note_data: Dict[str, Any],
        on_update: Callable[[str, Dict[str, Any]], None],
        on_delete: Callable[[str], None],
        on_new_note: Callable[[Optional[int], Optional[int]], None],
        on_open_hub: Callable[[], None],
        on_close_window: Optional[Callable[[str], None]] = None
    ):
        self.master = master
        self.data = note_data
        self.note_id = note_data["id"]
        self.on_update = on_update
        self.on_delete = on_delete
        self.on_new_note = on_new_note
        self.on_open_hub = on_open_hub
        self.on_close_window = on_close_window

        self.color_key = note_data.get("color", "yellow")
        if self.color_key not in THEMES:
            self.color_key = "yellow"
        self.theme = THEMES[self.color_key]

        # Pin is NOT default: unpinned by default (sticks to desktop, other apps come on top)
        self.is_pinned = note_data.get("is_pinned", False)
        self.is_collapsed = note_data.get("is_collapsed", False)
        self.current_font_size = BASE_FONT_SIZE
        self._is_placeholder_active = False
        self._is_hovered = False
        self._leave_timer = None
        self._tools_popup = None
        self._is_closing = False

        # Window creation
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.title("ScreenStick")

        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.win.iconbitmap(ico_path)
            except Exception:
                pass

        # Position and size
        self.w = note_data.get("width", 280)
        self.h = note_data.get("height", 240)
        self.x = note_data.get("x", 320)
        self.y = note_data.get("y", 160)
        self.prev_height = self.h

        # Minimum dimensions to comfortably fit "+ tools ... x"
        self.min_w = 210
        self.min_h = 100

        self.win.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")

        # Set desktop z-order (other applications come on top by default)
        self.set_pinned_state(self.is_pinned)

        # High DPI, drop shadow, and taskbar integration
        apply_drop_shadow(self.win)
        make_taskbar_friendly(self.win, is_pinned=self.is_pinned)

        # Drag tracking
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._orig_w = self.w
        self._orig_h = self.h
        self._save_timer = None

        # Build UI
        self._setup_fonts()
        self._build_ui()
        self._bind_events()
        self._load_content()

        # Bring note forward upon launch so user sees it right away
        self.focus()

        # Start with clean surface (header appears on hover)
        self._hide_hover_controls()

    def _setup_fonts(self):
        self.font_normal = tkfont.Font(family=FONT_FAMILY, size=self.current_font_size)
        self.font_bold = tkfont.Font(family=FONT_FAMILY, size=self.current_font_size, weight="bold")
        self.font_italic = tkfont.Font(family=FONT_FAMILY, size=self.current_font_size, slant="italic")
        self.font_action_btn = tkfont.Font(family=FONT_FAMILY, size=11, weight="bold")
        self.font_tool_bold = tkfont.Font(family=FONT_FAMILY, size=9, weight="bold")
        self.font_tool_italic = tkfont.Font(family=FONT_FAMILY, size=9, slant="italic")
        self.font_tool_underline = tkfont.Font(family=FONT_FAMILY, size=9, underline=True)
        self.font_tool_strike = tkfont.Font(family=FONT_FAMILY, size=9, overstrike=True)
        self.font_tool_symbol = tkfont.Font(family=FONT_FAMILY, size=10)

    def _build_ui(self):
        # 1px border container
        self.border_frame = tk.Frame(self.win, bg=self.theme["border"], padx=1, pady=1)
        self.border_frame.pack(fill="both", expand=True)

        # Main inner container
        self.main_container = tk.Frame(self.border_frame, bg=self.theme["bg"])
        self.main_container.pack(fill="both", expand=True)

        # --- Top Header: + tools ... x ---
        self.header_frame = tk.Frame(self.main_container, bg=self.theme["header_bg"], height=28)

        # 1. '+' Button (New note)
        self.btn_new = tk.Label(
            self.header_frame,
            text="＋",
            font=self.font_action_btn,
            bg=self.theme["header_bg"],
            fg=self.theme["fg"],
            padx=5,
            pady=0,
            cursor="hand2"
        )
        self.btn_new.pack(side="left", padx=(4, 2), pady=2)

        # Subtle divider
        self.sep_tools = tk.Frame(self.header_frame, bg=self.theme["border"], width=1, height=14)
        self.sep_tools.pack(side="left", padx=3, pady=7)

        # 2. 'tools' Container: B, I, U, S, •, ☑
        self.tools_frame = tk.Frame(self.header_frame, bg=self.theme["header_bg"])
        self.tools_frame.pack(side="left", padx=1)

        self.btn_bold = tk.Label(
            self.tools_frame, text="B", font=self.font_tool_bold,
            bg=self.theme["header_bg"], fg=self.theme["fg"], padx=4, pady=0, cursor="hand2"
        )
        self.btn_bold.pack(side="left", padx=1, pady=2)

        self.btn_italic = tk.Label(
            self.tools_frame, text="I", font=self.font_tool_italic,
            bg=self.theme["header_bg"], fg=self.theme["fg"], padx=4, pady=0, cursor="hand2"
        )
        self.btn_italic.pack(side="left", padx=1, pady=2)

        self.btn_underline = tk.Label(
            self.tools_frame, text="U", font=self.font_tool_underline,
            bg=self.theme["header_bg"], fg=self.theme["fg"], padx=4, pady=0, cursor="hand2"
        )
        self.btn_underline.pack(side="left", padx=1, pady=2)

        self.btn_strike = tk.Label(
            self.tools_frame, text="S", font=self.font_tool_strike,
            bg=self.theme["header_bg"], fg=self.theme["fg"], padx=4, pady=0, cursor="hand2"
        )
        self.btn_strike.pack(side="left", padx=1, pady=2)

        self.btn_bullet = tk.Label(
            self.tools_frame, text="•", font=self.font_tool_symbol,
            bg=self.theme["header_bg"], fg=self.theme["fg"], padx=3, pady=0, cursor="hand2"
        )
        self.btn_bullet.pack(side="left", padx=1, pady=2)

        self.btn_check = tk.Label(
            self.tools_frame, text="☑", font=self.font_tool_symbol,
            bg=self.theme["header_bg"], fg=self.theme["fg"], padx=3, pady=0, cursor="hand2"
        )
        self.btn_check.pack(side="left", padx=1, pady=2)

        # 3. Draggable middle spacer (click and drag to move note)
        self.drag_spacer = tk.Label(
            self.header_frame,
            bg=self.theme["header_bg"],
            cursor="fleur"
        )
        self.drag_spacer.pack(side="left", fill="both", expand=True)

        # 4. 'x' Button (Close / Delete note) - packed to far right
        self.btn_close = tk.Label(
            self.header_frame,
            text="✕",
            font=tkfont.Font(family=FONT_FAMILY, size=10, weight="bold"),
            bg=self.theme["header_bg"],
            fg=self.theme["muted_fg"],
            padx=5,
            pady=0,
            cursor="hand2"
        )
        self.btn_close.pack(side="right", padx=(2, 4), pady=2)

        # 5. '...' Button (Three dots menu) - packed right next to 'x'
        self.btn_menu = tk.Label(
            self.header_frame,
            text="⋯",
            font=self.font_action_btn,
            bg=self.theme["header_bg"],
            fg=self.theme["fg"],
            padx=5,
            pady=0,
            cursor="hand2"
        )
        self.btn_menu.pack(side="right", padx=(2, 2), pady=2)

        # --- Text Editor fills the note down to the bottom (no bottom bar!) ---
        self.text_widget = tk.Text(
            self.main_container,
            wrap="word",
            undo=True,
            font=self.font_normal,
            bg=self.theme["bg"],
            fg=self.theme["fg"],
            insertbackground=self.theme["fg"],
            selectbackground=self.theme["btn_hover"],
            selectforeground=self.theme["fg"],
            bd=0,
            padx=12,
            pady=6,
            spacing1=2,
            spacing3=2,
            highlightthickness=0
        )
        self.text_widget.pack(fill="both", expand=True, pady=(28, 0))

        self._configure_text_tags()

        # Corner resize grip (Only visible on hover in bottom-right corner)
        self.resize_grip = tk.Label(
            self.main_container,
            text="◢",
            font=(FONT_FAMILY, 8),
            bg=self.theme["bg"],
            fg=self.theme["muted_fg"],
            cursor="size_nw_se"
        )

    def _configure_text_tags(self):
        self.text_widget.tag_configure("bold", font=self.font_bold)
        self.text_widget.tag_configure("italic", font=self.font_italic)
        self.text_widget.tag_configure("underline", underline=True)
        self.text_widget.tag_configure("strike", overstrike=True)
        self.text_widget.tag_configure("checked", overstrike=True, foreground=self.theme["muted_fg"])
        self.text_widget.tag_configure("placeholder", foreground=self.theme["placeholder"])

    def _bind_events(self):
        # Action button bindings
        self.btn_new.bind("<Button-1>", lambda e: self._on_plus_clicked())
        self.btn_bold.bind("<Button-1>", lambda e: self._apply_tag("bold"))
        self.btn_italic.bind("<Button-1>", lambda e: self._apply_tag("italic"))
        self.btn_underline.bind("<Button-1>", lambda e: self._apply_tag("underline"))
        self.btn_strike.bind("<Button-1>", lambda e: self._apply_tag("strike"))
        self.btn_bullet.bind("<Button-1>", lambda e: self._insert_bullet())
        self.btn_check.bind("<Button-1>", lambda e: self._insert_checkbox())
        self.btn_menu.bind("<Button-1>", lambda e: self._toggle_menu_popup())
        self.btn_close.bind("<Button-1>", lambda e: self._on_close_clicked())

        # Handle closing from Taskbar (right-click -> close) or Alt+F4
        self.win.protocol("WM_DELETE_WINDOW", self._on_wm_delete)
        self.win.bind("<Destroy>", self._on_win_destroy, add="+")
        self.win.bind("<FocusOut>", self._on_focus_out, add="+")

        # Stick to Screen (stays on wallpaper behind other apps even when clicked or edited)
        def _enforce_stick_to_screen(e=None):
            if not self.is_pinned:
                stick_window_to_desktop(self.win)
                self.win.after_idle(lambda: not self.is_pinned and stick_window_to_desktop(self.win))

        for w in [self.win, self.main_container, self.text_widget, self.header_frame]:
            for ev in ["<Button-1>", "<ButtonRelease-1>", "<FocusIn>", "<KeyRelease>"]:
                w.bind(ev, _enforce_stick_to_screen, add="+")

        # Button hover highlights
        for btn in [self.btn_new, self.btn_bold, self.btn_italic, self.btn_underline,
                    self.btn_strike, self.btn_bullet, self.btn_check, self.btn_menu]:
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.theme["btn_hover"]))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=self.theme["header_bg"]))

        self.btn_close.bind("<Enter>", lambda e: self.btn_close.configure(bg="#FEE2E2", fg="#DC2626"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.configure(bg=self.theme["header_bg"], fg=self.theme["muted_fg"]))

        # Dragging on header frame & drag spacer
        for drag_target in [self.header_frame, self.drag_spacer]:
            drag_target.bind("<Button-1>", self._start_drag)
            drag_target.bind("<B1-Motion>", self._on_drag)
            drag_target.bind("<ButtonRelease-1>", self._stop_drag)

        # Resizing from bottom-right grip
        self.resize_grip.bind("<Button-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._on_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self._stop_resize)

        # Global hover detection across note
        hover_targets = [
            self.win, self.border_frame, self.main_container, self.text_widget,
            self.header_frame, self.tools_frame, self.drag_spacer, self.btn_new,
            self.btn_bold, self.btn_italic, self.btn_underline, self.btn_strike,
            self.btn_bullet, self.btn_check, self.btn_menu, self.btn_close, self.resize_grip
        ]
        for w in hover_targets:
            w.bind("<Enter>", self._on_mouse_enter, add="+")
            w.bind("<Leave>", self._on_mouse_leave, add="+")

        # Text Editor events
        self.text_widget.bind("<FocusIn>", self._on_focus_in)
        self.text_widget.bind("<FocusOut>", self._on_focus_out)
        self.text_widget.bind("<KeyRelease>", self._schedule_save)
        self.text_widget.bind("<ButtonRelease-1>", self._on_text_click)

        # Shortcuts
        self.win.bind("<Control-n>", lambda e: self._on_plus_clicked())
        self.win.bind("<Control-N>", lambda e: self._on_plus_clicked())
        self.win.bind("<Control-b>", lambda e: self._apply_tag("bold"))
        self.win.bind("<Control-B>", lambda e: self._apply_tag("bold"))
        self.win.bind("<Control-i>", lambda e: self._apply_tag("italic"))
        self.win.bind("<Control-I>", lambda e: self._apply_tag("italic"))
        self.win.bind("<Control-u>", lambda e: self._apply_tag("underline"))
        self.win.bind("<Control-U>", lambda e: self._apply_tag("underline"))
        self.win.bind("<Control-t>", lambda e: self._apply_tag("strike"))
        self.win.bind("<Control-T>", lambda e: self._apply_tag("strike"))

        self.text_widget.bind("<Button-3>", self._show_context_menu)

    # --- Dragging the Note Window ---
    def _start_drag(self, event):
        self._drag_start_x = event.x_root - self.win.winfo_x()
        self._drag_start_y = event.y_root - self.win.winfo_y()

    def _on_drag(self, event):
        new_x = event.x_root - self._drag_start_x
        new_y = event.y_root - self._drag_start_y
        self.win.geometry(f"+{new_x}+{new_y}")

    def _stop_drag(self, event):
        self.x = self.win.winfo_x()
        self.y = self.win.winfo_y()
        self.on_update(self.note_id, {"x": self.x, "y": self.y})
        if not self.is_pinned:
            stick_window_to_desktop(self.win)

    # --- Hover Management: Header appears on hover, disappears on leave ---
    def _on_mouse_enter(self, event=None):
        self._is_hovered = True
        self._show_hover_controls()

    def _on_mouse_leave(self, event=None):
        if self._leave_timer:
            self.win.after_cancel(self._leave_timer)
        self._leave_timer = self.win.after(90, self._check_if_really_left)

    def _check_if_really_left(self):
        # Keep header visible if the '...' popup menu is currently open
        if self._tools_popup and self._tools_popup.winfo_exists():
            return
        try:
            px = self.win.winfo_pointerx()
            py = self.win.winfo_pointery()
            wx = self.win.winfo_rootx()
            wy = self.win.winfo_rooty()
            ww = self.win.winfo_width()
            wh = self.win.winfo_height()

            if not (wx <= px <= wx + ww and wy <= py <= wy + wh):
                self._is_hovered = False
                self._hide_hover_controls()
        except Exception:
            pass

    def _show_hover_controls(self):
        """Show top header bar '+ tools ... x' and corner grip."""
        self.header_frame.place(x=0, y=0, relwidth=1.0, height=28)
        self.resize_grip.place(relx=1.0, rely=1.0, x=-2, y=-2, anchor="se")

    def _hide_hover_controls(self):
        """Hide header and grip completely; only note text remains."""
        self.header_frame.place_forget()
        self.resize_grip.place_forget()

    # --- '...' (Three Dots) Menu Popup ---
    def _toggle_menu_popup(self):
        if self._tools_popup and self._tools_popup.winfo_exists():
            self._tools_popup.destroy()
            self._tools_popup = None
            return

        popup = tk.Toplevel(self.win)
        self._tools_popup = popup
        popup.overrideredirect(True)
        popup.wm_attributes("-topmost", True)

        bx = self.btn_menu.winfo_rootx()
        by = self.btn_menu.winfo_rooty() + self.btn_menu.winfo_height() + 4
        popup.geometry(f"245x198+{bx - 185}+{by}")

        card = tk.Frame(popup, bg="#FFFFFF", bd=1, relief="solid")
        card.pack(fill="both", expand=True)

        # 1. Pastel Color Palette Swatches (7 colors)
        color_row = tk.Frame(card, bg="#FFFFFF", padx=8, pady=6)
        color_row.pack(fill="x")

        tk.Label(color_row, text="Color:", font=(FONT_FAMILY, 8, "bold"), bg="#FFFFFF", fg="#6B7280").pack(side="left", padx=(0, 4))
        for key, theme in THEMES.items():
            is_active = (key == self.color_key)
            swatch = tk.Label(
                color_row,
                bg=theme["header_bg"],
                width=2,
                height=1,
                cursor="hand2",
                relief="solid",
                bd=2 if is_active else 1
            )
            swatch.pack(side="left", padx=2)
            swatch.bind("<Button-1>", lambda e, k=key: self._select_color(k, popup))

        # Divider
        tk.Frame(card, bg="#E5E7EB", height=1).pack(fill="x", padx=6, pady=2)

        # 2. Stick to Screen / Always on Top Toggle
        pin_row = tk.Frame(card, bg="#FFFFFF", padx=8, pady=4)
        pin_row.pack(fill="x")
        if self.is_pinned:
            pin_txt = "📌  Always on Top: ON"
            pin_bg = "#EFF6FF"
            pin_fg = "#2563EB"
            hover_bg = "#DBEAFE"
        else:
            pin_txt = "🖥️  Stick to Screen (Wallpaper: ON)"
            pin_bg = "#ECFDF5"
            pin_fg = "#059669"
            hover_bg = "#D1FAE5"

        lbl_pin = tk.Label(
            pin_row,
            text=pin_txt,
            font=(FONT_FAMILY, 9),
            bg=pin_bg,
            fg=pin_fg,
            anchor="w",
            padx=6,
            pady=3,
            cursor="hand2"
        )
        lbl_pin.pack(fill="x")
        lbl_pin.bind("<Button-1>", lambda e: (popup.destroy(), self.toggle_pin()))
        lbl_pin.bind("<Enter>", lambda e: lbl_pin.configure(bg=hover_bg))
        lbl_pin.bind("<Leave>", lambda e: lbl_pin.configure(bg=pin_bg))

        # Divider
        tk.Frame(card, bg="#E5E7EB", height=1).pack(fill="x", padx=6, pady=2)

        # 3. Font Size Controls (A- / A+)
        font_row = tk.Frame(card, bg="#FFFFFF", padx=8, pady=4)
        font_row.pack(fill="x")
        tk.Label(font_row, text="Font Size:", font=(FONT_FAMILY, 8, "bold"), bg="#FFFFFF", fg="#6B7280").pack(side="left")

        btn_a_minus = tk.Label(font_row, text="A-", font=(FONT_FAMILY, 8, "bold"), bg="#F3F4F6", fg="#1F2937", padx=6, pady=1, cursor="hand2", bd=1, relief="solid")
        btn_a_minus.pack(side="left", padx=4)
        btn_a_minus.bind("<Button-1>", lambda e: self._decrease_font_size())

        btn_a_plus = tk.Label(font_row, text="A+", font=(FONT_FAMILY, 8, "bold"), bg="#F3F4F6", fg="#1F2937", padx=6, pady=1, cursor="hand2", bd=1, relief="solid")
        btn_a_plus.pack(side="left", padx=2)
        btn_a_plus.bind("<Button-1>", lambda e: self._increase_font_size())

        # Divider
        tk.Frame(card, bg="#E5E7EB", height=1).pack(fill="x", padx=6, pady=2)

        # 4. Notes Hub & Search link
        lbl_hub = tk.Label(
            card,
            text="📋  Notes Hub & Search",
            font=(FONT_FAMILY, 9),
            bg="#FFFFFF",
            fg="#374151",
            anchor="w",
            padx=10,
            pady=3,
            cursor="hand2"
        )
        lbl_hub.pack(fill="x")
        lbl_hub.bind("<Button-1>", lambda e: (popup.destroy(), self.on_open_hub()))
        lbl_hub.bind("<Enter>", lambda e: lbl_hub.configure(bg="#F3F4F6"))
        lbl_hub.bind("<Leave>", lambda e: lbl_hub.configure(bg="#FFFFFF"))

        # Divider
        tk.Frame(card, bg="#E5E7EB", height=1).pack(fill="x", padx=6, pady=2)

        # 5. Delete note option
        lbl_del = tk.Label(
            card,
            text="🗑️  Delete Note",
            font=(FONT_FAMILY, 9),
            bg="#FFFFFF",
            fg="#DC2626",
            anchor="w",
            padx=10,
            pady=3,
            cursor="hand2"
        )
        lbl_del.pack(fill="x")
        lbl_del.bind("<Button-1>", lambda e: (popup.destroy(), self._on_delete_clicked()))
        lbl_del.bind("<Enter>", lambda e: lbl_del.configure(bg="#FEE2E2"))
        lbl_del.bind("<Leave>", lambda e: lbl_del.configure(bg="#FFFFFF"))

        popup.bind("<FocusOut>", lambda e: (popup.destroy(), self._schedule_leave_check_direct()))
        popup.focus_set()

    def _schedule_leave_check_direct(self):
        self._tools_popup = None
        self._on_mouse_leave()

    def _select_color(self, color_key: str, popup: tk.Toplevel):
        try:
            popup.destroy()
        except Exception:
            pass
        self._tools_popup = None
        if color_key in THEMES:
            self.color_key = color_key
            self.theme = THEMES[color_key]
            self._apply_theme()
            self.on_update(self.note_id, {"color": self.color_key})

    def _apply_theme(self):
        """Update colors seamlessly across note and header elements."""
        self.border_frame.configure(bg=self.theme["border"])
        self.main_container.configure(bg=self.theme["bg"])
        self.header_frame.configure(bg=self.theme["header_bg"])
        self.sep_tools.configure(bg=self.theme["border"])
        self.tools_frame.configure(bg=self.theme["header_bg"])
        self.drag_spacer.configure(bg=self.theme["header_bg"])

        # Update action buttons
        self.btn_new.configure(bg=self.theme["header_bg"], fg=self.theme["fg"])
        self.btn_menu.configure(bg=self.theme["header_bg"], fg=self.theme["fg"])
        self.btn_close.configure(bg=self.theme["header_bg"], fg=self.theme["muted_fg"])

        # Update formatting buttons
        for btn in [self.btn_bold, self.btn_italic, self.btn_underline,
                    self.btn_strike, self.btn_bullet, self.btn_check]:
            btn.configure(bg=self.theme["header_bg"], fg=self.theme["fg"])

        self.text_widget.configure(
            bg=self.theme["bg"],
            fg=self.theme["fg"] if not self._is_placeholder_active else self.theme["placeholder"],
            insertbackground=self.theme["fg"],
            selectbackground=self.theme["btn_hover"],
            selectforeground=self.theme["fg"]
        )
        self.resize_grip.configure(bg=self.theme["bg"], fg=self.theme["muted_fg"])
        self._configure_text_tags()

    # --- Resizing Window ---
    def _start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._orig_w = self.win.winfo_width()
        self._orig_h = self.win.winfo_height()

    def _on_resize(self, event):
        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y
        new_w = max(self.min_w, self._orig_w + delta_x)
        new_h = max(self.min_h, self._orig_h + delta_y)
        self.win.geometry(f"{new_w}x{new_h}")

    def _stop_resize(self, event):
        self.w = self.win.winfo_width()
        self.h = self.win.winfo_height()
        self.prev_height = self.h
        self.on_update(self.note_id, {"width": self.w, "height": self.h})
        if not self.is_pinned:
            stick_window_to_desktop(self.win)

    # --- Pin & Desktop Sticking State ---
    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.prev_height = max(self.win.winfo_height(), self.min_h)
            self.win.geometry(f"{self.win.winfo_width()}x32")
        else:
            self.win.geometry(f"{self.win.winfo_width()}x{self.prev_height}")
        self.on_update(self.note_id, {"is_collapsed": self.is_collapsed})

    def toggle_pin(self):
        """Toggle between sticking to desktop (default) and floating on top."""
        self.is_pinned = not self.is_pinned
        self.set_pinned_state(self.is_pinned)
        self.on_update(self.note_id, {"is_pinned": self.is_pinned})

    def set_pinned_state(self, pinned: bool):
        self.win.wm_attributes("-topmost", pinned)
        set_window_z_order(self.win, pinned)

    # --- Text Editing & Formatting Tools ---
    def _apply_tag(self, tag_name: str):
        if self._is_placeholder_active:
            return
        try:
            sel_first = self.text_widget.index("sel.first")
            sel_last = self.text_widget.index("sel.last")
        except tk.TclError:
            return

        current_tags = self.text_widget.tag_names(sel_first)
        if tag_name in current_tags:
            self.text_widget.tag_remove(tag_name, sel_first, sel_last)
        else:
            self.text_widget.tag_add(tag_name, sel_first, sel_last)
        self._schedule_save()

    def _insert_bullet(self):
        if self._is_placeholder_active:
            self._clear_placeholder()
        pos = self.text_widget.index("insert")
        line_num = pos.split(".")[0]
        start = f"{line_num}.0"
        txt = self.text_widget.get(start, f"{line_num}.end")
        if txt.startswith("• "):
            self.text_widget.delete(start, f"{line_num}.2")
        else:
            self.text_widget.insert(start, "• ")
        self._schedule_save()

    def _insert_checkbox(self):
        if self._is_placeholder_active:
            self._clear_placeholder()
        pos = self.text_widget.index("insert")
        line_num = pos.split(".")[0]
        start = f"{line_num}.0"
        txt = self.text_widget.get(start, f"{line_num}.end")
        if txt.startswith("[ ] "):
            self.text_widget.delete(start, f"{line_num}.4")
        elif txt.startswith("[✓] "):
            self.text_widget.delete(start, f"{line_num}.4")
            self.text_widget.tag_remove("checked", start, f"{line_num}.end")
        else:
            self.text_widget.insert(start, "[ ] ")
        self._schedule_save()

    def _on_text_click(self, event):
        if self._is_placeholder_active:
            self._clear_placeholder()
            return
        try:
            idx = self.text_widget.index(f"@{event.x},{event.y}")
            line_num, col = idx.split(".")
            start = f"{line_num}.0"
            end = f"{line_num}.end"
            txt = self.text_widget.get(start, end)
            if int(col) <= 4:
                if txt.startswith("[ ] "):
                    self.text_widget.delete(start, f"{line_num}.4")
                    self.text_widget.insert(start, "[✓] ")
                    self.text_widget.tag_add("checked", start, end)
                    self._schedule_save()
                elif txt.startswith("[✓] "):
                    self.text_widget.delete(start, f"{line_num}.4")
                    self.text_widget.insert(start, "[ ] ")
                    self.text_widget.tag_remove("checked", start, end)
                    self._schedule_save()
        except Exception:
            pass

    def _increase_font_size(self):
        self.current_font_size = min(22, self.current_font_size + 1)
        self._update_fonts()

    def _decrease_font_size(self):
        self.current_font_size = max(9, self.current_font_size - 1)
        self._update_fonts()

    def _update_fonts(self):
        self.font_normal.configure(size=self.current_font_size)
        self.font_bold.configure(size=self.current_font_size)
        self.font_italic.configure(size=self.current_font_size)
        self.text_widget.configure(font=self.font_normal)

    def _on_focus_in(self, event):
        if self._is_placeholder_active:
            self._clear_placeholder()

    def _on_focus_out(self, event):
        content = self.text_widget.get("1.0", "end-1c").strip()
        if not content:
            self._show_placeholder()

    def _show_placeholder(self):
        self._is_placeholder_active = True
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", "Take a note...")
        self.text_widget.tag_add("placeholder", "1.0", "end")
        self.text_widget.configure(fg=self.theme["placeholder"])

    def _clear_placeholder(self):
        if self._is_placeholder_active:
            self._is_placeholder_active = False
            self.text_widget.delete("1.0", "end")
            self.text_widget.tag_remove("placeholder", "1.0", "end")
            self.text_widget.configure(fg=self.theme["fg"])

    def _on_plus_clicked(self):
        nx = self.win.winfo_x() + 30
        ny = self.win.winfo_y() + 30
        self.on_new_note(nx, ny)

    def _on_close_clicked(self):
        """Called when user clicks ✕ to close the window (saves note, keeps in DB)."""
        if self._is_closing:
            return
        self._is_closing = True
        self._do_save()
        if self.on_close_window:
            self.on_close_window(self.note_id)
        self.destroy()

    def _on_delete_clicked(self):
        """Called when user selects Delete Note from menu (removes note from DB)."""
        if self._is_closing:
            return
        self._is_closing = True
        self.on_delete(self.note_id)
        self.destroy()

    def _schedule_save(self, event=None):
        if self._save_timer:
            self.win.after_cancel(self._save_timer)
        self._save_timer = self.win.after(400, self._do_save)

    def _do_save(self):
        if self._is_placeholder_active:
            return
        raw = self.text_widget.get("1.0", "end-1c")
        formatting = []
        for tag in ["bold", "italic", "underline", "strike", "checked"]:
            ranges = self.text_widget.tag_ranges(tag)
            for i in range(0, len(ranges), 2):
                formatting.append({
                    "tag": tag,
                    "start": str(ranges[i]),
                    "end": str(ranges[i+1])
                })

        self.on_update(self.note_id, {
            "text": raw,
            "formatting": formatting,
            "width": self.win.winfo_width(),
            "height": self.win.winfo_height(),
            "x": self.win.winfo_x(),
            "y": self.win.winfo_y(),
            "color": self.color_key,
            "is_pinned": self.is_pinned
        })

    def _load_content(self):
        raw = self.data.get("text", "")
        if raw.strip():
            self._is_placeholder_active = False
            self.text_widget.delete("1.0", "end")
            self.text_widget.insert("1.0", raw)
            formatting = self.data.get("formatting", [])
            for item in formatting:
                t = item.get("tag")
                s = item.get("start")
                e = item.get("end")
                if t and s and e:
                    try:
                        self.text_widget.tag_add(t, s, e)
                    except Exception:
                        pass
        else:
            self._show_placeholder()

    def _show_context_menu(self, event):
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: self.text_widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: self.text_widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: self.text_widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Bold", accelerator="Ctrl+B", command=lambda: self._apply_tag("bold"))
        menu.add_command(label="Italic", accelerator="Ctrl+I", command=lambda: self._apply_tag("italic"))
        menu.add_command(label="Underline", accelerator="Ctrl+U", command=lambda: self._apply_tag("underline"))
        menu.add_command(label="Strikethrough", accelerator="Ctrl+T", command=lambda: self._apply_tag("strike"))
        menu.add_separator()
        menu.add_command(label="Checklist Item ([ ])", command=self._insert_checkbox)
        menu.add_command(label="Bullet List (•)", command=self._insert_bullet)
        menu.tk_popup(event.x_root, event.y_root)

    def lift_to_front(self):
        """Actively bring note window to front of all applications on screen."""
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.attributes("-topmost", True)
            self.win.focus_force()
            self.text_widget.focus_set()
            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
                    from styles import force_foreground_window
                    force_foreground_window(hwnd)
                except Exception:
                    pass
            # If in Stick to Screen mode (unpinned), release topmost after brief delay
            # so other applications naturally come on top when user works in them
            if not self.is_pinned:
                def _settle_to_desktop():
                    try:
                        if self.win.winfo_exists() and not self.is_pinned:
                            self.win.attributes("-topmost", False)
                            stick_window_to_desktop(self.win)
                    except Exception:
                        pass
                self.win.after(800, _settle_to_desktop)
        except Exception:
            pass

    def focus(self):
        """Focus text widget while respecting stick to screen / pinned state."""
        try:
            self.win.deiconify()
            if self.is_pinned:
                self.win.lift()
                self.win.attributes("-topmost", True)
                self.win.focus_force()
                self.text_widget.focus_set()
                if sys.platform == "win32":
                    try:
                        import ctypes
                        hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
                        from styles import force_foreground_window
                        force_foreground_window(hwnd)
                    except Exception:
                        pass
            else:
                stick_window_to_desktop(self.win)
                self.text_widget.focus_set()
        except Exception:
            pass

    def _on_focus_out(self, event):
        """When note loses focus to another application, stick to desktop if unpinned."""
        if self.is_pinned:
            return
        def check_focus():
            try:
                if not self.win.winfo_exists():
                    return
                focused = self.win.focus_get()
                if focused is None and not self.is_pinned:
                    self.win.attributes("-topmost", False)
                    stick_window_to_desktop(self.win)
            except Exception:
                pass
        self.win.after(150, check_focus)

    def _on_wm_delete(self):
        """Called when user closes from Taskbar (right-click -> close) or Alt+F4."""
        if self._is_closing:
            return
        self._is_closing = True
        self._do_save()
        if self.on_close_window:
            self.on_close_window(self.note_id)
        self.destroy()

    def _on_win_destroy(self, event):
        """Called when the Tk window is destroyed."""
        if event.widget == self.win and not self._is_closing:
            self._is_closing = True
            if self.on_close_window:
                self.on_close_window(self.note_id)

    def destroy(self):
        self._is_closing = True
        try:
            self.win.destroy()
        except Exception:
            pass
