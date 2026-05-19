"""
Professional Overtime Calculator
Payroll period: 19th of month to 18th of next month
Auto-saves to SQLite database
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import sqlite3
import os
import datetime
from typing import Optional


# ─── Constants ────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overtime_data.db")

COLORS = {
    "bg":          "#1E2A3A",
    "sidebar":     "#16202E",
    "card":        "#263348",
    "accent":      "#3B82F6",
    "accent_dark": "#2563EB",
    "success":     "#10B981",
    "warning":     "#F59E0B",
    "danger":      "#EF4444",
    "text":        "#F1F5F9",
    "text_muted":  "#94A3B8",
    "border":      "#334155",
    "input_bg":    "#1E2A3A",
    "header":      "#0F172A",
    "row_even":    "#1E2A3A",
    "row_odd":     "#263348",
    "row_sel":     "#3B82F6",
}

FONTS = {
    "title":   ("Segoe UI", 20, "bold"),
    "heading": ("Segoe UI", 13, "bold"),
    "body":    ("Segoe UI", 11),
    "small":   ("Segoe UI", 9),
    "mono":    ("Consolas", 11),
}


# ─── Database Layer ───────────────────────────────────────────────────────────
class Database:
    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS work_entries (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_date    TEXT    NOT NULL UNIQUE,
                    start_time    TEXT    NOT NULL,
                    end_time      TEXT    NOT NULL,
                    break_minutes INTEGER NOT NULL DEFAULT 0,
                    notes         TEXT    DEFAULT ''
                );

                INSERT OR IGNORE INTO settings VALUES ('hourly_rate',      '15.00');
                INSERT OR IGNORE INTO settings VALUES ('regular_hours',    '8.0');
                INSERT OR IGNORE INTO settings VALUES ('ot_multiplier',    '1.5');
                INSERT OR IGNORE INTO settings VALUES ('currency_symbol',  '$');
                INSERT OR IGNORE INTO settings VALUES ('employee_name',    'Employee');
            """)

    # Settings
    def get_setting(self, key: str) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else ""

    def set_setting(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))

    # Entries
    def upsert_entry(self, entry_date: str, start_time: str, end_time: str,
                     break_minutes: int, notes: str):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO work_entries (entry_date, start_time, end_time, break_minutes, notes)
                VALUES (?,?,?,?,?)
                ON CONFLICT(entry_date) DO UPDATE SET
                    start_time    = excluded.start_time,
                    end_time      = excluded.end_time,
                    break_minutes = excluded.break_minutes,
                    notes         = excluded.notes
            """, (entry_date, start_time, end_time, break_minutes, notes))

    def get_entry(self, entry_date: str) -> Optional[tuple]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT entry_date,start_time,end_time,break_minutes,notes FROM work_entries WHERE entry_date=?",
                (entry_date,)
            ).fetchone()

    def get_entries_for_period(self, start_date: str, end_date: str) -> list:
        with self._conn() as conn:
            return conn.execute("""
                SELECT entry_date,start_time,end_time,break_minutes,notes
                FROM work_entries
                WHERE entry_date >= ? AND entry_date <= ?
                ORDER BY entry_date
            """, (start_date, end_date)).fetchall()

    def delete_entry(self, entry_date: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM work_entries WHERE entry_date=?", (entry_date,))


# ─── Helpers ──────────────────────────────────────────────────────────────────
def payroll_period(reference: datetime.date) -> tuple[datetime.date, datetime.date]:
    """Return (period_start, period_end) for the payroll period containing `reference`."""
    if reference.day >= 19:
        start = reference.replace(day=19)
        # end is the 18th of the next month
        if reference.month == 12:
            end = reference.replace(year=reference.year + 1, month=1, day=18)
        else:
            end = reference.replace(month=reference.month + 1, day=18)
    else:
        # start is the 19th of the previous month
        if reference.month == 1:
            start = reference.replace(year=reference.year - 1, month=12, day=19)
        else:
            start = reference.replace(month=reference.month - 1, day=19)
        end = reference.replace(day=18)
    return start, end


def calc_overtime(start_str: str, end_str: str, break_min: int,
                  regular_hours: float, hourly_rate: float,
                  ot_multiplier: float) -> dict:
    """Return overtime calculation details."""
    fmt = "%H:%M"
    start = datetime.datetime.strptime(start_str, fmt)
    end   = datetime.datetime.strptime(end_str,   fmt)
    if end <= start:
        end += datetime.timedelta(days=1)          # crosses midnight
    total_minutes = (end - start).seconds // 60 - break_min
    total_minutes = max(total_minutes, 0)
    total_hours   = total_minutes / 60.0
    regular_min   = min(total_minutes, int(regular_hours * 60))
    ot_minutes    = max(total_minutes - int(regular_hours * 60), 0)
    ot_hours      = ot_minutes / 60.0
    regular_pay   = (regular_min / 60.0) * hourly_rate
    ot_pay        = ot_hours * hourly_rate * ot_multiplier
    total_pay     = regular_pay + ot_pay
    return {
        "total_minutes": total_minutes,
        "total_hours":   total_hours,
        "regular_min":   regular_min,
        "ot_minutes":    ot_minutes,
        "ot_hours":      ot_hours,
        "regular_pay":   regular_pay,
        "ot_pay":        ot_pay,
        "total_pay":     total_pay,
    }


def fmt_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m"


# ─── Styled Widgets ───────────────────────────────────────────────────────────
class StyledFrame(tk.Frame):
    def __init__(self, master, bg=None, **kw):
        super().__init__(master, bg=bg or COLORS["card"], **kw)


class StyledLabel(tk.Label):
    def __init__(self, master, text="", style="body", fg=None, **kw):
        f = FONTS.get(style, FONTS["body"])
        super().__init__(master,
                         text=text,
                         font=f,
                         fg=fg or COLORS["text"],
                         bg=kw.pop("bg", master.cget("bg")),
                         **kw)


class StyledEntry(tk.Entry):
    def __init__(self, master, width=14, **kw):
        super().__init__(master,
                         font=FONTS["mono"],
                         fg=COLORS["text"],
                         bg=COLORS["input_bg"],
                         insertbackground=COLORS["text"],
                         relief="flat",
                         highlightthickness=1,
                         highlightbackground=COLORS["border"],
                         highlightcolor=COLORS["accent"],
                         width=width,
                         **kw)


class StyledButton(tk.Button):
    def __init__(self, master, text="", command=None, style="primary", **kw):
        colors = {
            "primary": (COLORS["accent"],      COLORS["accent_dark"], COLORS["text"]),
            "success": (COLORS["success"],      "#059669",             COLORS["text"]),
            "danger":  (COLORS["danger"],       "#DC2626",             COLORS["text"]),
            "neutral": (COLORS["border"],       "#475569",             COLORS["text"]),
        }
        bg, abg, fg = colors.get(style, colors["primary"])
        super().__init__(master,
                         text=text,
                         command=command,
                         font=FONTS["body"],
                         fg=fg,
                         bg=bg,
                         activebackground=abg,
                         activeforeground=fg,
                         relief="flat",
                         cursor="hand2",
                         padx=14,
                         pady=6,
                         **kw)


# ─── Main Application ─────────────────────────────────────────────────────────
class OvertimeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database(DB_PATH)
        self.title("Overtime Calculator")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=COLORS["bg"])
        self._configure_styles()
        self._build_ui()
        self._load_settings()
        self._refresh_period()
        self._load_today()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                         background=COLORS["card"],
                         foreground=COLORS["text"],
                         fieldbackground=COLORS["card"],
                         rowheight=28,
                         font=FONTS["body"])
        style.configure("Treeview.Heading",
                         background=COLORS["header"],
                         foreground=COLORS["text"],
                         font=FONTS["heading"],
                         relief="flat")
        style.map("Treeview",
                  background=[("selected", COLORS["row_sel"])],
                  foreground=[("selected", COLORS["text"])])
        style.configure("TScrollbar",
                         background=COLORS["border"],
                         troughcolor=COLORS["sidebar"],
                         arrowcolor=COLORS["text"])

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header bar
        header = tk.Frame(self, bg=COLORS["header"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="⏱  Overtime Calculator",
                 font=FONTS["title"], fg=COLORS["accent"],
                 bg=COLORS["header"]).pack(side="left", padx=20, pady=10)

        self._lbl_period = tk.Label(header, text="",
                                    font=FONTS["body"], fg=COLORS["text_muted"],
                                    bg=COLORS["header"])
        self._lbl_period.pack(side="left", padx=10)

        self._lbl_employee = tk.Label(header, text="",
                                      font=FONTS["body"], fg=COLORS["text"],
                                      bg=COLORS["header"])
        self._lbl_employee.pack(side="right", padx=20)

        # ── Main area: sidebar + content
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)

        sidebar = tk.Frame(main, bg=COLORS["sidebar"], width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        content = tk.Frame(main, bg=COLORS["bg"])
        content.pack(side="left", fill="both", expand=True, padx=16, pady=16)
        self._build_content(content)

    def _build_sidebar(self, parent):
        StyledLabel(parent, "Navigation", style="heading",
                    bg=COLORS["sidebar"], fg=COLORS["text_muted"]).pack(pady=(20, 8), padx=16, anchor="w")

        nav_items = [
            ("📅  Enter Times",  self._show_entry_tab),
            ("📊  Payroll Period", self._show_period_tab),
            ("⚙️  Settings",     self._show_settings_tab),
        ]
        self._nav_buttons = []
        for label, cmd in nav_items:
            btn = tk.Button(parent, text=label, command=cmd,
                            font=FONTS["body"], fg=COLORS["text"],
                            bg=COLORS["sidebar"],
                            activebackground=COLORS["accent"],
                            activeforeground=COLORS["text"],
                            relief="flat", anchor="w", padx=20, pady=10,
                            cursor="hand2")
            btn.pack(fill="x", pady=1)
            self._nav_buttons.append(btn)

        # Separator
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", padx=12, pady=16)

        # Quick stats in sidebar
        StyledLabel(parent, "This Period", style="heading",
                    bg=COLORS["sidebar"], fg=COLORS["text_muted"]).pack(padx=16, anchor="w")
        self._sb_days   = self._sidebar_stat(parent, "Days worked", "0")
        self._sb_ot_h   = self._sidebar_stat(parent, "Total OT",    "0h 00m")
        self._sb_ot_pay = self._sidebar_stat(parent, "OT Earnings", "$0.00")

    def _sidebar_stat(self, parent, label, value):
        frame = tk.Frame(parent, bg=COLORS["sidebar"])
        frame.pack(fill="x", padx=16, pady=4)
        tk.Label(frame, text=label, font=FONTS["small"],
                 fg=COLORS["text_muted"], bg=COLORS["sidebar"]).pack(anchor="w")
        lbl = tk.Label(frame, text=value, font=FONTS["heading"],
                       fg=COLORS["success"], bg=COLORS["sidebar"])
        lbl.pack(anchor="w")
        return lbl

    def _build_content(self, parent):
        self._notebook_frame = tk.Frame(parent, bg=COLORS["bg"])
        self._notebook_frame.pack(fill="both", expand=True)

        self._tab_entry    = tk.Frame(self._notebook_frame, bg=COLORS["bg"])
        self._tab_period   = tk.Frame(self._notebook_frame, bg=COLORS["bg"])
        self._tab_settings = tk.Frame(self._notebook_frame, bg=COLORS["bg"])

        self._build_entry_tab(self._tab_entry)
        self._build_period_tab(self._tab_period)
        self._build_settings_tab(self._tab_settings)

        self._active_tab = None
        self._show_entry_tab()

    # ── Entry tab ─────────────────────────────────────────────────────────────
    def _build_entry_tab(self, parent):
        top = tk.Frame(parent, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 12))

        StyledLabel(top, "Daily Time Entry", style="title",
                    bg=COLORS["bg"]).pack(side="left")

        # ── Input card
        card = StyledFrame(parent)
        card.pack(fill="x", pady=(0, 12))

        # Row 1: date
        r1 = tk.Frame(card, bg=COLORS["card"])
        r1.pack(fill="x", padx=20, pady=(16, 8))
        StyledLabel(r1, "Date (YYYY-MM-DD)", style="body",
                    bg=COLORS["card"]).grid(row=0, column=0, sticky="w", padx=(0, 12))
        self._ent_date = StyledEntry(r1, width=16)
        self._ent_date.grid(row=0, column=1, sticky="w")
        self._ent_date.insert(0, datetime.date.today().isoformat())

        btn_today = StyledButton(r1, "Today", command=self._set_today)
        btn_today.grid(row=0, column=2, padx=(8, 0))

        # Row 2: start / end / break
        r2 = tk.Frame(card, bg=COLORS["card"])
        r2.pack(fill="x", padx=20, pady=8)

        fields = [
            ("Start Time (HH:MM)", "_ent_start", "08:00"),
            ("End Time   (HH:MM)", "_ent_end",   "17:00"),
            ("Break (minutes)",    "_ent_break", "60"),
        ]
        for i, (lbl, attr, default) in enumerate(fields):
            StyledLabel(r2, lbl, style="body", bg=COLORS["card"]).grid(
                row=0, column=i*2, sticky="w", padx=(0 if i == 0 else 20, 8))
            ent = StyledEntry(r2, width=10)
            ent.grid(row=0, column=i*2+1, sticky="w")
            ent.insert(0, default)
            setattr(self, attr, ent)

        # Row 3: notes
        r3 = tk.Frame(card, bg=COLORS["card"])
        r3.pack(fill="x", padx=20, pady=8)
        StyledLabel(r3, "Notes", style="body", bg=COLORS["card"]).grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        self._ent_notes = StyledEntry(r3, width=60)
        self._ent_notes.grid(row=0, column=1, sticky="w")

        # Buttons row
        btn_row = tk.Frame(card, bg=COLORS["card"])
        btn_row.pack(fill="x", padx=20, pady=(8, 16))
        StyledButton(btn_row, "💾  Save Entry",    command=self._save_entry, style="primary").pack(side="left", padx=(0, 8))
        StyledButton(btn_row, "🔄  Calculate",     command=self._calculate_preview, style="success").pack(side="left", padx=(0, 8))
        StyledButton(btn_row, "🗑  Delete Entry",  command=self._delete_entry, style="danger").pack(side="left")

        # ── Live result card
        res_card = StyledFrame(parent)
        res_card.pack(fill="x", pady=(0, 12))
        StyledLabel(res_card, "Day Breakdown", style="heading",
                    bg=COLORS["card"]).pack(anchor="w", padx=20, pady=(12, 8))
        self._result_frame = tk.Frame(res_card, bg=COLORS["card"])
        self._result_frame.pack(fill="x", padx=20, pady=(0, 16))
        self._build_result_labels()

        # ── Period table
        tbl_card = StyledFrame(parent)
        tbl_card.pack(fill="both", expand=True)
        hdr = tk.Frame(tbl_card, bg=COLORS["card"])
        hdr.pack(fill="x", padx=20, pady=(12, 6))
        StyledLabel(hdr, "Payroll Period Entries", style="heading",
                    bg=COLORS["card"]).pack(side="left")
        StyledButton(hdr, "↻ Refresh", command=self._refresh_period, style="neutral").pack(side="right")

        cols = ("Date", "Start", "End", "Break", "Total Hrs", "OT Min", "OT Hrs", "OT Pay", "Notes")
        self._tree = ttk.Treeview(tbl_card, columns=cols, show="headings", height=10)
        widths = (110, 70, 70, 60, 90, 75, 75, 90, 160)
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col, command=lambda c=col: None)
            self._tree.column(col, width=w, anchor="center", minwidth=w)

        vsb = ttk.Scrollbar(tbl_card, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(0, 16))
        vsb.pack(side="left", fill="y", pady=(0, 16), padx=(0, 16))
        self._tree.tag_configure("ot",    foreground=COLORS["warning"])
        self._tree.tag_configure("no_ot", foreground=COLORS["text"])
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _build_result_labels(self):
        metrics = [
            ("total_hours", "Total Hours",    COLORS["text"],    ""),
            ("ot_minutes",  "OT Minutes",     COLORS["warning"], "min"),
            ("ot_hours",    "OT Hours",       COLORS["warning"], "h"),
            ("regular_pay", "Regular Pay",    COLORS["success"], ""),
            ("ot_pay",      "OT Pay",         COLORS["warning"], ""),
            ("total_pay",   "Total Day Pay",  COLORS["accent"],  ""),
        ]
        self._result_vars = {}
        for i, (key, label, color, _) in enumerate(metrics):
            col = i % 3
            row_n = i // 3
            cell = tk.Frame(self._result_frame, bg=COLORS["card"])
            cell.grid(row=row_n, column=col, padx=16, pady=4, sticky="w")
            tk.Label(cell, text=label, font=FONTS["small"],
                     fg=COLORS["text_muted"], bg=COLORS["card"]).pack(anchor="w")
            var = tk.StringVar(value="—")
            lbl = tk.Label(cell, textvariable=var, font=FONTS["heading"],
                           fg=color, bg=COLORS["card"])
            lbl.pack(anchor="w")
            self._result_vars[key] = var

    # ── Period tab ────────────────────────────────────────────────────────────
    def _build_period_tab(self, parent):
        StyledLabel(parent, "Payroll Period Summary", style="title",
                    bg=COLORS["bg"]).pack(anchor="w", pady=(0, 16))

        # Period selector
        sel = StyledFrame(parent)
        sel.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(sel, bg=COLORS["card"])
        inner.pack(fill="x", padx=20, pady=12)

        StyledLabel(inner, "Period starting:", bg=COLORS["card"]).pack(side="left")
        self._period_var = tk.StringVar()
        self._period_combo = ttk.Combobox(inner, textvariable=self._period_var, width=22,
                                          state="readonly", font=FONTS["body"])
        self._period_combo.pack(side="left", padx=8)
        StyledButton(inner, "Load Period", command=self._load_selected_period,
                     style="primary").pack(side="left")

        # Summary cards
        summary_row = tk.Frame(parent, bg=COLORS["bg"])
        summary_row.pack(fill="x", pady=(0, 12))

        self._sum_cards = {}
        for key, label, color in [
            ("days",     "Days Worked",    COLORS["text"]),
            ("total_h",  "Total Hours",    COLORS["text"]),
            ("ot_h",     "Total OT Hours", COLORS["warning"]),
            ("ot_min",   "Total OT Min",   COLORS["warning"]),
            ("reg_pay",  "Regular Pay",    COLORS["success"]),
            ("ot_pay",   "OT Earnings",    COLORS["warning"]),
            ("tot_pay",  "Total Earnings", COLORS["accent"]),
        ]:
            card = StyledFrame(summary_row)
            card.pack(side="left", padx=(0, 8), fill="both", expand=True)
            tk.Label(card, text=label, font=FONTS["small"],
                     fg=COLORS["text_muted"], bg=COLORS["card"]).pack(pady=(10, 2), padx=12, anchor="w")
            var = tk.StringVar(value="—")
            tk.Label(card, textvariable=var, font=FONTS["heading"],
                     fg=color, bg=COLORS["card"]).pack(pady=(0, 10), padx=12, anchor="w")
            self._sum_cards[key] = var

        # Period detail table
        tbl_card = StyledFrame(parent)
        tbl_card.pack(fill="both", expand=True)
        StyledLabel(tbl_card, "Daily Details", style="heading",
                    bg=COLORS["card"]).pack(anchor="w", padx=20, pady=(12, 6))

        cols = ("Date", "Day", "Start", "End", "Break", "Total Hrs", "OT Min", "OT Hrs",
                "Reg Pay", "OT Pay", "Total Pay", "Notes")
        self._period_tree = ttk.Treeview(tbl_card, columns=cols, show="headings", height=14)
        col_widths = (110, 80, 70, 70, 55, 85, 70, 70, 85, 85, 90, 140)
        for col, w in zip(cols, col_widths):
            self._period_tree.heading(col, text=col)
            self._period_tree.column(col, width=w, anchor="center", minwidth=w)

        vsb2 = ttk.Scrollbar(tbl_card, orient="vertical", command=self._period_tree.yview)
        hsb2 = ttk.Scrollbar(tbl_card, orient="horizontal", command=self._period_tree.xview)
        self._period_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        self._period_tree.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(0, 4))
        vsb2.pack(side="left", fill="y", pady=(0, 4))

        self._period_tree.tag_configure("ot",    foreground=COLORS["warning"])
        self._period_tree.tag_configure("no_ot", foreground=COLORS["text"])
        self._period_tree.tag_configure("weekend", foreground=COLORS["text_muted"])

    # ── Settings tab ──────────────────────────────────────────────────────────
    def _build_settings_tab(self, parent):
        StyledLabel(parent, "Settings", style="title",
                    bg=COLORS["bg"]).pack(anchor="w", pady=(0, 16))

        card = StyledFrame(parent)
        card.pack(fill="x")

        self._setting_vars = {}
        settings_def = [
            ("employee_name",  "Employee Name",           "text",  "Employee"),
            ("hourly_rate",    "Hourly Rate",              "float", "15.00"),
            ("regular_hours",  "Regular Hours / Day",      "float", "8.0"),
            ("ot_multiplier",  "Overtime Multiplier",      "float", "1.5"),
            ("currency_symbol","Currency Symbol",          "text",  "$"),
        ]
        inner = tk.Frame(card, bg=COLORS["card"])
        inner.pack(fill="x", padx=24, pady=20)

        for i, (key, label, kind, default) in enumerate(settings_def):
            tk.Label(inner, text=label, font=FONTS["body"],
                     fg=COLORS["text"], bg=COLORS["card"],
                     width=24, anchor="w").grid(row=i, column=0, pady=8, sticky="w")
            var = tk.StringVar(value=default)
            ent = StyledEntry(inner, width=20, textvariable=var)
            ent.grid(row=i, column=1, padx=16, pady=8, sticky="w")
            self._setting_vars[key] = var

        StyledButton(inner, "💾  Save Settings", command=self._save_settings,
                     style="success").grid(row=len(settings_def), column=0,
                                           columnspan=2, pady=16, sticky="w")

        # Info box
        info = StyledFrame(parent)
        info.pack(fill="x", pady=(16, 0))
        info_text = (
            "ℹ️  Payroll Period: 19th of each month → 18th of the following month\n"
            "   OT Pay = OT Hours × Hourly Rate × OT Multiplier\n"
            "   Regular Pay = Regular Hours × Hourly Rate\n"
            "   Break time is subtracted before any calculations."
        )
        tk.Label(info, text=info_text, font=FONTS["small"],
                 fg=COLORS["text_muted"], bg=COLORS["card"],
                 justify="left", padx=20, pady=14).pack(anchor="w")

    # ── Navigation ────────────────────────────────────────────────────────────
    def _show_tab(self, tab):
        if self._active_tab:
            self._active_tab.pack_forget()
        tab.pack(fill="both", expand=True)
        self._active_tab = tab

    def _show_entry_tab(self):
        self._set_nav_active(0)
        self._show_tab(self._tab_entry)

    def _show_period_tab(self):
        self._set_nav_active(1)
        self._refresh_period_combos()
        self._load_selected_period()
        self._show_tab(self._tab_period)

    def _show_settings_tab(self):
        self._set_nav_active(2)
        self._show_tab(self._tab_settings)

    def _set_nav_active(self, index):
        for i, btn in enumerate(self._nav_buttons):
            btn.configure(bg=COLORS["accent"] if i == index else COLORS["sidebar"])

    # ── Settings I/O ─────────────────────────────────────────────────────────
    def _load_settings(self):
        for key, var in self._setting_vars.items():
            val = self.db.get_setting(key)
            if val:
                var.set(val)
        name = self.db.get_setting("employee_name") or "Employee"
        self._lbl_employee.configure(text=f"👤  {name}")

    def _save_settings(self):
        for key, var in self._setting_vars.items():
            self.db.set_setting(key, var.get().strip())
        name = self._setting_vars["employee_name"].get().strip() or "Employee"
        self._lbl_employee.configure(text=f"👤  {name}")
        messagebox.showinfo("Settings Saved", "Your settings have been saved successfully.")

    def _get_numeric_setting(self, key: str, default: float) -> float:
        try:
            return float(self.db.get_setting(key) or default)
        except ValueError:
            return default

    # ── Entry I/O ─────────────────────────────────────────────────────────────
    def _set_today(self):
        self._ent_date.delete(0, "end")
        self._ent_date.insert(0, datetime.date.today().isoformat())
        self._load_today()

    def _load_today(self):
        self._load_date(self._ent_date.get().strip())

    def _load_date(self, date_str: str):
        row = self.db.get_entry(date_str)
        if row:
            _, start, end, brk, notes = row
            for ent, val in [(self._ent_start, start), (self._ent_end, end),
                             (self._ent_break, str(brk)), (self._ent_notes, notes)]:
                ent.delete(0, "end")
                ent.insert(0, val)
            self._calculate_preview()

    def _save_entry(self):
        entry_date = self._ent_date.get().strip()
        start      = self._ent_start.get().strip()
        end        = self._ent_end.get().strip()
        notes      = self._ent_notes.get().strip()

        # Validate
        try:
            datetime.date.fromisoformat(entry_date)
        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a date in YYYY-MM-DD format.")
            return

        for label, val in [("Start time", start), ("End time", end)]:
            try:
                datetime.datetime.strptime(val, "%H:%M")
            except ValueError:
                messagebox.showerror("Invalid Time", f"{label} must be in HH:MM format (e.g. 08:00).")
                return

        try:
            brk = int(self._ent_break.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Invalid Break", "Break minutes must be a whole number.")
            return

        self.db.upsert_entry(entry_date, start, end, brk, notes)
        self._calculate_preview()
        self._refresh_period()
        messagebox.showinfo("Saved", f"Entry for {entry_date} saved successfully.")

    def _delete_entry(self):
        date_str = self._ent_date.get().strip()
        if not messagebox.askyesno("Delete Entry", f"Delete entry for {date_str}?"):
            return
        self.db.delete_entry(date_str)
        for ent in (self._ent_start, self._ent_end, self._ent_notes):
            ent.delete(0, "end")
        self._ent_break.delete(0, "end")
        self._ent_break.insert(0, "60")
        for var in self._result_vars.values():
            var.set("—")
        self._refresh_period()

    def _calculate_preview(self):
        start = self._ent_start.get().strip()
        end   = self._ent_end.get().strip()
        try:
            brk = int(self._ent_break.get().strip() or "0")
        except ValueError:
            brk = 0
        try:
            datetime.datetime.strptime(start, "%H:%M")
            datetime.datetime.strptime(end, "%H:%M")
        except ValueError:
            return

        rate    = self._get_numeric_setting("hourly_rate",   15.0)
        reg_h   = self._get_numeric_setting("regular_hours",  8.0)
        ot_mult = self._get_numeric_setting("ot_multiplier",  1.5)
        curr    = self.db.get_setting("currency_symbol") or "$"

        calc = calc_overtime(start, end, brk, reg_h, rate, ot_mult)

        self._result_vars["total_hours"].set(f"{calc['total_hours']:.2f} h  ({fmt_duration(calc['total_minutes'])})")
        self._result_vars["ot_minutes"].set(f"{calc['ot_minutes']} min")
        self._result_vars["ot_hours"].set(f"{calc['ot_hours']:.2f} h")
        self._result_vars["regular_pay"].set(f"{curr}{calc['regular_pay']:.2f}")
        self._result_vars["ot_pay"].set(f"{curr}{calc['ot_pay']:.2f}")
        self._result_vars["total_pay"].set(f"{curr}{calc['total_pay']:.2f}")

    # ── Period view ───────────────────────────────────────────────────────────
    def _refresh_period_combos(self):
        """Populate the period combo with last 6 payroll periods."""
        today = datetime.date.today()
        periods = []
        ref = today
        for _ in range(6):
            s, e = payroll_period(ref)
            label = f"{s.strftime('%d %b %Y')}  →  {e.strftime('%d %b %Y')}"
            periods.append((s.isoformat(), label))
            # Move back one period
            ref = s - datetime.timedelta(days=1)

        self._period_options = {lbl: iso for iso, lbl in periods}
        self._period_combo["values"] = [lbl for _, lbl in periods]
        if not self._period_var.get():
            self._period_combo.current(0)

    def _refresh_period(self):
        """Refresh the entry-tab table for current payroll period and sidebar stats."""
        today = datetime.date.today()
        start, end = payroll_period(today)
        self._lbl_period.configure(
            text=f"Period: {start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}")

        rate    = self._get_numeric_setting("hourly_rate",   15.0)
        reg_h   = self._get_numeric_setting("regular_hours",  8.0)
        ot_mult = self._get_numeric_setting("ot_multiplier",  1.5)
        curr    = self.db.get_setting("currency_symbol") or "$"

        entries = self.db.get_entries_for_period(start.isoformat(), end.isoformat())
        self._tree.delete(*self._tree.get_children())

        total_ot_min = 0
        total_ot_pay = 0.0

        for row in entries:
            date_str, st, en, brk, notes = row
            calc = calc_overtime(st, en, brk, reg_h, rate, ot_mult)
            tag  = "ot" if calc["ot_minutes"] > 0 else "no_ot"
            self._tree.insert("", "end", values=(
                date_str, st, en, f"{brk}m",
                f"{calc['total_hours']:.2f}",
                f"{calc['ot_minutes']}",
                f"{calc['ot_hours']:.2f}",
                f"{curr}{calc['ot_pay']:.2f}",
                notes,
            ), tags=(tag,))
            total_ot_min += calc["ot_minutes"]
            total_ot_pay += calc["ot_pay"]

        self._sb_days.configure(text=str(len(entries)))
        self._sb_ot_h.configure(text=fmt_duration(total_ot_min))
        self._sb_ot_pay.configure(text=f"{curr}{total_ot_pay:.2f}")

    def _load_selected_period(self):
        selected_label = self._period_var.get()
        if not selected_label or not hasattr(self, "_period_options"):
            return
        start_iso = self._period_options.get(selected_label)
        if not start_iso:
            return
        start = datetime.date.fromisoformat(start_iso)
        _, end = payroll_period(start)

        rate    = self._get_numeric_setting("hourly_rate",   15.0)
        reg_h   = self._get_numeric_setting("regular_hours",  8.0)
        ot_mult = self._get_numeric_setting("ot_multiplier",  1.5)
        curr    = self.db.get_setting("currency_symbol") or "$"

        entries = self.db.get_entries_for_period(start.isoformat(), end.isoformat())
        self._period_tree.delete(*self._period_tree.get_children())

        days = 0
        total_h = 0.0
        ot_h  = 0.0
        ot_min = 0
        reg_pay = 0.0
        ot_pay  = 0.0
        tot_pay = 0.0

        for row in entries:
            date_str, st, en, brk, notes = row
            d = datetime.date.fromisoformat(date_str)
            day_name = d.strftime("%A")
            calc = calc_overtime(st, en, brk, reg_h, rate, ot_mult)
            if d.weekday() >= 5:
                tag = "weekend"
            elif calc["ot_minutes"] > 0:
                tag = "ot"
            else:
                tag = "no_ot"
            self._period_tree.insert("", "end", values=(
                date_str, day_name, st, en, f"{brk}m",
                f"{calc['total_hours']:.2f}",
                f"{calc['ot_minutes']}",
                f"{calc['ot_hours']:.2f}",
                f"{curr}{calc['regular_pay']:.2f}",
                f"{curr}{calc['ot_pay']:.2f}",
                f"{curr}{calc['total_pay']:.2f}",
                notes,
            ), tags=(tag,))
            days    += 1
            total_h += calc["total_hours"]
            ot_h    += calc["ot_hours"]
            ot_min  += calc["ot_minutes"]
            reg_pay += calc["regular_pay"]
            ot_pay  += calc["ot_pay"]
            tot_pay += calc["total_pay"]

        self._sum_cards["days"].set(str(days))
        self._sum_cards["total_h"].set(f"{total_h:.2f} h")
        self._sum_cards["ot_h"].set(f"{ot_h:.2f} h")
        self._sum_cards["ot_min"].set(f"{ot_min} min")
        self._sum_cards["reg_pay"].set(f"{curr}{reg_pay:.2f}")
        self._sum_cards["ot_pay"].set(f"{curr}{ot_pay:.2f}")
        self._sum_cards["tot_pay"].set(f"{curr}{tot_pay:.2f}")

    # ── Tree selection ────────────────────────────────────────────────────────
    def _on_tree_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0])["values"]
        if values:
            date_str = values[0]
            self._ent_date.delete(0, "end")
            self._ent_date.insert(0, date_str)
            self._load_date(date_str)

    # ── Window close ─────────────────────────────────────────────────────────
    def _on_close(self):
        self.destroy()


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = OvertimeApp()
    app.mainloop()
