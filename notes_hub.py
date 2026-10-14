"""
Notes Hub / Manager Window.
Minimalist, clean, and modern central search and manager for all notes.
"""

import os
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Dict, Any, List
from styles import THEMES, FONT_FAMILY

class NotesHub:
    def __init__(
        self,
        master: tk.Tk,
        storage,
        on_open_note: Callable[[str], None],
        on_create_note: Callable[[], None],
        on_delete_permanently: Callable[[str], None]
    ):
        self.master = master
        self.storage = storage
        self.on_open_note = on_open_note
        self.on_create_note = on_create_note
        self.on_delete_permanently = on_delete_permanently

        self.win = tk.Toplevel(master)
        self.win.title("ScreenStick - Notes Hub")

        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.win.iconbitmap(ico_path)
            except Exception:
                pass

        self.win.geometry("420x500+250+180")
        self.win.minsize(360, 380)
        self.win.configure(bg="#F8FAFC")

        self.font_header = tkfont.Font(family=FONT_FAMILY, size=13, weight="bold")
        self.font_body = tkfont.Font(family=FONT_FAMILY, size=10)
        self.font_bold = tkfont.Font(family=FONT_FAMILY, size=10, weight="bold")
        self.font_small = tkfont.Font(family=FONT_FAMILY, size=8)

        self.current_filter = "active"

        self._build_ui()
        self.refresh_notes()

    def _build_ui(self):
        # 1. Top Header
        top_bar = tk.Frame(self.win, bg="#FFFFFF", padx=18, pady=14)
        top_bar.pack(fill="x", side="top")

        lbl_title = tk.Label(
            top_bar,
            text="ScreenStick Hub",
            font=self.font_header,
            bg="#FFFFFF",
            fg="#0F172A"
        )
        lbl_title.pack(side="left")

        btn_new = tk.Label(
            top_bar,
            text="＋ New Note",
            font=self.font_bold,
            bg="#0F172A",
            fg="#FFFFFF",
            padx=12,
            pady=5,
            cursor="hand2"
        )
        btn_new.pack(side="right")
        btn_new.bind("<Button-1>", lambda e: self._create_new())
        btn_new.bind("<Enter>", lambda e: btn_new.configure(bg="#334155"))
        btn_new.bind("<Leave>", lambda e: btn_new.configure(bg="#0F172A"))

        # Thin divider
        div = tk.Frame(self.win, bg="#E2E8F0", height=1)
        div.pack(fill="x")

        # 2. Search Box
        search_container = tk.Frame(self.win, bg="#F8FAFC", padx=16, pady=10)
        search_container.pack(fill="x")

        search_box = tk.Frame(search_container, bg="#FFFFFF", bd=1, relief="solid")
        search_box.pack(fill="x")

        lbl_icon = tk.Label(search_box, text="🔍", font=self.font_body, bg="#FFFFFF", fg="#94A3B8")
        lbl_icon.pack(side="left", padx=(10, 4), pady=6)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_notes())
        self.entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            font=self.font_body,
            bg="#FFFFFF",
            fg="#0F172A",
            bd=0,
            insertbackground="#0F172A"
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=6)

        # 3. Filter Pills
        filter_bar = tk.Frame(self.win, bg="#F8FAFC", padx=16, pady=2)
        filter_bar.pack(fill="x", pady=(0, 6))

        self.pill_active = self._create_filter_pill(filter_bar, "Active Notes", "active")
        self.pill_active.pack(side="left", padx=(0, 6))

        self.pill_all = self._create_filter_pill(filter_bar, "All Notes", "all")
        self.pill_all.pack(side="left")

        self._update_filter_pills()

        # 4. Scrollable Container
        scroll_container = tk.Frame(self.win, bg="#F8FAFC", padx=16)
        scroll_container.pack(fill="both", expand=True, pady=(0, 12))

        self.canvas = tk.Canvas(scroll_container, bg="#F8FAFC", bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=self.canvas.yview)
        self.card_list = tk.Frame(self.canvas, bg="#F8FAFC")

        self.card_list.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_win = self.canvas.create_window((0, 0), window=self.card_list, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_win, width=e.width)
        )
        self.canvas.bind_all("<MouseWheel>", self._on_scroll)

    def _create_filter_pill(self, parent, text, val):
        pill = tk.Label(
            parent,
            text=text,
            font=self.font_small,
            padx=10,
            pady=3,
            cursor="hand2"
        )
        pill.bind("<Button-1>", lambda e, v=val: self._set_filter(v))
        return pill

    def _set_filter(self, val):
        self.current_filter = val
        self._update_filter_pills()
        self.refresh_notes()

    def _update_filter_pills(self):
        for pill, val in [(self.pill_active, "active"), (self.pill_all, "all")]:
            if self.current_filter == val:
                pill.configure(bg="#0F172A", fg="#FFFFFF")
            else:
                pill.configure(bg="#E2E8F0", fg="#475569")

    def _on_scroll(self, event):
        if self.win.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_new(self):
        self.on_create_note()
        self.refresh_notes()

    def refresh_notes(self):
        for w in self.card_list.winfo_children():
            w.destroy()

        query = self.search_var.get().lower().strip()
        if self.current_filter == "active":
            notes = self.storage.get_active_notes()
        else:
            notes = self.storage.get_all_notes()

        notes = sorted(notes, key=lambda n: n.get("updated_at", ""), reverse=True)

        if query:
            notes = [n for n in notes if query in n.get("text", "").lower()]

        if not notes:
            empty = tk.Label(
                self.card_list,
                text="No notes found.\nClick '＋ New Note' to create one.",
                font=self.font_body,
                bg="#F8FAFC",
                fg="#94A3B8",
                pady=40
            )
            empty.pack(fill="x")
            return

        for note in notes:
            self._render_card(note)

    def _render_card(self, note: Dict[str, Any]):
        color_key = note.get("color", "yellow")
        theme = THEMES.get(color_key, THEMES["yellow"])
        raw = note.get("text", "").strip()

        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        title = lines[0][:32] if lines else "Empty Note"
        snippet = lines[1][:50] if len(lines) > 1 else ""

        is_deleted = note.get("is_deleted", False)

        card = tk.Frame(self.card_list, bg="#FFFFFF", bd=1, relief="solid")
        card.pack(fill="x", pady=4)

        # Color Accent Strip on top of card
        strip = tk.Frame(card, bg=theme["header_bg"], height=4)
        strip.pack(fill="x", side="top")

        body = tk.Frame(card, bg="#FFFFFF", padx=12, pady=8)
        body.pack(fill="both", expand=True)

        # Left Info
        left = tk.Frame(body, bg="#FFFFFF")
        left.pack(side="left", fill="both", expand=True)

        lbl_t = tk.Label(left, text=title, font=self.font_bold, bg="#FFFFFF", fg="#0F172A", anchor="w")
        lbl_t.pack(fill="x")

        if snippet:
            lbl_s = tk.Label(left, text=snippet, font=self.font_small, bg="#FFFFFF", fg="#64748B", anchor="w")
            lbl_s.pack(fill="x", pady=(1, 0))

        updated = note.get("updated_at", "")
        pin_badge = "📌 Pinned" if note.get("is_pinned") else "📍"
        meta_str = f"{updated} • {pin_badge}"
        if is_deleted:
            meta_str += " • Archived"

        lbl_m = tk.Label(left, text=meta_str, font=(FONT_FAMILY, 8), bg="#FFFFFF", fg="#94A3B8", anchor="w")
        lbl_m.pack(fill="x", pady=(3, 0))

        # Right Action buttons
        right = tk.Frame(body, bg="#FFFFFF")
        right.pack(side="right", padx=(8, 0))

        btn_open = tk.Label(
            right,
            text="Open" if not is_deleted else "Restore",
            font=self.font_small,
            bg=theme["header_bg"],
            fg=theme["fg"],
            padx=10,
            pady=4,
            cursor="hand2"
        )
        btn_open.pack(side="left", padx=2)
        btn_open.bind("<Button-1>", lambda e, nid=note["id"]: self._open(nid, is_deleted))

        btn_del = tk.Label(
            right,
            text="🗑",
            font=self.font_small,
            bg="#FFFFFF",
            fg="#94A3B8",
            padx=6,
            pady=4,
            cursor="hand2"
        )
        btn_del.pack(side="left", padx=2)
        btn_del.bind("<Button-1>", lambda e, nid=note["id"]: self._del(nid))
        btn_del.bind("<Enter>", lambda e, b=btn_del: b.configure(fg="#DC2626"))
        btn_del.bind("<Leave>", lambda e, b=btn_del: b.configure(fg="#94A3B8"))

    def _open(self, note_id: str, is_deleted: bool):
        if is_deleted:
            self.storage.restore_note(note_id)
        self.on_open_note(note_id)
        self.refresh_notes()

    def _del(self, note_id: str):
        self.on_delete_permanently(note_id)
        self.refresh_notes()

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.refresh_notes()
