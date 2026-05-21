#!/usr/bin/env python3
"""Leadmachine — Lead-Dashboard für Google-Places-CSV-Dateien"""

import os
import sys
import csv
import json
import re
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

# ── Datenpfad ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _app_dir = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(sys.executable))))
    DATA_FILE = os.path.join(_app_dir, "leads.json")
else:
    DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")

# ── Farbpalette ───────────────────────────────────────────────────────────────
BG       = "#0a0a0c"
SIDEBAR  = "#0c0c0f"
CARD     = "#141417"
CARD_HI  = "#1b1b20"
BORDER   = "#26262c"
TEXT     = "#f4f4f6"
SUBTLE   = "#a2a2ac"
MUTED    = "#6c6c78"
FAINT    = "#4a4a54"
ACCENT   = "#3b82f6"
ACCENT_H = "#2f6fd6"

STATUS = {
    "pending":            {"label": "Offen",          "bg": CARD,      "bd": BORDER,    "fg": SUBTLE},
    "nicht_erreicht":     {"label": "Nicht erreicht", "bg": "#241c08", "bd": "#4d3c12", "fg": "#e0a526"},
    "interessiert":       {"label": "Interessiert",   "bg": "#0e1729", "bd": "#23426c", "fg": "#5b9bf3"},
    "rueckruf":           {"label": "Rückruf",        "bg": "#1a1030", "bd": "#3d2a5c", "fg": "#b07ae8"},
    "nicht_interessiert": {"label": "Kein Interesse", "bg": "#251010", "bd": "#4d2222", "fg": "#ef6b6b"},
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
        self.leads = []
        self.current_idx = 0
        self.view = "call"
        self._current_lead = None
        self._last_action = None
        self.nav = {}
        self._load()
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

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"leads": self.leads}, f, ensure_ascii=False, indent=2)

    # ── UI-Aufbau ────────────────────────────────────────────────────────────

    def _build(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title("Leadmachine")
        self.root.geometry("1340x850")
        self.root.minsize(1180, 760)
        self.root.configure(fg_color=BG)

        self.f_logo    = ctk.CTkFont("SF Pro Display", 17, "bold")
        self.f_h1      = ctk.CTkFont("SF Pro Display", 23, "bold")
        self.f_sub     = ctk.CTkFont("SF Pro Text", 13)
        self.f_section = ctk.CTkFont("SF Pro Display", 15, "bold")
        self.f_micro   = ctk.CTkFont("SF Pro Text", 11)
        self.f_label   = ctk.CTkFont("SF Pro Text", 10, "bold")
        self.f_kpi     = ctk.CTkFont("SF Pro Display", 25, "bold")
        self.f_company = ctk.CTkFont("SF Pro Display", 25, "bold")
        self.f_body    = ctk.CTkFont("SF Pro Text", 13)
        self.f_bodyb   = ctk.CTkFont("SF Pro Text", 13, "bold")
        self.f_nav     = ctk.CTkFont("SF Pro Text", 13)
        self.f_btn     = ctk.CTkFont("SF Pro Display", 13, "bold")
        self.f_small   = ctk.CTkFont("SF Pro Text", 12)

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

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
        self._nav_item(sb, "call", "Anrufen",     lambda: self._show_view("call"))
        self._nav_item(sb, "list", "Alle Leads",  lambda: self._show_view("list"))
        self._nav_section(sb, "DATEN")
        self._nav_item(sb, "import", "CSV importieren", self._import_csv, toggle=False)

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

    # ── Main-Bereich ─────────────────────────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Topbar
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

        # View-Container
        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 0))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.call_view = ctk.CTkFrame(self.content, fg_color="transparent")
        self.list_view = ctk.CTkFrame(self.content, fg_color="transparent")
        self._build_call_view()
        self._build_list_view()

        # Statusbar
        self.statusbar_var = tk.StringVar(value="")
        sb_bar = ctk.CTkFrame(main, fg_color="transparent", height=26)
        sb_bar.grid(row=2, column=0, sticky="ew", padx=28, pady=(4, 10))
        ctk.CTkLabel(sb_bar, textvariable=self.statusbar_var, font=self.f_micro,
                     text_color=FAINT).pack(side="left")

    def _show_view(self, view):
        self.view = view
        self.call_view.grid_forget()
        self.list_view.grid_forget()
        if view == "call":
            self.call_view.grid(row=0, column=0, sticky="nsew")
            self.title_lbl.configure(text="Anrufen")
            self._set_nav_active("call")
        else:
            self.list_view.grid(row=0, column=0, sticky="nsew")
            self.title_lbl.configure(text="Alle Leads")
            self._set_nav_active("list")
            self._refresh_list()

    # ── Call-View ────────────────────────────────────────────────────────────

    def _build_call_view(self):
        v = self.call_view
        v.grid_columnconfigure(0, weight=3, uniform="c")
        v.grid_columnconfigure(1, weight=2, uniform="c")
        v.grid_rowconfigure(1, weight=1)

        kpis = ctk.CTkFrame(v, fg_color="transparent")
        kpis.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.kpi_vars = {}
        defs = [
            ("gesamt",       "Leads gesamt", "#1a2740", "#5b9bf3", "≡"),
            ("offen",        "Offen",        "#2a2410", "#e0a526", "○"),
            ("interessiert", "Interessiert", "#11243d", "#5b9bf3", "◆"),
            ("kunde",        "Kunden",       "#0e2417", "#52c878", "✓"),
        ]
        for i, (key, label, tint, fg, glyph) in enumerate(defs):
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

        # Kopf: Position + Versuch-Zähler + Status-Pille
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x")
        self.lead_pos = ctk.CTkLabel(head, text="", font=self.f_label, text_color=MUTED)
        self.lead_pos.pack(side="left")
        self.status_pill = ctk.CTkLabel(head, text="  Offen  ", font=self.f_label,
                                        text_color=SUBTLE, fg_color=CARD_HI,
                                        corner_radius=11, height=22)
        self.status_pill.pack(side="right")

        # Firmenname + Rating
        self.title_var = tk.StringVar()
        ctk.CTkLabel(body, textvariable=self.title_var, font=self.f_company,
                     text_color=TEXT, anchor="w", justify="left",
                     wraplength=560).pack(fill="x", pady=(10, 2))
        self.rating_var = tk.StringVar()
        ctk.CTkLabel(body, textvariable=self.rating_var, font=self.f_body,
                     text_color="#e0a526", anchor="w").pack(fill="x")

        # Detail-Grid
        detail = ctk.CTkFrame(body, fg_color=BG, corner_radius=12,
                              border_width=1, border_color=BORDER)
        detail.pack(fill="x", pady=(16, 0))
        grid = ctk.CTkFrame(detail, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=14)
        self.phone_var    = tk.StringVar()
        self.address_var  = tk.StringVar()
        self.website_var  = tk.StringVar()
        self.category_var = tk.StringVar()
        self._detail_row(grid, 0, "TELEFON", self.phone_var,   ACCENT, self._copy_phone)
        self._detail_row(grid, 1, "ADRESSE", self.address_var, TEXT,   None)
        self._detail_row(grid, 2, "WEBSITE", self.website_var, ACCENT, self._open_website)
        self._detail_row(grid, 3, "BRANCHE", self.category_var, TEXT,  None)

        # Sekundäraktionen: Maps · Überspringen · Bearbeiten · Löschen
        sec = ctk.CTkFrame(body, fg_color="transparent")
        sec.pack(fill="x", pady=(14, 0))
        _ghost = dict(fg_color=CARD_HI, hover_color=BORDER, corner_radius=9,
                      height=36, border_width=1, border_color=BORDER, font=self.f_btn)
        ctk.CTkButton(sec, text="Google Maps", command=self._open_maps,
                      text_color=SUBTLE, width=120, **_ghost).pack(side="left")
        ctk.CTkButton(sec, text="Überspringen", command=self._skip,
                      text_color=MUTED, width=120, **_ghost).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sec, text="Bearbeiten", command=self._edit_lead,
                      text_color=ACCENT, width=110, **_ghost).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sec, text="Löschen", command=self._delete_current,
                      fg_color="#1a0808", hover_color="#4d2020", text_color="#ef6b6b",
                      corner_radius=9, height=36, border_width=1, border_color="#4d2020",
                      font=self.f_btn, width=90).pack(side="right")

        # Notizen
        ctk.CTkLabel(body, text="NOTIZEN", font=self.f_label, text_color=MUTED,
                     anchor="w").pack(fill="x", pady=(16, 5))
        self.notes_text = ctk.CTkTextbox(body, height=52, font=self.f_body,
                                         fg_color=BG, text_color=TEXT,
                                         corner_radius=10, border_width=1,
                                         border_color=BORDER, wrap="word")
        self.notes_text.pack(fill="x")

        # Status-Aktionen
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(14, 0))
        order = ["nicht_erreicht", "interessiert", "rueckruf", "nicht_interessiert", "kunde"]
        f_action = ctk.CTkFont("SF Pro Display", 12, "bold")
        for i, st in enumerate(order):
            actions.grid_columnconfigure(i, weight=1)
            cfg = STATUS[st]
            ctk.CTkButton(actions, text=cfg["label"], font=f_action,
                          command=lambda s=st: self._set_status(s),
                          fg_color=cfg["bg"], hover_color=cfg["bd"],
                          text_color=cfg["fg"], border_width=1, border_color=cfg["bd"],
                          corner_radius=10, height=46).grid(
                              row=0, column=i, sticky="nsew",
                              padx=(0 if i == 0 else 6, 0))

        # Tastaturkürzel-Hinweis
        ctk.CTkLabel(body,
                     text="[1] Nicht err.  [2] Interessiert  [3] Rückruf  "
                          "[4] Kein Interesse  [5] Kunde   "
                          "Leertaste: Überspringen   Entf: Löschen   ⌘Z: Rückgängig",
                     font=ctk.CTkFont(size=10), text_color=FAINT,
                     anchor="w", wraplength=700).pack(fill="x", pady=(6, 0))

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
        for st in ["pending","nicht_erreicht","interessiert","rueckruf","nicht_interessiert","kunde"]:
            cfg = STATUS[st]
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=7)
            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x")
            dot = ctk.CTkFrame(hdr, width=9, height=9, corner_radius=5, fg_color=cfg["fg"])
            dot.pack(side="left", pady=2)
            dot.pack_propagate(False)
            ctk.CTkLabel(hdr, text=cfg["label"], font=self.f_body, text_color=SUBTLE).pack(
                side="left", padx=8)
            cnt = tk.StringVar(value="0")
            ctk.CTkLabel(hdr, textvariable=cnt, font=self.f_bodyb, text_color=TEXT).pack(side="right")
            bar = ctk.CTkProgressBar(row, height=6, corner_radius=3,
                                     fg_color=CARD_HI, progress_color=cfg["fg"])
            bar.pack(fill="x", pady=(6, 0))
            bar.set(0)
            self.pipe[st] = (cnt, bar)

        ctk.CTkFrame(body, fg_color=BORDER, height=1).pack(fill="x", pady=(16, 14))
        ctk.CTkLabel(body, text="GESAMTFORTSCHRITT", font=self.f_label,
                     text_color=MUTED, anchor="w").pack(fill="x")
        self.pipe_total = ctk.CTkLabel(body, text="0 %", font=self.f_h1,
                                       text_color=TEXT, anchor="w")
        self.pipe_total.pack(fill="x", pady=(2, 8))
        self.pipe_bar = ctk.CTkProgressBar(body, height=8, corner_radius=4,
                                           fg_color=CARD_HI, progress_color=ACCENT)
        self.pipe_bar.pack(fill="x")
        self.pipe_bar.set(0)
        self.pipe_hint = ctk.CTkLabel(body, text="", font=self.f_micro,
                                      text_color=MUTED, anchor="w")
        self.pipe_hint.pack(fill="x", pady=(8, 0))

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

        # Rechte Buttons
        _rbtn = dict(font=self.f_btn, corner_radius=8, height=34, border_width=1)
        ctk.CTkButton(bar, text="CSV exportieren", command=self._export_csv,
                      fg_color=CARD_HI, hover_color=BORDER, text_color=SUBTLE,
                      border_color=BORDER, width=130, **_rbtn).pack(side="right", padx=(8, 0))
        ctk.CTkButton(bar, text="Löschen", command=self._delete_selected,
                      fg_color="#1a0808", hover_color="#4d2020", text_color="#ef6b6b",
                      border_color="#4d2020", width=90, **_rbtn).pack(side="right")

        self.list_count = ctk.CTkLabel(bar, text="", font=self.f_small, text_color=MUTED)
        self.list_count.pack(side="right", padx=(0, 16))

        # Tabelle
        wrap = tk.Frame(card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("LM.Treeview", background=CARD, foreground=SUBTLE,
                        fieldbackground=CARD, rowheight=34, borderwidth=0,
                        font=("SF Pro Text", 12))
        style.configure("LM.Treeview.Heading", background=BG, foreground=MUTED,
                        font=("SF Pro Text", 10, "bold"), relief="flat",
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
        pending  = [l for l in self.leads if l["status"] == "pending"]
        rueckruf = [l for l in self.leads if l["status"] == "rueckruf"]
        retry    = [l for l in self.leads if l["status"] == "nicht_erreicht"]
        return pending + rueckruf + retry

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
            s = l.get("status", "pending")
            counts[s] = counts.get(s, 0) + 1
        total = len(self.leads)
        self.kpi_vars["gesamt"].set(str(total))
        self.kpi_vars["offen"].set(str(counts["pending"]))
        self.kpi_vars["interessiert"].set(str(counts["interessiert"]))
        self.kpi_vars["kunde"].set(str(counts["kunde"]))
        mx = max(counts.values()) if any(counts.values()) else 1
        for st, (cnt, bar) in self.pipe.items():
            cnt.set(str(counts[st]))
            bar.set(counts[st] / mx)
        offen = counts["pending"] + counts["nicht_erreicht"] + counts["rueckruf"]
        done = total - offen
        frac = (done / total) if total else 0
        self.sb_prog.set(frac)
        self.sb_prog_lbl.configure(text=f"{done} / {total}")
        self.pipe_bar.set(frac)
        self.pipe_total.configure(text=f"{int(frac*100)} %")
        self.pipe_hint.configure(text=f"{done} bearbeitet · {offen} offen")

    def _show_lead(self, lead):
        q = self._callable()
        idx = q.index(lead) + 1 if lead in q else "?"
        attempts = lead.get("attempts", 0)
        pos = f"LEAD {idx} VON {len(q)}"
        if attempts > 0:
            pos += f"  ·  {attempts + 1}. Versuch"
        self.lead_pos.configure(text=pos)

        cfg = STATUS.get(lead["status"], STATUS["pending"])
        self.status_pill.configure(text=f"  {cfg['label']}  ",
                                   fg_color=cfg["bg"], text_color=cfg["fg"])
        self.title_var.set(lead.get("title") or "—")
        rating = lead.get("rating", "")
        reviews = lead.get("reviews", "")
        if rating:
            try:
                r = int(round(float(rating)))
                stars = "★" * r + "☆" * (5 - r)
            except ValueError:
                stars = ""
            self.rating_var.set(f"{stars}   {rating}  ·  {reviews} Bewertungen")
        else:
            self.rating_var.set("☆☆☆☆☆   Keine Bewertung")
        self.phone_var.set(lead.get("phone") or "—")
        parts = [lead.get("street", ""), lead.get("city", "")]
        self.address_var.set(", ".join(p for p in parts if p) or "—")
        self.website_var.set(lead.get("website") or "—")
        self.category_var.set(lead.get("category") or "—")
        self.notes_text.delete("1.0", "end")
        if lead.get("notes"):
            self.notes_text.insert("1.0", lead["notes"])
        self._current_lead = lead

    def _show_empty(self):
        self.lead_pos.configure(text="")
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
        self.notes_text.delete("1.0", "end")
        self._current_lead = None

    def _save_notes(self):
        if self._current_lead:
            self._current_lead["notes"] = self.notes_text.get("1.0", "end").strip()

    def _set_status(self, status):
        if not self._current_lead:
            return
        self._save_notes()
        self._last_action = {
            "lead_id":      self._current_lead["id"],
            "prev_status":  self._current_lead["status"],
            "prev_notes":   self._current_lead.get("notes", ""),
            "prev_attempts":self._current_lead.get("attempts", 0),
            "prev_called":  self._current_lead.get("called_at"),
        }
        if status == "nicht_erreicht":
            self._current_lead["attempts"] = self._current_lead.get("attempts", 0) + 1
        self._current_lead["status"] = status
        self._current_lead["called_at"] = datetime.now().isoformat()
        self._save()
        self.current_idx = 0
        self._refresh()
        self.statusbar_var.set(
            f"Status gesetzt: {STATUS[status]['label']}   ·   ⌘Z zum Rückgängigmachen")

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
        if not messagebox.askyesno(
                "Lead löschen",
                f"'{name}' wirklich löschen?\nDieser Vorgang kann nicht rückgängig gemacht werden."):
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
        if len(sel) == 1:
            lead = next((l for l in self.leads if l["id"] == sel[0]), None)
            name = lead.get("title", "?") if lead else "?"
            msg = f"'{name}' wirklich löschen?"
        else:
            msg = f"{len(sel)} Leads wirklich löschen?"
        if not messagebox.askyesno("Löschen",
                msg + "\nDieser Vorgang kann nicht rückgängig gemacht werden."):
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

        fields = [("Firma", "title"), ("Telefon", "phone"),
                  ("Website", "website"), ("Branche", "category")]
        entries = {}
        for label, key in fields:
            row = ctk.CTkFrame(win, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(row, text=label.upper(), font=self.f_label,
                         text_color=MUTED).pack(anchor="w")
            var = tk.StringVar(value=lead.get(key, ""))
            ctk.CTkEntry(row, textvariable=var, font=self.f_body, fg_color=CARD,
                         text_color=TEXT, corner_radius=8, border_color=BORDER,
                         height=36).pack(fill="x", pady=(3, 0))
            entries[key] = var

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 0))

        def _save():
            for key, var in entries.items():
                lead[key] = var.get().strip()
            lead["phone_normalized"] = normalize_phone(lead.get("phone", ""))
            self._save()
            self._refresh()
            win.destroy()
            self.statusbar_var.set(f"'{lead.get('title', '')}' aktualisiert")

        ctk.CTkButton(btn_row, text="Speichern", command=_save, font=self.f_btn,
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
            messagebox.showinfo("Export", "Keine Leads zum Exportieren (Filter prüfen).")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Alle Dateien", "*.*")],
            initialfile="leads_export.csv")
        if not path:
            return
        status_labels = {k: v["label"] for k, v in STATUS.items()}
        fields = ["title", "phone", "city", "street", "website",
                  "category", "rating", "reviews", "status", "attempts", "notes"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for l in visible:
                row = {k: l.get(k, "") for k in fields}
                row["status"] = status_labels.get(l.get("status", ""), l.get("status", ""))
                writer.writerow(row)
        self.statusbar_var.set(
            f"{len(visible)} Leads exportiert → {os.path.basename(path)}")

    # ── CSV Import ───────────────────────────────────────────────────────────

    def _import_csv(self):
        paths = filedialog.askopenfilenames(
            title="CSV-Dateien auswählen",
            filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")])
        if not paths:
            return
        existing = {l["phone_normalized"] for l in self.leads if l.get("phone_normalized")}
        added = duplicates = skipped = 0
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        phone_raw  = row.get("phone", "").strip()
                        phone_norm = normalize_phone(phone_raw)
                        if phone_norm and phone_norm in existing:
                            duplicates += 1
                            continue
                        title = row.get("title", "").strip()
                        if not title:
                            skipped += 1
                            continue
                        cats = [row.get(f"categories/{i}", "").strip()
                                for i in range(10)
                                if row.get(f"categories/{i}", "").strip()]
                        self.leads.append({
                            "id": f"{datetime.now().isoformat()}_{len(self.leads)+added}",
                            "title": title, "phone": phone_raw,
                            "phone_normalized": phone_norm,
                            "street":   row.get("street",     "").strip(),
                            "city":     row.get("city",        "").strip(),
                            "website":  row.get("website",     "").strip(),
                            "rating":   row.get("totalScore",  "").strip(),
                            "reviews":  row.get("reviewsCount","").strip(),
                            "category": row.get("categoryName","").strip()
                                        or (cats[0] if cats else ""),
                            "maps_url": row.get("url",         "").strip(),
                            "status": "pending", "notes": "", "attempts": 0,
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
        order = ["nicht_erreicht","interessiert","rueckruf","nicht_interessiert","kunde"]

        def _in_text(widget):
            return isinstance(widget, (tk.Text, tk.Entry))

        def on_key(event):
            if _in_text(event.widget):
                return
            if self.view != "call":
                return
            key = event.keysym
            if key in ("1","2","3","4","5"):
                self._set_status(order[int(key)-1])
            elif key == "space":
                self._skip()

        def on_delete(event):
            if _in_text(event.widget):
                return
            if self.view == "call":
                self._delete_current()

        self.root.bind("<Key>",       on_key)
        self.root.bind("<Delete>",    on_delete)
        self.root.bind("<Command-z>", lambda e: self._undo())
        self.root.bind("<Command-Z>", lambda e: self._undo())

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
            stars    = f"★ {rating}" if rating else "—"
            attempts = lead.get("attempts", 0)
            cfg      = STATUS.get(lead["status"], {})
            self.tree.insert("", "end", iid=lead["id"], tags=(lead["status"],),
                             values=(lead.get("title",""), lead.get("phone",""),
                                     lead.get("city",""), lead.get("category",""),
                                     stars, str(attempts) if attempts else "—",
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
            messagebox.showinfo(
                "Info",
                f"Status: {STATUS.get(lead['status'],{}).get('label','')}\n"
                "Nicht in der Anruf-Warteschlange.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    LeadMachine().run()
