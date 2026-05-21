#!/usr/bin/env python3
"""Leadmachine — Lead-Dashboard für Google-Places-CSV-Dateien"""

import os
import sys
import csv
import json
import re
import platform
import shutil
import webbrowser
from datetime import datetime, date, timedelta

_IS_MAC    = platform.system() == "Darwin"
_FONT_D    = "SF Pro Display" if _IS_MAC else "Segoe UI"
_FONT_T    = "SF Pro Text"    if _IS_MAC else "Segoe UI"
_MOD       = "Command"        if _IS_MAC else "Control"
_UNDO_HINT = "⌘Z"            if _IS_MAC else "Strg+Z"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

# ── Pfade ─────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    if _IS_MAC:
        _base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(sys.executable))))
    else:
        _base = os.path.dirname(sys.executable)
else:
    _base = os.path.dirname(os.path.abspath(__file__))

DATA_FILE   = os.path.join(_base, "leads.json")
CONFIG_FILE = os.path.join(_base, "config.json")
BACKUP_DIR  = os.path.join(_base, "backups")

# ── Config ────────────────────────────────────────────────────────────────────
def _load_cfg():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cfg(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

CFG = _load_cfg()

# ── Appearance ────────────────────────────────────────────────────────────────
_DARK = CFG.get("appearance", "dark") == "dark"
ctk.set_appearance_mode("dark" if _DARK else "light")

if _DARK:
    BG      = "#0a0a0c"
    SIDEBAR = "#0c0c0f"
    CARD    = "#141417"
    CARD_HI = "#1b1b20"
    BORDER  = "#26262c"
    TEXT    = "#f4f4f6"
    SUBTLE  = "#a2a2ac"
    MUTED   = "#6c6c78"
    FAINT   = "#4a4a54"
else:
    BG      = "#f0f0f5"
    SIDEBAR = "#e4e4ec"
    CARD    = "#ffffff"
    CARD_HI = "#ebebf5"
    BORDER  = "#d0d0dc"
    TEXT    = "#0a0a1a"
    SUBTLE  = "#444454"
    MUTED   = "#888898"
    FAINT   = "#aaaabc"

ACCENT   = "#3b82f6"
ACCENT_H = "#2f6fd6"

STATUS = {
    "pending":            {"label": "Offen",          "bg": CARD,      "bd": BORDER,    "fg": SUBTLE},
    "nicht_erreicht":     {"label": "Nicht erreicht", "bg": "#241c08", "bd": "#4d3c12", "fg": "#e0a526"},
    "interessiert":       {"label": "Interessiert",   "bg": "#0e1729", "bd": "#23426c", "fg": "#5b9bf3"},
    "rueckruf":           {"label": "Rückruf",        "bg": "#1a1030", "bd": "#3d2a5c", "fg": "#b07ae8"},
    "nicht_interessiert": {"label": "Kein Interesse", "bg": "#251010", "bd": "#4d2222", "fg": "#ef6b6b"},
    "nicht_passend":      {"label": "Nicht passend",  "bg": "#1c1824", "bd": "#3d2f5c", "fg": "#a78bfa"},
    "kunde":              {"label": "Kunde",          "bg": "#0c1f13", "bd": "#1d4a2b", "fg": "#52c878"},
}

WD = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
MO = ["Januar","Februar","März","April","Mai","Juni","Juli","August",
      "September","Oktober","November","Dezember"]


def normalize_phone(phone):
    if not phone:
        return None
    n = re.sub(r"[^\d+]", "", phone)
    if n.startswith("0049"):
        n = "+49" + n[4:]
    elif n.startswith("049"):
        n = "+49" + n[3:]
    return n or None


class LeadMachine:
    def __init__(self):
        self.leads        = []
        self.current_idx  = 0
        self.view         = "call"
        self._current_lead = None
        self._last_action  = None
        self.nav           = {}
        self._call_filter  = "alle"
        self._call_start   = None
        self._timer_id     = None
        self._resize_id    = None
        self._load()
        self._auto_backup()
        self._build()
        self._show_view("call")
        self._refresh()
        self._bind_shortcuts()

    # ── Persistenz ───────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.leads = json.load(f).get("leads", [])
            except Exception:
                self.leads = []
        for lead in self.leads:
            lead.setdefault("attempts", 0)
            lead.setdefault("call_log", [])

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"leads": self.leads}, f, ensure_ascii=False, indent=2)

    # ── Auto-Backup ──────────────────────────────────────────────────────────

    def _auto_backup(self):
        if not os.path.exists(DATA_FILE):
            return
        os.makedirs(BACKUP_DIR, exist_ok=True)
        dest = os.path.join(BACKUP_DIR, f"leads_{date.today().isoformat()}.json")
        if not os.path.exists(dest):
            shutil.copy2(DATA_FILE, dest)
        backups = sorted(f for f in os.listdir(BACKUP_DIR)
                         if f.startswith("leads_") and f.endswith(".json"))
        for old in backups[:-14]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except Exception:
                pass

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        self.root = ctk.CTk()
        self.root.title("Leadmachine")
        self.root.configure(fg_color=BG)
        try:
            self.root.geometry(CFG.get("geometry", "1340x850"))
        except Exception:
            self.root.geometry("1340x850")
        self.root.minsize(1180, 760)
        self.root.bind("<Configure>", self._on_resize)

        self.f_logo    = ctk.CTkFont(_FONT_D, 17, "bold")
        self.f_h1      = ctk.CTkFont(_FONT_D, 23, "bold")
        self.f_sub     = ctk.CTkFont(_FONT_T, 13)
        self.f_section = ctk.CTkFont(_FONT_D, 15, "bold")
        self.f_micro   = ctk.CTkFont(_FONT_T, 11)
        self.f_label   = ctk.CTkFont(_FONT_T, 10, "bold")
        self.f_kpi     = ctk.CTkFont(_FONT_D, 25, "bold")
        self.f_company = ctk.CTkFont(_FONT_D, 25, "bold")
        self.f_body    = ctk.CTkFont(_FONT_T, 13)
        self.f_bodyb   = ctk.CTkFont(_FONT_T, 13, "bold")
        self.f_nav     = ctk.CTkFont(_FONT_T, 13)
        self.f_btn     = ctk.CTkFont(_FONT_D, 13, "bold")
        self.f_small   = ctk.CTkFont(_FONT_T, 12)

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _on_resize(self, event):
        if event.widget != self.root:
            return
        if self._resize_id:
            self.root.after_cancel(self._resize_id)
        self._resize_id = self.root.after(800, self._save_geometry)

    def _save_geometry(self):
        CFG["geometry"] = self.root.geometry()
        _save_cfg(CFG)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self.root, width=248, corner_radius=0,
                          fg_color=SIDEBAR, border_width=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)

        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=20, pady=(22, 26))
        mark = ctk.CTkFrame(logo, width=34, height=34, corner_radius=9, fg_color=ACCENT)
        mark.pack(side="left")
        mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="L", font=self.f_logo, text_color="#ffffff").pack(expand=True)
        ctk.CTkLabel(logo, text="Leadmachine", font=self.f_logo, text_color=TEXT).pack(
            side="left", padx=10)

        self._nav_section(sb, "ÜBERSICHT")
        self._nav_item(sb, "call",  "Anrufen",     lambda: self._show_view("call"))
        self._nav_item(sb, "list",  "Alle Leads",  lambda: self._show_view("list"))
        self._nav_item(sb, "stats", "Statistiken", lambda: self._show_view("stats"))
        self._nav_section(sb, "DATEN")
        self._nav_item(sb, "import", "CSV importieren", self._import_csv, toggle=False)

        theme_lbl = "☀  Hellmodus" if _DARK else "☾  Dunkelmodus"
        ctk.CTkButton(sb, text=theme_lbl, command=self._toggle_theme,
                      font=self.f_small, fg_color="transparent", hover_color=CARD_HI,
                      text_color=MUTED, corner_radius=8, height=34,
                      anchor="w").pack(fill="x", padx=16, pady=(8, 0))

        bottom = ctk.CTkFrame(sb, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=16, pady=18)
        prog_card = ctk.CTkFrame(bottom, fg_color=CARD, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        prog_card.pack(fill="x")
        inner = ctk.CTkFrame(prog_card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(inner, text="ABGEARBEITET", font=self.f_label, text_color=MUTED).pack(anchor="w")
        self.sb_prog_lbl = ctk.CTkLabel(inner, text="0 / 0", font=self.f_section, text_color=TEXT)
        self.sb_prog_lbl.pack(anchor="w", pady=(2, 6))
        self.sb_prog = ctk.CTkProgressBar(inner, height=6, corner_radius=3,
                                          fg_color=CARD_HI, progress_color=ACCENT)
        self.sb_prog.pack(fill="x")
        self.sb_prog.set(0)

    def _toggle_theme(self):
        CFG["appearance"] = "light" if _DARK else "dark"
        _save_cfg(CFG)
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        self.root.destroy()

    def _nav_section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=self.f_label, text_color=FAINT,
                     anchor="w").pack(fill="x", padx=24, pady=(12, 6))

    def _nav_item(self, parent, key, label, command, toggle=True):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=40)
        row.pack(fill="x", padx=12, pady=1)
        row.pack_propagate(False)
        indic = ctk.CTkFrame(row, width=3, corner_radius=2, fg_color="transparent")
        indic.pack(side="left", fill="y", pady=8)
        btn = ctk.CTkButton(row, text="   " + label, anchor="w", font=self.f_nav,
                            fg_color="transparent", hover_color=CARD,
                            text_color=SUBTLE, corner_radius=8, height=38, command=command)
        btn.pack(side="left", fill="both", expand=True, padx=(6, 0))
        if toggle:
            self.nav[key] = (indic, btn)

    def _set_nav_active(self, key):
        for k, (indic, btn) in self.nav.items():
            if k == key:
                indic.configure(fg_color=ACCENT)
                btn.configure(fg_color=CARD_HI, text_color=TEXT)
            else:
                indic.configure(fg_color="transparent")
                btn.configure(fg_color="transparent", text_color=SUBTLE)

    # ── Main ─────────────────────────────────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 12))
        tl = ctk.CTkFrame(top, fg_color="transparent")
        tl.pack(side="left")
        self.title_lbl = ctk.CTkLabel(tl, text="Anrufen", font=self.f_h1,
                                      text_color=TEXT, anchor="w")
        self.title_lbl.pack(anchor="w")
        now = datetime.now()
        date_str = f"{WD[now.weekday()]}, {now.day}. {MO[now.month-1]} {now.year}"
        ctk.CTkLabel(tl, text=date_str, font=self.f_sub, text_color=MUTED,
                     anchor="w").pack(anchor="w", pady=(2, 0))
        ctk.CTkButton(top, text="CSV importieren", command=self._import_csv,
                      font=self.f_btn, fg_color=ACCENT, hover_color=ACCENT_H,
                      text_color="#ffffff", corner_radius=9, height=40,
                      width=160).pack(side="right")

        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=28)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.call_view  = ctk.CTkFrame(self.content, fg_color="transparent")
        self.list_view  = ctk.CTkFrame(self.content, fg_color="transparent")
        self.stats_view = ctk.CTkFrame(self.content, fg_color="transparent")
        self._build_call_view()
        self._build_list_view()
        self._build_stats_view()

        self.statusbar_var = tk.StringVar(value="")
        sb_bar = ctk.CTkFrame(main, fg_color="transparent", height=26)
        sb_bar.grid(row=2, column=0, sticky="ew", padx=28, pady=(4, 10))
        ctk.CTkLabel(sb_bar, textvariable=self.statusbar_var, font=self.f_micro,
                     text_color=FAINT).pack(side="left")

    def _show_view(self, view):
        self.view = view
        for f in (self.call_view, self.list_view, self.stats_view):
            f.grid_forget()
        if view == "call":
            self.call_view.grid(row=0, column=0, sticky="nsew")
            self.title_lbl.configure(text="Anrufen")
            self._set_nav_active("call")
        elif view == "list":
            self.list_view.grid(row=0, column=0, sticky="nsew")
            self.title_lbl.configure(text="Alle Leads")
            self._set_nav_active("list")
            self._refresh_list()
        else:
            self.stats_view.grid(row=0, column=0, sticky="nsew")
            self.title_lbl.configure(text="Statistiken")
            self._set_nav_active("stats")
            self._refresh_stats()

    # ── Call-View ────────────────────────────────────────────────────────────

    def _build_call_view(self):
        v = self.call_view
        v.grid_columnconfigure(0, weight=3, uniform="c")
        v.grid_columnconfigure(1, weight=2, uniform="c")
        v.grid_rowconfigure(1, weight=1)

        kpis = ctk.CTkFrame(v, fg_color="transparent")
        kpis.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.kpi_vars = {}
        for i, (key, label, tint, fg, glyph) in enumerate([
            ("gesamt",       "Leads gesamt", "#1a2740", "#5b9bf3", "≡"),
            ("offen",        "Offen",        "#2a2410", "#e0a526", "○"),
            ("interessiert", "Interessiert", "#11243d", "#5b9bf3", "◆"),
            ("kunde",        "Kunden",       "#0e2417", "#52c878", "✓"),
        ]):
            kpis.grid_columnconfigure(i, weight=1)
            self._kpi_card(kpis, i, key, label, tint, fg, glyph)

        self.call_panel = self._section(v, "Nächster Anruf")
        self.call_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        self._build_lead_panel(self.call_panel)

        pipe = self._section(v, "Pipeline")
        pipe.grid(row=1, column=1, sticky="nsew")
        self._build_pipeline(pipe)

    def _kpi_card(self, parent, col, key, label, tint, fg, glyph):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER)
        card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack(fill="x", padx=16, pady=15)
        icon = ctk.CTkFrame(pad, width=42, height=42, corner_radius=10, fg_color=tint)
        icon.pack(side="left")
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text=glyph, font=ctk.CTkFont(size=18), text_color=fg).pack(expand=True)
        txt = ctk.CTkFrame(pad, fg_color="transparent")
        txt.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(txt, text=label.upper(), font=self.f_label, text_color=MUTED,
                     anchor="w").pack(anchor="w")
        var = tk.StringVar(value="0")
        self.kpi_vars[key] = var
        ctk.CTkLabel(txt, textvariable=var, font=self.f_kpi, text_color=TEXT,
                     anchor="w").pack(anchor="w", pady=(1, 0))

    def _section(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(18, 0))
        ctk.CTkLabel(head, text=title, font=self.f_section, text_color=TEXT).pack(side="left")
        return card

    def _build_lead_panel(self, panel):
        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=(14, 20))

        # Kopfzeile: Position · Timer · Status-Pille
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x")
        self.lead_pos  = ctk.CTkLabel(head, text="", font=self.f_label, text_color=MUTED)
        self.lead_pos.pack(side="left")
        self.timer_lbl = ctk.CTkLabel(head, text="", font=self.f_label, text_color=ACCENT)
        self.timer_lbl.pack(side="left", padx=(14, 0))
        self.status_pill = ctk.CTkLabel(head, text="  Offen  ", font=self.f_label,
                                        text_color=SUBTLE, fg_color=CARD_HI,
                                        corner_radius=11, height=22)
        self.status_pill.pack(side="right")

        # Schnellfilter-Chips
        chips = ctk.CTkFrame(body, fg_color="transparent")
        chips.pack(fill="x", pady=(8, 0))
        self._chip_btns = {}
        for key, lbl in [("alle","Alle"), ("pending","Offen"),
                          ("rueckruf","Rückrufe"), ("nicht_erreicht","Nicht erreicht")]:
            btn = ctk.CTkButton(chips, text=lbl, command=lambda k=key: self._set_call_filter(k),
                                font=self.f_micro, height=26, corner_radius=13,
                                fg_color=CARD_HI, hover_color=BORDER,
                                border_width=1, border_color=BORDER, text_color=MUTED)
            btn.pack(side="left", padx=(0, 6))
            self._chip_btns[key] = btn
        self._update_chips()

        # Firma + Rating + Zusatzinfos
        self.title_var = tk.StringVar()
        ctk.CTkLabel(body, textvariable=self.title_var, font=self.f_company,
                     text_color=TEXT, anchor="w", justify="left",
                     wraplength=560).pack(fill="x", pady=(10, 2))
        self.rating_var = tk.StringVar()
        ctk.CTkLabel(body, textvariable=self.rating_var, font=self.f_body,
                     text_color="#e0a526", anchor="w").pack(fill="x")
        self.reason_var = tk.StringVar()
        ctk.CTkLabel(body, textvariable=self.reason_var, font=self.f_small,
                     text_color="#a78bfa", anchor="w", wraplength=560).pack(fill="x", pady=(2, 0))
        self.rueckruf_var = tk.StringVar()
        ctk.CTkLabel(body, textvariable=self.rueckruf_var, font=self.f_small,
                     text_color="#b07ae8", anchor="w").pack(fill="x", pady=(2, 0))

        # Detail-Grid
        detail = ctk.CTkFrame(body, fg_color=BG, corner_radius=12,
                              border_width=1, border_color=BORDER)
        detail.pack(fill="x", pady=(12, 0))
        grid = ctk.CTkFrame(detail, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=14)
        self.phone_var    = tk.StringVar()
        self.address_var  = tk.StringVar()
        self.website_var  = tk.StringVar()
        self.category_var = tk.StringVar()
        self._detail_row(grid, 0, "TELEFON", self.phone_var,    ACCENT, self._copy_phone)
        self._detail_row(grid, 1, "ADRESSE", self.address_var,  TEXT,   None)
        self._detail_row(grid, 2, "WEBSITE", self.website_var,  ACCENT, self._open_website)
        self._detail_row(grid, 3, "BRANCHE", self.category_var, TEXT,   None)

        # Sekundäraktionen
        sec = ctk.CTkFrame(body, fg_color="transparent")
        sec.pack(fill="x", pady=(10, 0))
        _g = dict(fg_color=CARD_HI, hover_color=BORDER, corner_radius=9,
                  height=36, border_width=1, border_color=BORDER, font=self.f_btn)
        ctk.CTkButton(sec, text="Google Maps",  command=self._open_maps,
                      text_color=SUBTLE, width=120, **_g).pack(side="left")
        ctk.CTkButton(sec, text="Überspringen", command=self._skip,
                      text_color=MUTED,   width=120, **_g).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sec, text="Bearbeiten",   command=self._edit_lead,
                      text_color=ACCENT,  width=110, **_g).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sec, text="Löschen", command=self._delete_current,
                      fg_color="#1a0808", hover_color="#4d2020", text_color="#ef6b6b",
                      corner_radius=9, height=36, border_width=1, border_color="#4d2020",
                      font=self.f_btn, width=90).pack(side="right")

        # Notizen
        notes_hdr = ctk.CTkFrame(body, fg_color="transparent")
        notes_hdr.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(notes_hdr, text="NOTIZEN", font=self.f_label, text_color=MUTED).pack(side="left")
        ctk.CTkButton(notes_hdr, text="Verlauf", command=self._show_call_history,
                      font=self.f_micro, height=22, corner_radius=8,
                      fg_color=CARD_HI, hover_color=BORDER, text_color=MUTED,
                      border_width=1, border_color=BORDER).pack(side="right")
        self.notes_text = ctk.CTkTextbox(body, height=85, font=self.f_body,
                                          fg_color=BG, text_color=TEXT,
                                          corner_radius=10, border_width=1,
                                          border_color=BORDER, wrap="word")
        self.notes_text.pack(fill="x")

        # Status-Buttons
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(12, 0))
        order = ["nicht_erreicht","interessiert","rueckruf",
                 "nicht_interessiert","nicht_passend","kunde"]
        f_act = ctk.CTkFont(_FONT_D, 11, "bold")
        for i, st in enumerate(order):
            actions.grid_columnconfigure(i, weight=1)
            cfg = STATUS[st]
            if st == "nicht_passend":
                cmd = self._ask_reason_then_set
            elif st == "rueckruf":
                cmd = self._ask_rueckruf_date
            else:
                cmd = lambda s=st: self._set_status(s)
            ctk.CTkButton(actions, text=cfg["label"], font=f_act, command=cmd,
                          fg_color=cfg["bg"], hover_color=cfg["bd"],
                          text_color=cfg["fg"], border_width=1, border_color=cfg["bd"],
                          corner_radius=10, height=46).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 0))

        ctk.CTkLabel(body,
                     text=f"[1] Nicht err.  [2] Interessiert  [3] Rückruf  "
                          f"[4] Kein Interesse  [5] Nicht passend  [6] Kunde   "
                          f"Leertaste: Überspringen   Entf: Löschen   {_UNDO_HINT}: Rückgängig",
                     font=ctk.CTkFont(size=10), text_color=FAINT,
                     anchor="w", wraplength=700).pack(fill="x", pady=(6, 0))

    def _set_call_filter(self, key):
        self._call_filter = key
        self._update_chips()
        self.current_idx = 0
        self._refresh()

    def _update_chips(self):
        for key, btn in self._chip_btns.items():
            active = key == self._call_filter
            btn.configure(
                fg_color=ACCENT if active else CARD_HI,
                text_color="#ffffff" if active else MUTED,
                border_color=ACCENT if active else BORDER)

    def _detail_row(self, parent, r, label, var, color, cmd):
        parent.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(parent, text=label, font=self.f_label, text_color=MUTED,
                     anchor="w", width=90).grid(row=r, column=0, sticky="w", pady=5)
        lbl = ctk.CTkLabel(parent, textvariable=var, font=self.f_body,
                           text_color=color, anchor="w",
                           cursor="hand2" if cmd else "arrow")
        lbl.grid(row=r, column=1, sticky="w", pady=5)
        if cmd:
            lbl.bind("<Button-1>", lambda e: cmd())

    def _build_pipeline(self, panel):
        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=(14, 20))
        self.pipe = {}
        for st in ["pending","nicht_erreicht","interessiert","rueckruf",
                   "nicht_interessiert","nicht_passend","kunde"]:
            cfg = STATUS[st]
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=4)
            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x")
            dot = ctk.CTkFrame(hdr, width=9, height=9, corner_radius=5, fg_color=cfg["fg"])
            dot.pack(side="left", pady=2)
            dot.pack_propagate(False)
            ctk.CTkLabel(hdr, text=cfg["label"], font=self.f_body, text_color=SUBTLE).pack(
                side="left", padx=8)
            cnt = tk.StringVar(value="0")
            ctk.CTkLabel(hdr, textvariable=cnt, font=self.f_bodyb, text_color=TEXT).pack(side="right")
            bar = ctk.CTkProgressBar(row, height=5, corner_radius=3,
                                     fg_color=CARD_HI, progress_color=cfg["fg"])
            bar.pack(fill="x", pady=(4, 0))
            bar.set(0)
            self.pipe[st] = (cnt, bar)

        ctk.CTkFrame(body, fg_color=BORDER, height=1).pack(fill="x", pady=(12, 10))
        ctk.CTkLabel(body, text="GESAMTFORTSCHRITT", font=self.f_label,
                     text_color=MUTED, anchor="w").pack(fill="x")
        self.pipe_total = ctk.CTkLabel(body, text="0 %", font=self.f_h1,
                                       text_color=TEXT, anchor="w")
        self.pipe_total.pack(fill="x", pady=(2, 6))
        self.pipe_bar = ctk.CTkProgressBar(body, height=8, corner_radius=4,
                                           fg_color=CARD_HI, progress_color=ACCENT)
        self.pipe_bar.pack(fill="x")
        self.pipe_bar.set(0)
        self.pipe_hint = ctk.CTkLabel(body, text="", font=self.f_micro,
                                      text_color=MUTED, anchor="w")
        self.pipe_hint.pack(fill="x", pady=(6, 0))

    # ── Statistik-View ────────────────────────────────────────────────────────

    def _build_stats_view(self):
        v = self.stats_view
        v.grid_columnconfigure(0, weight=1)
        v.grid_columnconfigure(1, weight=1)
        v.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(v, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.stat_vars = {}
        for i, (key, label, tint, fg) in enumerate([
            ("conversion",   "Conversion Rate",  "#0e2417", "#52c878"),
            ("avg_attempts", "Ø Versuche/Kunde", "#11243d", "#5b9bf3"),
            ("heute",        "Heute bearbeitet", "#2a2410", "#e0a526"),
            ("avg_dur",      "Ø Gesprächszeit",  "#1c1824", "#a78bfa"),
        ]):
            top.grid_columnconfigure(i, weight=1)
            card = ctk.CTkFrame(top, fg_color=CARD, corner_radius=14,
                                border_width=1, border_color=BORDER)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            pad = ctk.CTkFrame(card, fg_color="transparent")
            pad.pack(fill="x", padx=16, pady=15)
            ctk.CTkLabel(pad, text=label.upper(), font=self.f_label,
                         text_color=MUTED, anchor="w").pack(anchor="w")
            var = tk.StringVar(value="—")
            self.stat_vars[key] = var
            ctk.CTkLabel(pad, textvariable=var, font=self.f_kpi,
                         text_color=TEXT, anchor="w").pack(anchor="w", pady=(4, 0))

        left = self._section(v, "Letzte Anrufe")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        self._build_call_log_table(left)

        right = self._section(v, "Status-Verteilung")
        right.grid(row=1, column=1, sticky="nsew")
        self._build_status_chart(right)

    def _build_call_log_table(self, panel):
        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(12, 16))
        wrap = tk.Frame(body, bg=CARD)
        wrap.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical")
        sb.pack(side="right", fill="y")
        style = ttk.Style()
        style.configure("Log.Treeview", background=CARD, foreground=SUBTLE,
                        fieldbackground=CARD, rowheight=30, borderwidth=0,
                        font=(_FONT_T, 11))
        style.configure("Log.Treeview.Heading", background=BG, foreground=MUTED,
                        font=(_FONT_T, 10, "bold"), relief="flat", borderwidth=0)
        style.map("Log.Treeview", background=[("selected", "#1d2a44")],
                  foreground=[("selected", TEXT)])
        self.log_tree = ttk.Treeview(wrap, columns=("time","firma","status","dauer"),
                                     show="headings", style="Log.Treeview",
                                     yscrollcommand=sb.set)
        sb.config(command=self.log_tree.yview)
        for c, lab, w in zip(("time","firma","status","dauer"),
                              ("ZEIT","FIRMA","STATUS","DAUER"),
                              (130, 210, 130, 80)):
            self.log_tree.heading(c, text=lab)
            self.log_tree.column(c, width=w, minwidth=40)
        self.log_tree.pack(fill="both", expand=True)
        for k, cfg in STATUS.items():
            self.log_tree.tag_configure(k, foreground=cfg["fg"])

    def _build_status_chart(self, panel):
        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=(14, 20))
        self.chart_rows = {}
        for st, cfg in STATUS.items():
            if st == "pending":
                continue
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=7)
            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr, text=cfg["label"], font=self.f_body,
                         text_color=cfg["fg"], anchor="w").pack(side="left")
            pct_var = tk.StringVar(value="0 %")
            ctk.CTkLabel(hdr, textvariable=pct_var, font=self.f_bodyb,
                         text_color=TEXT).pack(side="right")
            bar = ctk.CTkProgressBar(row, height=8, corner_radius=4,
                                     fg_color=CARD_HI, progress_color=cfg["fg"])
            bar.pack(fill="x", pady=(5, 0))
            bar.set(0)
            self.chart_rows[st] = (pct_var, bar)

    def _refresh_stats(self):
        today = date.today().isoformat()
        counts = {k: 0 for k in STATUS}
        att_to_kunde = []
        all_durations = []
        heute = 0

        for lead in self.leads:
            s = lead.get("status", "pending")
            counts[s] = counts.get(s, 0) + 1
            if s == "kunde":
                att_to_kunde.append(lead.get("attempts", 0))
            for e in lead.get("call_log", []):
                if e.get("duration_s"):
                    all_durations.append(e["duration_s"])
                if e.get("ts", "").startswith(today):
                    heute += 1

        total = len(self.leads)
        offen = counts["pending"] + counts["nicht_erreicht"] + counts["rueckruf"]
        done  = total - offen

        self.stat_vars["conversion"].set(
            f"{counts['kunde']/done*100:.1f}%" if done else "—")
        self.stat_vars["avg_attempts"].set(
            f"{sum(att_to_kunde)/len(att_to_kunde):.1f}" if att_to_kunde else "—")
        self.stat_vars["heute"].set(str(heute))
        if all_durations:
            avg_s = int(sum(all_durations) / len(all_durations))
            self.stat_vars["avg_dur"].set(f"{avg_s//60}:{avg_s%60:02d} min")
        else:
            self.stat_vars["avg_dur"].set("—")

        mx = max((counts[k] for k in STATUS if k != "pending"), default=1) or 1
        for st, (pct_var, bar) in self.chart_rows.items():
            n = counts.get(st, 0)
            pct_var.set(f"{n/total*100:.0f} %" if total else "0 %")
            bar.set(n / mx)

        self.log_tree.delete(*self.log_tree.get_children())
        entries = []
        for lead in self.leads:
            for e in lead.get("call_log", []):
                entries.append((e.get("ts", ""), lead.get("title", ""), e))
        entries.sort(key=lambda x: x[0], reverse=True)
        for ts, firma, e in entries[:100]:
            try:
                ts_str = datetime.fromisoformat(ts).strftime("%d.%m. %H:%M")
            except Exception:
                ts_str = ts[:16]
            st = e.get("status_after", "")
            dur_s = e.get("duration_s", 0)
            self.log_tree.insert("", "end", tags=(st,),
                                 values=(ts_str, firma,
                                         STATUS.get(st, {}).get("label", st),
                                         f"{dur_s//60}:{dur_s%60:02d}" if dur_s else "—"))

    # ── List-View ────────────────────────────────────────────────────────────

    def _build_list_view(self):
        v = self.list_view
        card = ctk.CTkFrame(v, fg_color=CARD, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True)

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(18, 10))

        ctk.CTkLabel(bar, text="STATUS", font=self.f_label, text_color=MUTED).pack(
            side="left", padx=(0, 8))
        self.filter_var = tk.StringVar(value="Alle")
        opts = ["Alle"] + [STATUS[k]["label"] for k in STATUS]
        ctk.CTkOptionMenu(bar, values=opts, variable=self.filter_var,
                          command=lambda _: self._refresh_list(),
                          font=self.f_body, fg_color=BG, button_color=CARD_HI,
                          button_hover_color=BORDER, text_color=TEXT,
                          dropdown_fg_color=CARD, dropdown_hover_color=CARD_HI,
                          dropdown_text_color=TEXT, corner_radius=8,
                          width=170).pack(side="left")

        ctk.CTkLabel(bar, text="SUCHE", font=self.f_label, text_color=MUTED).pack(
            side="left", padx=(20, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_list())
        ctk.CTkEntry(bar, textvariable=self.search_var, font=self.f_body,
                     fg_color=BG, text_color=TEXT, corner_radius=8,
                     border_color=BORDER, width=280,
                     placeholder_text="Firma, Telefon, Stadt …").pack(side="left")

        _rb = dict(font=self.f_btn, corner_radius=8, height=34, border_width=1)
        ctk.CTkButton(bar, text="CSV exportieren", command=self._export_csv,
                      fg_color=CARD_HI, hover_color=BORDER, text_color=SUBTLE,
                      border_color=BORDER, width=130, **_rb).pack(side="right", padx=(8, 0))
        ctk.CTkButton(bar, text="Löschen", command=self._delete_selected,
                      fg_color="#1a0808", hover_color="#4d2020", text_color="#ef6b6b",
                      border_color="#4d2020", width=90, **_rb).pack(side="right")
        self.list_count = ctk.CTkLabel(bar, text="", font=self.f_small, text_color=MUTED)
        self.list_count.pack(side="right", padx=(0, 16))

        wrap = tk.Frame(card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        style = ttk.Style()
        style.theme_use("default")
        style.configure("LM.Treeview", background=CARD, foreground=SUBTLE,
                        fieldbackground=CARD, rowheight=34, borderwidth=0,
                        font=(_FONT_T, 12))
        style.configure("LM.Treeview.Heading", background=BG, foreground=MUTED,
                        font=(_FONT_T, 10, "bold"), relief="flat",
                        borderwidth=0, padding=(8, 8))
        style.map("LM.Treeview", background=[("selected", "#1d2a44")],
                  foreground=[("selected", TEXT)])
        style.map("LM.Treeview.Heading", background=[("active", CARD_HI)])

        sb_scroll = ttk.Scrollbar(wrap, orient="vertical")
        sb_scroll.pack(side="right", fill="y")
        cols   = ("title","phone","city","category","rating","attempts","status")
        labels = ("FIRMA","TELEFON","STADT","BRANCHE","BEWERTUNG","VERSUCHE","STATUS")
        widths = (270, 155, 120, 175, 105, 80, 140)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 style="LM.Treeview", yscrollcommand=sb_scroll.set,
                                 selectmode="extended")
        sb_scroll.config(command=self.tree.yview)
        for c, lab, w in zip(cols, labels, widths):
            self.tree.heading(c, text=lab, command=lambda x=c: self._sort_list(x))
            self.tree.column(c, width=w, minwidth=50)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._jump_to_lead)
        self.tree.bind("<Delete>",    lambda e: self._delete_selected())
        self.tree.bind("<BackSpace>", lambda e: self._delete_selected())
        for k, cfg in STATUS.items():
            self.tree.tag_configure(k, foreground=cfg["fg"])

    # ── Logik ────────────────────────────────────────────────────────────────

    def _callable(self):
        f = self._call_filter
        if f == "pending":
            pool = [l for l in self.leads if l["status"] == "pending"]
        elif f == "rueckruf":
            pool = [l for l in self.leads if l["status"] == "rueckruf"]
        elif f == "nicht_erreicht":
            pool = [l for l in self.leads if l["status"] == "nicht_erreicht"]
        else:
            pool = [l for l in self.leads if l["status"] in ("pending","rueckruf","nicht_erreicht")]

        def _key(l):
            if l["status"] == "rueckruf" and l.get("rueckruf_at"):
                return (0, l["rueckruf_at"])
            return (1, l.get("added_at", ""))
        pool.sort(key=_key)
        return pool

    def _current(self):
        q = self._callable()
        if not q:
            return None
        self.current_idx = min(self.current_idx, len(q) - 1)
        return q[self.current_idx]

    def _refresh(self):
        self._update_stats()
        lead = self._current()
        if lead:
            self._show_lead(lead)
        else:
            self._show_empty()
        if self.view == "list":
            self._refresh_list()

    def _update_stats(self):
        counts = {k: 0 for k in STATUS}
        for l in self.leads:
            counts[l.get("status", "pending")] = counts.get(l.get("status","pending"), 0) + 1
        total = len(self.leads)
        self.kpi_vars["gesamt"].set(str(total))
        self.kpi_vars["offen"].set(str(counts["pending"]))
        self.kpi_vars["interessiert"].set(str(counts["interessiert"]))
        self.kpi_vars["kunde"].set(str(counts["kunde"]))
        mx = max(counts.values()) if any(counts.values()) else 1
        for st, (cnt, bar) in self.pipe.items():
            cnt.set(str(counts.get(st, 0)))
            bar.set(counts.get(st, 0) / mx)
        offen = counts["pending"] + counts["nicht_erreicht"] + counts["rueckruf"]
        done  = total - offen
        frac  = (done / total) if total else 0
        self.sb_prog.set(frac)
        self.sb_prog_lbl.configure(text=f"{done} / {total}")
        self.pipe_bar.set(frac)
        self.pipe_total.configure(text=f"{int(frac*100)} %")
        self.pipe_hint.configure(text=f"{done} bearbeitet · {offen} offen")

    def _show_lead(self, lead):
        q = self._callable()
        idx = q.index(lead) + 1 if lead in q else "?"
        pos = f"LEAD {idx} VON {len(q)}"
        if lead.get("attempts", 0) > 0:
            pos += f"  ·  {lead['attempts'] + 1}. Versuch"
        self.lead_pos.configure(text=pos)

        cfg = STATUS.get(lead["status"], STATUS["pending"])
        self.status_pill.configure(text=f"  {cfg['label']}  ",
                                   fg_color=cfg["bg"], text_color=cfg["fg"])
        self.title_var.set(lead.get("title") or "—")
        rating = lead.get("rating", "")
        if rating:
            try:
                r = int(round(float(rating)))
                stars = "★" * r + "☆" * (5 - r)
            except ValueError:
                stars = ""
            self.rating_var.set(f"{stars}   {rating}  ·  {lead.get('reviews','')} Bewertungen")
        else:
            self.rating_var.set("☆☆☆☆☆   Keine Bewertung")

        reason = lead.get("reason", "")
        self.reason_var.set(f"Nicht passend: {reason}" if reason else "")

        rb = lead.get("rueckruf_at", "")
        if rb:
            try:
                dt = datetime.fromisoformat(rb)
                tag = " (überfällig!)" if dt < datetime.now() else ""
                self.rueckruf_var.set(f"Rückruf: {dt.strftime('%d.%m.%Y %H:%M')}{tag}")
            except Exception:
                self.rueckruf_var.set("")
        else:
            self.rueckruf_var.set("")

        self.phone_var.set(lead.get("phone") or "—")
        parts = [lead.get("street",""), lead.get("city","")]
        self.address_var.set(", ".join(p for p in parts if p) or "—")
        self.website_var.set(lead.get("website") or "—")
        self.category_var.set(lead.get("category") or "—")
        self.notes_text.delete("1.0", "end")
        if lead.get("notes"):
            self.notes_text.insert("1.0", lead["notes"])
        self._current_lead = lead
        self._start_timer()

    def _show_empty(self):
        self._stop_timer()
        self.lead_pos.configure(text="")
        self.timer_lbl.configure(text="")
        self.status_pill.configure(text="  Fertig  ", fg_color=STATUS["kunde"]["bg"],
                                   text_color=STATUS["kunde"]["fg"])
        if self.leads:
            self.title_var.set("Alle Leads abgearbeitet")
            self.rating_var.set("Keine offenen Anrufe mehr")
        else:
            self.title_var.set("Noch keine Leads")
            self.rating_var.set("Importiere eine CSV-Datei zum Start")
        for v in (self.phone_var, self.address_var, self.website_var, self.category_var):
            v.set("—")
        self.reason_var.set("")
        self.rueckruf_var.set("")
        self.notes_text.delete("1.0", "end")
        self._current_lead = None

    # ── Timer ────────────────────────────────────────────────────────────────

    def _start_timer(self):
        self._stop_timer()
        self._call_start = datetime.now()
        self._timer_tick()

    def _stop_timer(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        self._call_start = None

    def _timer_tick(self):
        if not self._call_start:
            return
        s = int((datetime.now() - self._call_start).total_seconds())
        self.timer_lbl.configure(text=f"⏱ {s//60}:{s%60:02d}")
        self._timer_id = self.root.after(1000, self._timer_tick)

    def _elapsed_s(self):
        return int((datetime.now() - self._call_start).total_seconds()) if self._call_start else 0

    # ── Notizen / Verlauf ────────────────────────────────────────────────────

    def _save_notes(self):
        if self._current_lead:
            self._current_lead["notes"] = self.notes_text.get("1.0", "end").strip()

    def _show_call_history(self):
        lead = self._current_lead
        if not lead:
            return
        log = lead.get("call_log", [])
        if not log:
            messagebox.showinfo("Verlauf", "Noch keine Anrufaufzeichnungen.")
            return
        win = ctk.CTkToplevel(self.root)
        win.title(f"Verlauf: {lead.get('title','')}")
        win.geometry("560x440")
        win.configure(fg_color=BG)
        win.grab_set()
        win.after(150, win.lift)
        ctk.CTkLabel(win, text="ANRUFVERLAUF", font=self.f_section,
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(20, 12))
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for entry in reversed(log):
            try:
                ts_str = datetime.fromisoformat(entry.get("ts","")).strftime("%d.%m.%Y %H:%M")
            except Exception:
                ts_str = entry.get("ts","")[:16]
            st  = entry.get("status_after","")
            cfg = STATUS.get(st, {})
            dur = entry.get("duration_s", 0)
            dur_str = f"{dur//60}:{dur%60:02d} min" if dur else "—"
            card = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=10,
                                border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=(0, 8))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)
            hdr = ctk.CTkFrame(inner, fg_color="transparent")
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr, text=ts_str, font=self.f_label, text_color=MUTED).pack(side="left")
            ctk.CTkLabel(hdr, text=cfg.get("label", st), font=self.f_label,
                         text_color=cfg.get("fg", SUBTLE)).pack(side="left", padx=(10, 0))
            ctk.CTkLabel(hdr, text=dur_str, font=self.f_label, text_color=FAINT).pack(side="right")
            notes = entry.get("notes","")
            if notes:
                ctk.CTkLabel(inner, text=notes, font=self.f_small, text_color=SUBTLE,
                             anchor="w", justify="left", wraplength=480).pack(fill="x", pady=(6,0))

    # ── Status-Dialoge ───────────────────────────────────────────────────────

    def _ask_rueckruf_date(self):
        if not self._current_lead:
            return
        win = ctk.CTkToplevel(self.root)
        win.title("Rückruf planen")
        win.geometry("400x260")
        win.configure(fg_color=BG)
        win.grab_set()
        win.after(150, win.lift)

        ctk.CTkLabel(win, text="RÜCKRUF-TERMIN", font=self.f_section,
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(22, 12))

        date_var = tk.StringVar()
        time_var = tk.StringVar(value="09:00")

        quick = ctk.CTkFrame(win, fg_color="transparent")
        quick.pack(fill="x", padx=24, pady=(0, 12))
        _q = dict(font=self.f_small, height=30, corner_radius=8, fg_color=CARD_HI,
                  hover_color=BORDER, border_width=1, border_color=BORDER, text_color=SUBTLE)
        def _qset(days):
            date_var.set((date.today() + timedelta(days=days)).strftime("%d.%m.%Y"))
        ctk.CTkButton(quick, text="Morgen",   command=lambda: _qset(1),  **_q).pack(side="left")
        ctk.CTkButton(quick, text="+2 Tage",  command=lambda: _qset(2),  **_q).pack(side="left", padx=(8,0))
        ctk.CTkButton(quick, text="+1 Woche", command=lambda: _qset(7),  **_q).pack(side="left", padx=(8,0))
        _qset(1)

        for lbl, var, ph in [("DATUM (TT.MM.JJJJ)", date_var, "25.12.2025"),
                              ("UHRZEIT (HH:MM)",    time_var, "09:00")]:
            r = ctk.CTkFrame(win, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=(0, 6))
            ctk.CTkLabel(r, text=lbl, font=self.f_label, text_color=MUTED).pack(anchor="w")
            ctk.CTkEntry(r, textvariable=var, font=self.f_body, fg_color=CARD,
                         text_color=TEXT, corner_radius=8, border_color=BORDER,
                         height=36, placeholder_text=ph).pack(fill="x", pady=(3,0))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(12, 0))

        def _confirm():
            try:
                dt = datetime.strptime(f"{date_var.get().strip()} {time_var.get().strip()}",
                                       "%d.%m.%Y %H:%M")
            except ValueError:
                messagebox.showerror("Fehler", "Format: TT.MM.JJJJ und HH:MM")
                return
            win.destroy()
            self._set_status("rueckruf", rueckruf_at=dt.isoformat())

        ctk.CTkButton(btn_row, text="Speichern", command=_confirm, font=self.f_btn,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color="#ffffff",
                      corner_radius=9, height=38).pack(side="left")
        ctk.CTkButton(btn_row, text="Ohne Datum", font=self.f_btn,
                      command=lambda: [win.destroy(), self._set_status("rueckruf")],
                      fg_color=CARD_HI, hover_color=BORDER, text_color=MUTED,
                      corner_radius=9, height=38, border_width=1,
                      border_color=BORDER).pack(side="left", padx=(8, 0))
        win.bind("<Return>", lambda e: _confirm())

    def _ask_reason_then_set(self):
        if not self._current_lead:
            return
        win = ctk.CTkToplevel(self.root)
        win.title("Nicht passend")
        win.geometry("460x210")
        win.configure(fg_color=BG)
        win.grab_set()
        win.after(150, win.lift)
        ctk.CTkLabel(win, text="BEGRÜNDUNG (optional)", font=self.f_label,
                     text_color=MUTED).pack(anchor="w", padx=24, pady=(22, 6))
        var = tk.StringVar()
        entry = ctk.CTkEntry(win, textvariable=var, font=self.f_body, fg_color=CARD,
                             text_color=TEXT, corner_radius=8, border_color=BORDER, height=38,
                             placeholder_text="z.B. hat bereits Agentur, zu groß …")
        entry.pack(fill="x", padx=24)
        entry.focus()
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 0))
        def _confirm():
            reason = var.get().strip()
            win.destroy()
            self._set_status("nicht_passend", reason=reason)
        ctk.CTkButton(btn_row, text="Speichern", command=_confirm, font=self.f_btn,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color="#ffffff",
                      corner_radius=9, height=38).pack(side="left")
        ctk.CTkButton(btn_row, text="Abbrechen", command=win.destroy, font=self.f_btn,
                      fg_color=CARD_HI, hover_color=BORDER, text_color=MUTED,
                      corner_radius=9, height=38, border_width=1,
                      border_color=BORDER).pack(side="left", padx=(8, 0))
        win.bind("<Return>", lambda e: _confirm())

    def _set_status(self, status, reason="", rueckruf_at=None):
        if not self._current_lead:
            return
        self._save_notes()
        duration_s = self._elapsed_s()
        self._stop_timer()

        self._current_lead.setdefault("call_log", []).append({
            "ts":           datetime.now().isoformat(),
            "status_before": self._current_lead["status"],
            "status_after":  status,
            "notes":         self._current_lead.get("notes", ""),
            "duration_s":    duration_s,
        })

        self._last_action = {
            "lead_id":       self._current_lead["id"],
            "prev_status":   self._current_lead["status"],
            "prev_notes":    self._current_lead.get("notes", ""),
            "prev_reason":   self._current_lead.get("reason", ""),
            "prev_rueckruf": self._current_lead.get("rueckruf_at"),
            "prev_attempts": self._current_lead.get("attempts", 0),
            "prev_called":   self._current_lead.get("called_at"),
        }
        if status == "nicht_erreicht":
            self._current_lead["attempts"] = self._current_lead.get("attempts", 0) + 1
        if status == "nicht_passend":
            self._current_lead["reason"] = reason
        else:
            self._current_lead.pop("reason", None)
        if rueckruf_at:
            self._current_lead["rueckruf_at"] = rueckruf_at
        elif status != "rueckruf":
            self._current_lead.pop("rueckruf_at", None)
        self._current_lead["status"]    = status
        self._current_lead["called_at"] = datetime.now().isoformat()
        self._save()
        self.current_idx = 0
        self._refresh()
        self.statusbar_var.set(
            f"Status gesetzt: {STATUS[status]['label']}   ·   {_UNDO_HINT} zum Rückgängigmachen")

    def _skip(self):
        q = self._callable()
        if len(q) > 1:
            self._save_notes()
            if self._current_lead:
                self._save()
            self.current_idx = (self.current_idx + 1) % len(q)
            self._refresh()

    def _copy_phone(self):
        if not self._current_lead:
            return
        phone = self._current_lead.get("phone", "")
        if phone and phone != "—":
            self.root.clipboard_clear()
            self.root.clipboard_append(phone)
            self.statusbar_var.set(f"Kopiert: {phone}")

    def _open_website(self):
        if not self._current_lead:
            return
        url = self._current_lead.get("website", "")
        if url and url != "—":
            webbrowser.open(url if url.startswith("http") else "https://" + url)

    def _open_maps(self):
        if not self._current_lead:
            return
        url = self._current_lead.get("maps_url", "")
        if url:
            webbrowser.open(url)

    # ── Löschen ──────────────────────────────────────────────────────────────

    def _delete_current(self):
        if not self._current_lead:
            return
        name = self._current_lead.get("title", "Unbekannt")
        if not messagebox.askyesno("Lead löschen",
                f"'{name}' wirklich löschen?\nKann nicht rückgängig gemacht werden."):
            return
        self.leads = [l for l in self.leads if l["id"] != self._current_lead["id"]]
        self._last_action = None
        self._current_lead = None
        self.current_idx = 0
        self._save()
        self._refresh()
        self.statusbar_var.set(f"'{name}' gelöscht")

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        msg = (f"'{next((l.get('title','?') for l in self.leads if l['id']==sel[0]),'')}' löschen?"
               if len(sel) == 1 else f"{len(sel)} Leads löschen?")
        if not messagebox.askyesno("Löschen",
                msg + "\nKann nicht rückgängig gemacht werden."):
            return
        ids = set(sel)
        self.leads = [l for l in self.leads if l["id"] not in ids]
        if self._current_lead and self._current_lead.get("id") in ids:
            self._current_lead = None
            self.current_idx = 0
        self._last_action = None
        self._save()
        self._refresh_list()
        self._update_stats()
        self.statusbar_var.set(f"{len(sel)} Lead(s) gelöscht")

    # ── Rückgängig ───────────────────────────────────────────────────────────

    def _undo(self):
        if not self._last_action:
            self.statusbar_var.set("Nichts zum Rückgängigmachen")
            return
        a = self._last_action
        lead = next((l for l in self.leads if l["id"] == a["lead_id"]), None)
        if not lead:
            self.statusbar_var.set("Lead nicht mehr vorhanden")
            return
        lead["status"]    = a["prev_status"]
        lead["notes"]     = a["prev_notes"]
        lead["attempts"]  = a["prev_attempts"]
        lead["called_at"] = a["prev_called"]
        if a.get("prev_reason"):
            lead["reason"] = a["prev_reason"]
        else:
            lead.pop("reason", None)
        if a.get("prev_rueckruf"):
            lead["rueckruf_at"] = a["prev_rueckruf"]
        else:
            lead.pop("rueckruf_at", None)
        if lead.get("call_log"):
            lead["call_log"].pop()
        self._last_action = None
        self._save()
        self.current_idx = 0
        self._refresh()
        cfg = STATUS.get(a["prev_status"], STATUS["pending"])
        self.statusbar_var.set(f"Rückgängig: Status zurück auf '{cfg['label']}'")

    # ── Lead bearbeiten ──────────────────────────────────────────────────────

    def _edit_lead(self):
        lead = self._current_lead
        if not lead:
            return
        win = ctk.CTkToplevel(self.root)
        win.title("Lead bearbeiten")
        win.geometry("500x370")
        win.configure(fg_color=BG)
        win.grab_set()
        win.after(150, win.lift)
        ctk.CTkLabel(win, text="LEAD BEARBEITEN", font=self.f_section,
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(22, 14))
        entries = {}
        for label, key in [("Firma","title"),("Telefon","phone"),
                            ("Website","website"),("Branche","category")]:
            row = ctk.CTkFrame(win, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(row, text=label.upper(), font=self.f_label, text_color=MUTED).pack(anchor="w")
            var = tk.StringVar(value=lead.get(key, ""))
            ctk.CTkEntry(row, textvariable=var, font=self.f_body, fg_color=CARD,
                         text_color=TEXT, corner_radius=8, border_color=BORDER,
                         height=36).pack(fill="x", pady=(3, 0))
            entries[key] = var
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 0))
        def _save_edit():
            for key, var in entries.items():
                lead[key] = var.get().strip()
            lead["phone_normalized"] = normalize_phone(lead.get("phone",""))
            self._save()
            self._refresh()
            win.destroy()
            self.statusbar_var.set(f"'{lead.get('title','')}' aktualisiert")
        ctk.CTkButton(btn_row, text="Speichern", command=_save_edit, font=self.f_btn,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color="#ffffff",
                      corner_radius=9, height=38).pack(side="left")
        ctk.CTkButton(btn_row, text="Abbrechen", command=win.destroy, font=self.f_btn,
                      fg_color=CARD_HI, hover_color=BORDER, text_color=MUTED,
                      corner_radius=9, height=38, border_width=1,
                      border_color=BORDER).pack(side="left", padx=(8, 0))

    # ── CSV Export ───────────────────────────────────────────────────────────

    def _export_csv(self):
        visible_ids = set(self.tree.get_children())
        visible = [l for l in self.leads if l["id"] in visible_ids]
        if not visible:
            messagebox.showinfo("Export", "Keine Leads zum Exportieren.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV","*.csv"),("Alle Dateien","*.*")],
            initialfile="leads_export.csv")
        if not path:
            return
        slabels = {k: v["label"] for k, v in STATUS.items()}
        fields = ["title","phone","city","street","website","category",
                  "rating","reviews","status","attempts","notes","reason"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for l in visible:
                row = {k: l.get(k,"") for k in fields}
                row["status"] = slabels.get(l.get("status",""), l.get("status",""))
                writer.writerow(row)
        self.statusbar_var.set(f"{len(visible)} Leads exportiert → {os.path.basename(path)}")

    # ── CSV Import ───────────────────────────────────────────────────────────

    def _import_csv(self):
        paths = filedialog.askopenfilenames(
            title="CSV-Dateien auswählen",
            filetypes=[("CSV Dateien","*.csv"),("Alle Dateien","*.*")])
        if not paths:
            return
        existing = {l["phone_normalized"] for l in self.leads if l.get("phone_normalized")}
        added = duplicates = skipped = 0
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        phone_raw  = row.get("phone","").strip()
                        phone_norm = normalize_phone(phone_raw)
                        if phone_norm and phone_norm in existing:
                            duplicates += 1
                            continue
                        title = row.get("title","").strip()
                        if not title:
                            skipped += 1
                            continue
                        cats = [row.get(f"categories/{i}","").strip()
                                for i in range(10) if row.get(f"categories/{i}","").strip()]
                        self.leads.append({
                            "id": f"{datetime.now().isoformat()}_{len(self.leads)+added}",
                            "title": title, "phone": phone_raw,
                            "phone_normalized": phone_norm,
                            "street":   row.get("street","").strip(),
                            "city":     row.get("city","").strip(),
                            "website":  row.get("website","").strip(),
                            "rating":   row.get("totalScore","").strip(),
                            "reviews":  row.get("reviewsCount","").strip(),
                            "category": row.get("categoryName","").strip() or (cats[0] if cats else ""),
                            "maps_url": row.get("url","").strip(),
                            "status": "pending", "notes": "", "attempts": 0,
                            "call_log": [],
                            "added_at": datetime.now().isoformat(), "called_at": None,
                        })
                        if phone_norm:
                            existing.add(phone_norm)
                        added += 1
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Lesen:\n{path}\n\n{e}")
        self._save()
        self.current_idx = 0
        self._refresh()
        msg = f"{added} Leads importiert"
        if duplicates:
            msg += f"\n{duplicates} Duplikate übersprungen"
        if skipped:
            msg += f"\n{skipped} Zeilen ohne Firmenname übersprungen"
        messagebox.showinfo("Import abgeschlossen", msg)

    # ── Tastaturkürzel ───────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        def _in_text(w):
            return isinstance(w, (tk.Text, tk.Entry))

        def on_key(event):
            if _in_text(event.widget) or self.view != "call":
                return
            k = event.keysym
            if k in ("1","2","4","6"):
                st = {"1":"nicht_erreicht","2":"interessiert",
                      "4":"nicht_interessiert","6":"kunde"}[k]
                self._set_status(st)
            elif k == "3":
                self._ask_rueckruf_date()
            elif k == "5":
                self._ask_reason_then_set()
            elif k == "space":
                self._skip()

        def on_delete(event):
            if not _in_text(event.widget) and self.view == "call":
                self._delete_current()

        self.root.bind("<Key>",        on_key)
        self.root.bind("<Delete>",     on_delete)
        self.root.bind(f"<{_MOD}-z>", lambda e: self._undo())
        self.root.bind(f"<{_MOD}-Z>", lambda e: self._undo())

    # ── List-Refresh ─────────────────────────────────────────────────────────

    def _refresh_list(self):
        if not hasattr(self, "tree"):
            return
        label_to_key = {STATUS[k]["label"]: k for k in STATUS}
        filt_key = label_to_key.get(self.filter_var.get())
        query = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for lead in self.leads:
            if filt_key and lead["status"] != filt_key:
                continue
            if query:
                hay = (lead.get("title","") + lead.get("phone","") +
                       lead.get("city","") + lead.get("category","")).lower()
                if query not in hay:
                    continue
            rating   = lead.get("rating","")
            attempts = lead.get("attempts", 0)
            cfg      = STATUS.get(lead["status"], {})
            self.tree.insert("", "end", iid=lead["id"], tags=(lead["status"],),
                             values=(lead.get("title",""), lead.get("phone",""),
                                     lead.get("city",""), lead.get("category",""),
                                     f"★ {rating}" if rating else "—",
                                     str(attempts) if attempts else "—",
                                     cfg.get("label", lead["status"])))
            shown += 1
        self.list_count.configure(text=f"{shown} von {len(self.leads)} Leads")

    def _sort_list(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort()
        for idx, (_, k) in enumerate(items):
            self.tree.move(k, "", idx)

    def _jump_to_lead(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        lead = next((l for l in self.leads if l["id"] == sel[0]), None)
        if not lead:
            return
        q = self._callable()
        if lead in q:
            self.current_idx = q.index(lead)
            self._show_view("call")
            self._refresh()
        else:
            messagebox.showinfo("Info",
                f"Status: {STATUS.get(lead['status'],{}).get('label','')}\n"
                "Nicht in der Anruf-Warteschlange.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    LeadMachine().run()
