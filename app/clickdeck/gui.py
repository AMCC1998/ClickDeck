"""Janela principal: teclado visual à esquerda, editor da tecla selecionada à direita."""

import copy
import os
import re
import tempfile
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from urllib.parse import urlparse

import customtkinter as ctk

from .icon import save_ico
from . import actions, foreground
from .listener import port_labels
from . import config as cfgmod
from .config import (ACTION_TYPES, COLOR_NAMES, LED_MODES, MAX_PROFILES, MODES, NUM_BUTTONS, PALETTE,
                     empty_profile, resolve)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#14161c"
CARD = "#1f222b"
CARD_HOVER = "#2a2e3a"
FIELD = "#272b36"
MUTED = "#8b90a0"
DARK_TEXT = "#10131a"

ICONS = {"none": "＋", "program": "🚀", "url": "🌐", "command": ">_", "hotkey": "⚡", "click": "🎯", "focus": "🪟"}
SHORT = {"none": "Nenhuma", "program": "Programa", "url": "Site", "command": "Comando",
         "hotkey": "Atalho", "click": "Clicar", "focus": "Abrir/focar"}
PLACEHOLDERS = {
    "program": ("calc.exe ou C:\\...\\programa.exe", "Opcional"),
    "url": ("https://…", ""),
    "command": ("ex: shutdown /l", ""),
    "hotkey": ("ex: ctrl+alt+shift+m,0.5; ctrl+alt+shift+n", ""),
    "click": ("grava com 🎯 ou escreve ex: R 812,455; @34,88", ""),
    "focus": ("C:\\...\\programa.exe (se não estiver aberto)", "ex: Spotify ou Spotify.exe"),
}
SWATCHES_PER_ROW = 6
COLUMNS = 4 if NUM_BUTTONS > 6 else 3
KEY_TAGS = [f"F{13 + i}" for i in range(NUM_BUTTONS)]

_MODE_BY_NAME = {v: k for k, v in MODES.items()}
_LED_BY_NAME = {v: k for k, v in LED_MODES.items()}
_KEYSYMS = {
    "Return": "enter", "Escape": "esc", "BackSpace": "backspace", "Tab": "tab", "space": "space",
    "Delete": "delete", "Insert": "insert", "Home": "home", "End": "end", "Prior": "pageup",
    "Next": "pagedown", "Left": "left", "Right": "right", "Up": "up", "Down": "down",
    "Snapshot": "printscreen",
}
_MODIFIER_KEYSYMS = {"Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Meta_L",
                     "Meta_R", "Super_L", "Super_R", "Caps_Lock", "Num_Lock"}


def _blend(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _on(color: str) -> str:
    """Cor de texto legível sobre `color`."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return DARK_TEXT if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#f3f4f8"


def _summary(b: dict) -> str:
    kind, target = b["type"], b["target"]
    if kind == "none" or not target:
        return "Clica para configurar" if kind == "none" else "Falta preencher"
    if kind == "url":
        return urlparse(target if "://" in target else "https://" + target).netloc or target
    if kind in ("program", "focus"):
        return os.path.basename(target.rstrip("\\/")) or target
    return target


class KeyCap(ctk.CTkFrame):
    SIZE = 170

    def __init__(self, parent, index, on_select, on_run):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, corner_radius=20,
                         fg_color=CARD, border_width=3, border_color=CARD)
        self.pack_propagate(False)
        self.index = index
        self._accent = PALETTE[0][1]
        self._selected = False
        self.tag = ctk.CTkLabel(self, text=f"{index + 1}  ·  {KEY_TAGS[index]}", text_color=MUTED,
                                font=ctk.CTkFont(size=11))
        self.tag.pack(anchor="w", padx=14, pady=(10, 0))
        self.icon = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Segoe UI Emoji", size=36))
        self.icon.pack(pady=(4, 0))
        self.name = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.name.pack(padx=8)
        self.info = ctk.CTkLabel(self, text="", text_color=MUTED, wraplength=140,
                                 font=ctk.CTkFont(size=11))
        self.info.pack(padx=8)
        for w in (self, self.tag, self.icon, self.name, self.info):
            w.bind("<Button-1>", lambda _e: on_select(index))
            w.bind("<Double-Button-1>", lambda _e: on_run(index))
            w.configure(cursor="hand2") if w is self else None

    def update_view(self, data: dict, color: str, selected: bool, inherited: bool = False) -> None:
        self._accent, self._selected = color, selected
        fg = _on(color)
        soft = _blend(fg, color, 0.35)
        self.tag.configure(text=f"{self.index + 1}  ·  {KEY_TAGS[self.index]}" + ("  ·  ↩ Geral" if inherited else ""),
                           text_color=soft)
        self.icon.configure(text=ICONS[data["type"]], text_color=fg)
        self.name.configure(text=data["label"] or SHORT[data["type"]], text_color=fg)
        self.info.configure(text=_summary(data), text_color=soft)
        self.configure(fg_color=color, border_color="#ffffff" if selected else color)

    def flash(self) -> None:
        self.configure(fg_color=_blend(self._accent, "#ffffff", 0.6))
        self.after(220, lambda: self.configure(fg_color=self._accent))


class ConfigWindow:
    def __init__(self, root, cfg, ports, on_change, on_test, on_simulate):
        self.root = root
        self._on_change = on_change
        self._on_test = on_test
        self._on_simulate = on_simulate
        self.profiles = copy.deepcopy(cfg["profiles"])
        self.colors = list(cfg["colors"])
        self.pidx = 0
        self.data = self.profiles[0]["buttons"]
        self.sel = 0
        self._loading = False
        self._recording = False
        self._save_job = None
        self._status_job = None

        root.title("ClickDeck")
        root.geometry(f"{1060 + (COLUMNS - 3) * 184}x800")
        root.minsize(1040 + (COLUMNS - 3) * 184, 760)
        root.configure(fg_color=BG)
        try:  # sem isto o customtkinter põe o ícone dele na barra de título e na barra de tarefas
            ico = os.path.join(tempfile.gettempdir(), "clickdeck-icon.ico")
            save_ico(ico)
            root.iconbitmap(ico)
        except Exception:
            pass

        # --- barra de topo
        top = ctk.CTkFrame(root, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(18, 4))
        ctk.CTkLabel(top, text="ClickDeck", font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        self.pill = ctk.CTkLabel(top, text="●  a iniciar…", fg_color=CARD, corner_radius=14,
                                 text_color=MUTED, padx=14, pady=5, font=ctk.CTkFont(size=12))
        self.pill.pack(side="right")

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=8)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        # --- esquerda: teclado + definições
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(bar, text="Perfil", text_color=MUTED).pack(side="left")
        self.profile_menu = ctk.CTkOptionMenu(bar, values=[p["name"] for p in self.profiles], width=170,
                                              command=self._profile_chosen)
        self.profile_menu.pack(side="left", padx=8)
        for text, cmd in (("＋", self._new_profile), ("✎", self._rename_profile), ("🗑", self._delete_profile)):
            ctk.CTkButton(bar, text=text, width=34, height=28, fg_color=FIELD, hover_color=CARD_HOVER,
                          command=cmd).pack(side="left", padx=2)
        self.active_lbl = ctk.CTkLabel(bar, text="", text_color=MUTED, font=ctk.CTkFont(size=12))
        self.active_lbl.pack(side="right")

        info = ctk.CTkFrame(left, fg_color="transparent")
        info.pack(fill="x", pady=(0, 6))
        self.default_hint = ctk.CTkLabel(info, text="Perfil geral: usado quando nenhum outro perfil se aplica.",
                                         text_color=MUTED, font=ctk.CTkFont(size=12))
        self.match_row = ctk.CTkFrame(info, fg_color="transparent")
        ctk.CTkLabel(self.match_row, text="Ativa quando a janela for", text_color=MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.e_match = ctk.CTkEntry(self.match_row, placeholder_text="ex: Fusion360.exe", width=210, height=30,
                                    fg_color=FIELD, border_width=0)
        self.e_match.pack(side="left", padx=8)
        self.e_match.bind("<KeyRelease>", lambda _e: self._match_edited())
        ctk.CTkButton(self.match_row, text="🎯 Detetar", width=90, height=30, fg_color=FIELD,
                      hover_color=CARD_HOVER, command=self._detect_app).pack(side="left")

        ctk.CTkLabel(left, text="Clica numa tecla para a configurar  ·  duplo clique para a experimentar",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 10))
        pad = ctk.CTkFrame(left, fg_color="transparent")
        pad.pack(anchor="w")
        self.caps = []
        for i in range(NUM_BUTTONS):
            cap = KeyCap(pad, i, self.select, self._on_simulate_index)
            cap.grid(row=i // COLUMNS, column=i % COLUMNS, padx=7, pady=7)
            self.caps.append(cap)

        settings = ctk.CTkFrame(left, fg_color=CARD, corner_radius=14)
        settings.pack(fill="x", pady=(14, 0))
        row = ctk.CTkFrame(settings, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="Modo", text_color=MUTED).pack(side="left")
        self.mode_menu = ctk.CTkOptionMenu(row, values=list(MODES.values()), width=190,
                                           command=lambda _v: self._settings_changed())
        self.mode_menu.set(MODES[cfg["mode"]])
        self.mode_menu.pack(side="left", padx=(8, 12))
        self.autostart = ctk.CTkSwitch(row, text="Iniciar com o Windows",
                                       command=self._settings_changed)
        if cfg["autostart"]:
            self.autostart.select()
        self.autostart.pack(side="right")
        ctk.CTkButton(row, text="⬆ Importar", width=92, height=30, fg_color=FIELD, hover_color=CARD_HOVER,
                      command=self._import).pack(side="right", padx=(0, 18))
        ctk.CTkButton(row, text="⬇ Exportar", width=92, height=30, fg_color=FIELD, hover_color=CARD_HOVER,
                      command=self._export).pack(side="right", padx=(0, 6))

        lights = ctk.CTkFrame(left, fg_color=CARD, corner_radius=14)
        lights.pack(fill="x", pady=(10, 0))
        lrow = ctk.CTkFrame(lights, fg_color="transparent")
        lrow.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(lrow, text="Luzes", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        leds = cfg["leds"]
        self._led_color = leds["color"]
        self.led_menu = ctk.CTkOptionMenu(lrow, values=list(LED_MODES.values()), width=150,
                                          command=lambda _v: self._lights_changed())
        self.led_menu.set(LED_MODES[leds["mode"]])
        self.led_menu.pack(side="left", padx=(10, 12))
        ctk.CTkLabel(lrow, text="Brilho", text_color=MUTED).pack(side="left")
        self.led_bright = ctk.CTkSlider(lrow, from_=0, to=100, width=120,
                                        command=lambda _v: self._lights_changed())
        self.led_bright.set(leds["brightness"])
        self.led_bright.pack(side="left", padx=(8, 12))
        self.led_color_btn = ctk.CTkButton(lrow, text="Cor", width=48, height=28, corner_radius=14,
                                           command=self._pick_led_color)
        self.led_color_btn.pack(side="left")
        self.led_reactive = ctk.CTkSwitch(lrow, text="Acender ao premir", command=self._lights_changed)
        if leds["reactive"]:
            self.led_reactive.select()
        self.led_reactive.pack(side="right")
        self._led_colors = list(leds["colors"])
        self.custom_row = ctk.CTkFrame(lights, fg_color="transparent")
        ctk.CTkLabel(self.custom_row, text="Cor de cada LED", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        self.led_swatches = []
        for i in range(len(self._led_colors)):
            sw = ctk.CTkButton(self.custom_row, text=str(i + 1), width=30, height=30, corner_radius=15,
                               border_width=1, border_color="#3a3f4d", command=lambda i=i: self._pick_led(i))
            sw.pack(side="left", padx=2)
            self.led_swatches.append(sw)

        self.port_row = ctk.CTkFrame(lights, fg_color="transparent")
        self.port_row.pack(fill="x", padx=14, pady=(2, 10))
        ctk.CTkLabel(self.port_row, text="Porta", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
        self.port_box = ctk.CTkComboBox(self.port_row, values=["auto"] + ports, width=210,
                                        command=lambda _v: self._settings_changed())
        saved = cfg["serial_port"]
        self.port_box.set(next((p for p in ports if p.split("·")[0].strip() == saved), saved))
        self.port_box.bind("<KeyRelease>", lambda _e: self._settings_changed())
        self.port_box.pack(side="left", padx=8)
        ctk.CTkButton(self.port_row, text="⟳", width=30, height=28, fg_color=FIELD, hover_color=CARD_HOVER,
                      command=self._rescan_ports).pack(side="left")
        self.led_status = ctk.CTkLabel(self.port_row, text="Luzes: a procurar a placa…", text_color=MUTED,
                                       anchor="w", font=ctk.CTkFont(size=11))
        self.led_status.pack(side="left", padx=10)

        self.message = ctk.CTkLabel(left, text="", anchor="w", justify="left", wraplength=520,
                                    font=ctk.CTkFont(size=12))
        self.message.pack(fill="x", pady=(10, 0))

        # --- direita: editor
        self.editor = ctk.CTkFrame(body, fg_color=CARD, corner_radius=20, width=360)
        self.editor.grid(row=0, column=1, sticky="ns")
        self.editor.pack_propagate(False)
        self._build_editor()

        self._refresh_mode()
        self._refresh_lights()
        self._refresh_profiles()
        self.select(0)

    # ---- editor ---------------------------------------------------------------

    def _build_editor(self):
        ed = self.editor
        self.ed_title = ctk.CTkLabel(ed, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.ed_title.pack(anchor="w", padx=20, pady=(18, 8))

        self.e_name = ctk.CTkEntry(ed, placeholder_text="Nome da tecla (opcional)", fg_color=FIELD,
                                   border_width=0, height=36)
        self.e_name.pack(fill="x", padx=20)
        self.e_name.bind("<KeyRelease>", lambda _e: self._edited())

        head = ctk.CTkFrame(ed, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(12, 6))
        ctk.CTkLabel(head, text="COR DA CAPA", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.color_name = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.color_name.pack(side="right")
        swatches = ctk.CTkFrame(ed, fg_color="transparent")
        swatches.pack(anchor="w", padx=17, pady=(0, 10))
        self.swatches = {}
        for n, (name, c) in enumerate(PALETTE):
            btn = ctk.CTkButton(swatches, text="", width=30, height=30, corner_radius=15, fg_color=c,
                                hover_color=c, border_width=0, command=lambda c=c: self._pick_color(c))
            btn.grid(row=n // SWATCHES_PER_ROW, column=n % SWATCHES_PER_ROW, padx=3, pady=3)
            self.swatches[c] = btn
        self.custom_btn = ctk.CTkButton(swatches, text="＋", width=30, height=30, corner_radius=15,
                                        fg_color=FIELD, hover_color=CARD_HOVER, border_width=0,
                                        command=self._custom_color)
        n = len(PALETTE)
        self.custom_btn.grid(row=n // SWATCHES_PER_ROW, column=n % SWATCHES_PER_ROW, padx=3, pady=3)

        ctk.CTkLabel(ed, text="O QUE FAZ?", text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(anchor="w", padx=20, pady=(4, 6))
        grid = ctk.CTkFrame(ed, fg_color="transparent")
        grid.pack(padx=17)
        self.type_btns = {}
        for n, kind in enumerate(ACTION_TYPES):
            label = "∅  Nenhuma" if kind == "none" else f"{ICONS[kind]}  {SHORT[kind]}"
            b = ctk.CTkButton(grid, text=label, width=104, height=38, corner_radius=10, fg_color=FIELD,
                              hover_color=CARD_HOVER, font=ctk.CTkFont(size=12),
                              command=lambda k=kind: self._pick_type(k))
            b.grid(row=n // 3, column=n % 3, padx=3, pady=3)
            self.type_btns[kind] = b

        self.fields = ctk.CTkFrame(ed, fg_color="transparent")
        self.fields.pack(fill="x", padx=20, pady=(10, 0))
        self.l1 = ctk.CTkLabel(self.fields, text="", text_color=MUTED, font=ctk.CTkFont(size=12),
                               justify="left", anchor="w", wraplength=330)
        self.row1 = ctk.CTkFrame(self.fields, fg_color="transparent")
        self.e1 = ctk.CTkEntry(self.row1, fg_color=FIELD, border_width=0, height=36)
        self.e1.pack(side="left", fill="x", expand=True)
        self.e1.bind("<KeyRelease>", lambda _e: self._edited())
        self.side_btn = ctk.CTkButton(self.row1, text="", width=40, height=36, fg_color=FIELD,
                                      hover_color=CARD_HOVER, command=self._side_action)
        self.detect_btn = ctk.CTkButton(self.row1, text="🎯", width=40, height=36, fg_color=FIELD,
                                        hover_color=CARD_HOVER, command=self._detect_target)
        self.hk_frame = ctk.CTkFrame(self.fields, fg_color="transparent")
        self._hk = [[["", ""]]]            # toques alternativos > passos [atalho, espera em segundos]
        self._rec_entry = None
        self._rec_btn = None
        self.l2 = ctk.CTkLabel(self.fields, text="", text_color=MUTED, font=ctk.CTkFont(size=12))
        self.e2 = ctk.CTkEntry(self.fields, fg_color=FIELD, border_width=0, height=36)
        self.e2.bind("<KeyRelease>", lambda _e: self._edited())

        self.test_btn = ctk.CTkButton(ed, text="▶  Testar", height=42, corner_radius=12,
                                      text_color=DARK_TEXT, font=ctk.CTkFont(size=14, weight="bold"),
                                      command=self._test)
        self.test_btn.pack(side="bottom", fill="x", padx=20, pady=18)
        self.root.bind("<KeyPress>", self._on_keypress, add="+")

    def select(self, index: int) -> None:
        self._stop_recording()
        self.sel = index
        b = self.data[index]
        self._loading = True
        self.ed_title.configure(text=f"Tecla {index + 1}  ·  {KEY_TAGS[index]}")
        self._set_entry(self.e_name, b["label"])
        self._set_entry(self.e1, b["target"])
        self._set_entry(self.e2, b["extra"])
        if b["type"] == "hotkey":
            self._hk_load(b["target"])
        self._loading = False
        self._refresh_editor()
        self._refresh_caps()

    @staticmethod
    def _set_entry(entry, text):
        entry.delete(0, "end")
        entry.insert(0, text)

    def _refresh_caps(self):
        for i, cap in enumerate(self.caps):
            b, inherited = self.data[i], False
            if self.pidx and b["type"] == "none" and self.profiles[0]["buttons"][i]["type"] != "none":
                b, inherited = self.profiles[0]["buttons"][i], True
            cap.update_view(b, self.colors[i], i == self.sel, inherited)

    def _refresh_editor(self):
        b = self.data[self.sel]
        accent = self.colors[self.sel]
        for c, btn in self.swatches.items():
            btn.configure(border_width=3 if c == accent else 1,
                          border_color="#ffffff" if c == accent else "#3a3f4d")
        custom = accent not in self.swatches
        self.custom_btn.configure(fg_color=accent if custom else FIELD, hover_color=accent if custom else CARD_HOVER,
                                  text_color=_on(accent) if custom else "#dfe3ee",
                                  border_width=3 if custom else 0, border_color="#ffffff")
        self.color_name.configure(text=COLOR_NAMES.get(accent, f"Personalizada {accent}"), text_color=accent)
        for kind, btn in self.type_btns.items():
            active = kind == b["type"]
            btn.configure(fg_color=accent if active else FIELD, text_color=_on(accent) if active else "#dfe3ee",
                          hover_color=accent if active else CARD_HOVER)
        self.test_btn.configure(fg_color=accent, text_color=_on(accent),
                                hover_color=_blend(accent, "#ffffff", 0.2))

        for w in (self.l1, self.row1, self.hk_frame, self.l2, self.e2):
            w.pack_forget()
        self.side_btn.pack_forget()
        self.detect_btn.pack_forget()
        _, label1, label2 = ACTION_TYPES[b["type"]]
        ph1, ph2 = PLACEHOLDERS.get(b["type"], ("", ""))
        if label1 and b["type"] == "hotkey":
            self.l1.configure(text=label1)
            self.l1.pack(anchor="w", pady=(0, 4))
            self.hk_frame.pack(fill="x")
        elif label1:
            self.l1.configure(text=label1)
            self.l1.pack(anchor="w", pady=(0, 4))
            self.e1.configure(placeholder_text=ph1)
            self.row1.pack(fill="x")
            if b["type"] in ("program", "focus"):
                self.side_btn.configure(text="📂")
                self.side_btn.pack(side="left", padx=(6, 0))
                if b["type"] == "focus":
                    self.detect_btn.pack(side="left", padx=(6, 0))
            elif b["type"] == "click":
                self.side_btn.configure(text="🎯")
                self.side_btn.pack(side="left", padx=(6, 0))
        if label2:
            self.l2.configure(text=label2)
            self.l2.pack(anchor="w", pady=(10, 4))
            self.e2.configure(placeholder_text=ph2)
            self.e2.pack(fill="x")

    # ---- edições ----------------------------------------------------------------

    def _edited(self):
        if self._loading:
            return
        b = self.data[self.sel]
        b["label"] = self.e_name.get().strip()[:24]
        if b["type"] == "hotkey":
            b["target"] = self._hk_text()
        else:
            b["target"] = self.e1.get().strip() if b["type"] != "none" else ""
        b["extra"] = self.e2.get().strip() if ACTION_TYPES[b["type"]][2] else ""
        self._refresh_caps()
        self._schedule_save()

    def _pick_type(self, kind):
        self._stop_recording()
        self.data[self.sel]["type"] = kind
        if kind == "hotkey":
            self._hk_load(self.e1.get())
        self._edited()
        self._refresh_editor()

    def _pick_color(self, color):
        self.colors[self.sel] = color
        self._refresh_editor()
        self._refresh_caps()
        self._schedule_save()

    def _custom_color(self):
        picked = colorchooser.askcolor(color=self.colors[self.sel], parent=self.root,
                                       title="Cor da capa")[1]
        if picked:
            self._pick_color(picked.lower())

    def _side_action(self):
        kind = self.data[self.sel]["type"]
        if kind == "click":
            self._record_click()
        else:
            path = filedialog.askopenfilename(title="Escolher programa ou ficheiro")
            if path:
                self._set_entry(self.e1, path.replace("/", "\\"))
                self._edited()

    def _record_click(self):
        """Grava os cliques seguintes (esquerdo/direito) até 2,5 s sem clicar. Os cliques passam para a app."""
        self.set_status("Vai à janela do programa e faz os cliques que queres gravar (acaba 2,5 s depois do último).")
        self._rec = {"steps": [], "first": None, "prev": None, "start": time.time(), "last": time.time(),
                     "armed": False, "held": (True, True)}
        self.root.after(20, self._poll_click)

    def _poll_click(self):
        r = self._rec
        now = time.time()
        left, right = actions.mouse_buttons()
        if not left and not right:
            r["armed"] = True                           # só conta depois de largar o clique em «🎯»
            r["hover"] = actions.cursor_info()          # janela sob o cursor antes do clique (um menu pode abrir logo)
        if r["armed"] and (left, right) != r["held"] and (left or right):
            info = r.get("hover") or actions.cursor_info()
            if info and info[0] != os.getpid():
                _pid, hwnd, screen, rel = info
                btn = "R " if right and not left else ""
                if r["first"] is None or hwnd == r["first"]:
                    r["first"] = r["first"] or hwnd
                    r["steps"].append(f"{btn}{rel[0]},{rel[1]}")
                else:                                   # janela nova (menu): relativo ao clique anterior
                    r["steps"].append(f"{btn}@{screen[0] - r['prev'][0]},{screen[1] - r['prev'][1]}")
                r["prev"] = screen
                r["last"] = now
        r["held"] = (left, right)
        if r["steps"] and now - r["last"] > 2.5:
            self._set_entry(self.e1, "; ".join(r["steps"]))
            self._edited()
            self.set_status(f"Gravados {len(r['steps'])} clique(s). Usa «Testar» com a janela à frente.")
            return
        if not r["steps"] and now - r["start"] > 15:
            self.set_status("Não detetei nenhum clique: tenta de novo.", error=True)
            return
        self.root.after(20, self._poll_click)

    def _stop_recording(self):
        if self._recording:
            self._recording = False
            if self._rec_btn is not None:
                try:
                    self._rec_btn.configure(text="⏺", fg_color=FIELD)
                except Exception:
                    pass
            self._rec_btn = self._rec_entry = None

    def _on_keypress(self, event):
        if not self._recording or event.keysym in _MODIFIER_KEYSYMS:
            return None
        if len(event.keysym) == 1 and event.keysym.isalnum():
            key = event.keysym.lower()
        elif event.keysym[:1] == "F" and event.keysym[1:].isdigit():
            key = event.keysym.lower()
        else:
            key = _KEYSYMS.get(event.keysym)
        if key is None:
            self.set_status(f"A tecla «{event.keysym}» não é suportada em atalhos.", error=True)
            return "break"
        mods = [name for bit, name in ((0x4, "ctrl"), (0x20000, "alt"), (0x1, "shift")) if event.state & bit]
        entry = self._rec_entry
        self._stop_recording()
        self._set_entry(entry, "+".join(mods + [key]))
        self.set_status("")
        self._hk_changed()
        return "break"

    # ---- editor de atalhos: toques (alternativas) > passos (atalho + espera) -------------------
    # Fica guardado no mesmo texto de sempre: «a,0.5; b | c» (| separa toques, ; passos, ,s a espera).

    @staticmethod
    def _hk_parse(text: str) -> list:
        alts = []
        for alt in text.split("|"):
            steps = []
            for part in alt.split(";"):
                part = part.strip()
                if not part:
                    continue
                m = re.fullmatch(r"[wW]\s*(\d+)", part)
                if m:                                       # «w300» antigo: passa a espera do passo anterior
                    if steps:
                        total = float(steps[-1][1] or 0) + int(m.group(1)) / 1000
                        steps[-1][1] = f"{total:g}"
                    continue
                combo, _, delay = part.partition(",")
                steps.append([combo.strip(), delay.strip().replace(",", ".")])
            if steps:
                alts.append(steps)
        return alts or [[["", ""]]]

    def _hk_text(self) -> str:
        alts = []
        for steps in self._hk:
            parts = [f"{c},{d}" if d else c for c, d in steps if c]
            if parts:
                alts.append("; ".join(parts))
        return " | ".join(alts)

    def _hk_load(self, text: str) -> None:
        self._hk = self._hk_parse(text)
        self._hk_build()

    def _hk_changed(self) -> None:
        for steps, rows in zip(self._hk, self._hk_rows):
            for step, (e_combo, e_delay) in zip(steps, rows):
                step[0], step[1] = e_combo.get().strip(), e_delay.get().strip().replace(",", ".")
        self._edited()

    def _hk_structure(self, fn) -> None:
        self._stop_recording()
        self._hk_changed()
        fn()
        self._hk_build()
        self._edited()

    def _hk_build(self) -> None:
        for w in self.hk_frame.winfo_children():
            w.destroy()
        self._hk_rows = []
        many = len(self._hk) > 1
        for ai, steps in enumerate(self._hk):
            head = ctk.CTkFrame(self.hk_frame, fg_color="transparent")
            head.pack(fill="x", pady=(0 if ai == 0 else 12, 4))
            ctk.CTkLabel(head, text=f"{ai + 1}.º toque" if many else "Atalhos (em sequência)",
                         text_color="#dfe3ee", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            if many:
                ctk.CTkLabel(head, text="  — cada toque na tecla executa o seguinte, em ciclo",
                             text_color=MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
                ctk.CTkButton(head, text="✕", width=26, height=22, fg_color=FIELD, hover_color=CARD_HOVER,
                              command=lambda a=ai: self._hk_structure(lambda: self._hk.pop(a))).pack(side="right")
            rows = []
            for si, step in enumerate(steps):
                row = ctk.CTkFrame(self.hk_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)
                e_combo = ctk.CTkEntry(row, fg_color=FIELD, border_width=0, height=34,
                                       placeholder_text="ex: ctrl+alt+shift+m")
                e_combo.pack(side="left", fill="x", expand=True)
                e_combo.insert(0, step[0])
                e_combo.bind("<KeyRelease>", lambda _e: self._hk_changed())
                rec = ctk.CTkButton(row, text="⏺", width=34, height=34, fg_color=FIELD, hover_color=CARD_HOVER)
                rec.configure(command=lambda b=rec, e=e_combo: self._hk_record(b, e))
                rec.pack(side="left", padx=(5, 0))
                last = si == len(steps) - 1
                e_delay = ctk.CTkEntry(row, fg_color=FIELD, border_width=0, height=34, width=58,
                                       placeholder_text="0.15" if not last else "—",
                                       state="normal")
                e_delay.pack(side="left", padx=(5, 0))
                e_delay.insert(0, step[1])
                e_delay.bind("<KeyRelease>", lambda _e: self._hk_changed())
                ctk.CTkLabel(row, text="s", text_color=MUTED, width=12).pack(side="left", padx=(3, 0))
                if len(steps) > 1:
                    ctk.CTkButton(row, text="✕", width=26, height=34, fg_color=FIELD, hover_color=CARD_HOVER,
                                  command=lambda a=ai, s=si: self._hk_structure(lambda: self._hk[a].pop(s))
                                  ).pack(side="left", padx=(5, 0))
                rows.append((e_combo, e_delay))
            self._hk_rows.append(rows)
            ctk.CTkButton(self.hk_frame, text="＋ outro atalho (a seguir)", height=26, fg_color="transparent",
                          hover_color=CARD_HOVER, text_color=MUTED, anchor="w", font=ctk.CTkFont(size=12),
                          command=lambda a=ai: self._hk_structure(lambda: self._hk[a].append(["", ""]))
                          ).pack(fill="x", pady=(2, 0))
        ctk.CTkButton(self.hk_frame, text="＋ toque alternativo (alterna a cada toque)", height=28, fg_color=FIELD,
                      hover_color=CARD_HOVER, font=ctk.CTkFont(size=12),
                      command=lambda: self._hk_structure(lambda: self._hk.append([["", ""]]))
                      ).pack(fill="x", pady=(12, 0))

    def _hk_record(self, btn, entry) -> None:
        if self._recording and self._rec_entry is entry:
            self._stop_recording()
            return
        self._stop_recording()
        self._recording = True
        self._rec_entry, self._rec_btn = entry, btn
        btn.configure(text="…", fg_color=self.colors[self.sel])
        self.set_status("Prime o atalho que queres gravar (ex: Ctrl+Shift+M).")
        self.root.focus_set()

    # ---- definições gerais ------------------------------------------------------

    def _refresh_mode(self):
        return  # a porta (auto ou escolhida) serve para as luzes e para o modo série

    def _settings_changed(self):
        self._refresh_mode()
        self._schedule_save(delay=100)

    # ---- exportar / importar ------------------------------------------------------

    def _export(self):
        self.flush_save()
        folder = cfgmod.documents_dir() / "ClickDeck"
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            folder = cfgmod.documents_dir()
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Exportar configuração", initialdir=str(folder),
            initialfile=time.strftime("ClickDeck-config-%Y%m%d.json"), defaultextension=".json",
            filetypes=[("Configuração do ClickDeck", "*.json")])
        if not path:
            return
        try:
            cfgmod.export_config(self.get_config(), path)
        except OSError as e:
            self.set_status(f"Não consegui exportar: {e}", error=True)
            return
        self.set_status(f"Configuração exportada para {path}")

    def _import(self):
        folder = cfgmod.documents_dir() / "ClickDeck"
        path = filedialog.askopenfilename(
            parent=self.root, title="Importar configuração",
            initialdir=str(folder if folder.exists() else cfgmod.documents_dir()),
            filetypes=[("Configuração do ClickDeck", "*.json"), ("Todos os ficheiros", "*.*")])
        if not path:
            return
        try:
            new = cfgmod.import_config(path)
        except ValueError as e:
            self.set_status(str(e), error=True)
            return
        if not messagebox.askyesno(
                "Importar configuração",
                f"Substituir os perfis, teclas, cores e luzes atuais pelos de\n{os.path.basename(path)}?\n\n"
                "A configuração atual fica guardada numa cópia de segurança.", parent=self.root):
            return
        self.flush_save()
        cfgmod.backup_now()
        self.load_config(new)
        self._save_now()
        self.set_status("Configuração importada. Confirma os caminhos dos programas, que podem ser outros neste PC.")

    def load_config(self, cfg: dict) -> None:
        """Substitui perfis, cores e luzes (a porta e o arranque com o Windows mantêm-se)."""
        self._stop_recording()
        self.profiles = copy.deepcopy(cfg["profiles"])
        self.colors = list(cfg["colors"])
        leds = cfg["leds"]
        self._led_color = leds["color"]
        self._led_colors = list(leds["colors"])
        self.led_menu.set(LED_MODES[leds["mode"]])
        self.led_bright.set(leds["brightness"])
        (self.led_reactive.select if leds["reactive"] else self.led_reactive.deselect)()
        self.mode_menu.set(MODES[cfg["mode"]])
        self.pidx = 0
        self.sel = 0
        self.data = self.profiles[0]["buttons"]
        self._refresh_lights()
        self._refresh_profiles()
        self._refresh_caps()
        self.select(0)

    def _port_value(self) -> str:
        text = self.port_box.get().strip()
        return "auto" if not text or text.lower() == "auto" else text.split("·")[0].strip()

    def _rescan_ports(self):
        labels = port_labels()
        self.port_box.configure(values=["auto"] + labels)
        self.set_status(f"{len(labels)} porta(s) COM encontrada(s)" + (": " + ", ".join(labels) if labels else "."))

    def _pick_led(self, i):
        picked = colorchooser.askcolor(color=self._led_colors[i], parent=self.root,
                                       title=f"Cor do LED {i + 1}")[1]
        if picked:
            self._led_colors[i] = picked.lower()
            self._lights_changed()

    def _refresh_lights(self):
        mode = _LED_BY_NAME[self.led_menu.get()]
        solid = mode == "solid"
        if mode == "custom":
            self.custom_row.pack(fill="x", padx=14, pady=(0, 4), before=self.port_row)
        else:
            self.custom_row.pack_forget()
        for sw, c in zip(self.led_swatches, self._led_colors):
            sw.configure(fg_color=c, hover_color=c, text_color=_on(c))
        self.led_color_btn.configure(fg_color=self._led_color, hover_color=self._led_color,
                                     text_color=_on(self._led_color),
                                     state="normal" if solid else "disabled")

    def _lights_changed(self):
        self._refresh_lights()
        self._schedule_save(delay=200)

    def _pick_led_color(self):
        picked = colorchooser.askcolor(color=self._led_color, parent=self.root, title="Cor das luzes")[1]
        if picked:
            self._led_color = picked.lower()
            self._lights_changed()

    def set_led_status(self, text: str) -> None:
        self.led_status.configure(text=text)

    def get_config(self) -> dict:
        return {
            "mode": _MODE_BY_NAME[self.mode_menu.get()],
            "serial_port": self._port_value(),
            "autostart": bool(self.autostart.get()),
            "colors": list(self.colors),
            "leds": {
                "mode": _LED_BY_NAME[self.led_menu.get()],
                "brightness": int(round(self.led_bright.get())),
                "color": self._led_color,
                "colors": list(self._led_colors),
                "reactive": bool(self.led_reactive.get()),
            },
            "profiles": copy.deepcopy(self.profiles),
        }

    def _schedule_save(self, delay=500):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(delay, self._save_now)

    def flush_save(self):
        """Grava já o que estiver pendente (ao fechar, esconder ou sair)."""
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self._save_now()

    def _save_now(self):
        self._save_job = None
        self._on_change(self.get_config())

    # ---- perfis ------------------------------------------------------------------

    @property
    def profile_index(self) -> int:
        return self.pidx

    def _names(self):
        return [p["name"] for p in self.profiles]

    def _unique_name(self, name, ignore=None):
        taken = {p["name"].lower() for i, p in enumerate(self.profiles) if i != ignore}
        base, n = name, 2
        while name.lower() in taken:
            name, n = f"{base} {n}", n + 1
        return name

    def _refresh_profiles(self):
        default = self.pidx == 0
        self.profile_menu.configure(values=self._names())
        self.profile_menu.set(self.profiles[self.pidx]["name"])
        self.match_row.pack_forget()
        self.default_hint.pack_forget()
        if default:
            self.default_hint.pack(anchor="w")
        else:
            self._set_entry(self.e_match, self.profiles[self.pidx]["match"])
            self.match_row.pack(anchor="w")
        self.type_btns["none"].configure(text="∅  Nenhuma" if default else "↩  Do Geral")

    def _switch_profile(self, index):
        self._stop_recording()
        self.pidx = index
        self.data = self.profiles[index]["buttons"]
        self._refresh_profiles()
        self.select(self.sel)

    def _profile_chosen(self, name):
        self._switch_profile(self._names().index(name))

    def _ask_name(self, title):
        name = ctk.CTkInputDialog(text="Nome do perfil (ex: Fusion 360):", title=title).get_input()
        return name.strip()[:30] if name and name.strip() else None

    def _new_profile(self):
        if len(self.profiles) >= MAX_PROFILES:
            self.set_status(f"Máximo de {MAX_PROFILES} perfis.", error=True)
            return
        name = self._ask_name("Novo perfil")
        if name:
            self.profiles.append(empty_profile(self._unique_name(name)))
            self._switch_profile(len(self.profiles) - 1)
            self.set_status("Perfil criado. Usa «Detetar» para dizer em que app fica ativo; "
                            "as teclas vazias usam a ação do Geral.")
            self._schedule_save()

    def _rename_profile(self):
        if self.pidx == 0:
            self.set_status("O perfil Geral não pode ser renomeado.", error=True)
            return
        name = self._ask_name("Renomear perfil")
        if name:
            self.profiles[self.pidx]["name"] = self._unique_name(name, ignore=self.pidx)
            self._refresh_profiles()
            self._schedule_save()

    def _delete_profile(self):
        if self.pidx == 0:
            self.set_status("O perfil Geral não pode ser apagado.", error=True)
            return
        name = self.profiles[self.pidx]["name"]
        if messagebox.askyesno("ClickDeck", f"Apagar o perfil «{name}»?", parent=self.root):
            del self.profiles[self.pidx]
            self._switch_profile(0)
            self._schedule_save()

    def _match_edited(self):
        if self.pidx:
            self.profiles[self.pidx]["match"] = self.e_match.get().strip()
            self._schedule_save()

    def _detect_target(self):
        self.set_status("Muda agora para o programa que queres focar. A detetar daqui a 4 segundos…")
        self.root.after(4000, self._detect_target_done)

    def _detect_target_done(self):
        pid, path, title = foreground.foreground_full()
        if not path or pid == os.getpid():
            self.set_status("Não detetei nenhum programa: muda para ele durante os 4 segundos e tenta de novo.",
                            error=True)
            return
        self._set_entry(self.e1, path)
        self._set_entry(self.e2, os.path.basename(path))
        self._edited()
        self.set_status(f"Detetado: {os.path.basename(path)} ({title[:40]})")

    def _detect_app(self):
        self.set_status("Muda agora para a app que queres (ex: Fusion). A detetar daqui a 4 segundos…")
        self.root.after(4000, self._detect_done)

    def _detect_done(self):
        pid, exe, title = foreground.foreground()
        if not exe or pid == os.getpid():
            self.set_status("Não detetei nenhuma app: muda para ela durante os 4 segundos e tenta de novo.",
                            error=True)
            return
        self._set_entry(self.e_match, exe)
        self._match_edited()
        self.set_status(f"Detetado: {exe} ({title[:40]})")

    # ---- ações da janela ---------------------------------------------------------

    def _test(self):
        self._on_test(self.sel + 1, copy.deepcopy(resolve(self.profiles, self.pidx, self.sel + 1)))

    def _on_simulate_index(self, index):
        self.select(index)
        self._on_simulate(index + 1)

    def flash(self, n: int) -> None:
        self.caps[n - 1].flash()

    # ---- estado -------------------------------------------------------------------

    def set_listener_status(self, text: str) -> None:
        ok = text.startswith(("À escuta", "Ligado", "Modo simulação"))
        self.pill.configure(text=f"●  {text}", text_color="#6ed278" if ok else "#ffbe46")

    def set_active_profile(self, name: str) -> None:
        self.active_lbl.configure(text=f"●  A usar o perfil «{name}»", text_color="#6ed278")

    def set_status(self, text: str, error: bool = False) -> None:
        self.message.configure(text=text, text_color="#ff6b6b" if error else MUTED)
        if self._status_job:
            self.root.after_cancel(self._status_job)
            self._status_job = None
        if text and not error:
            self._status_job = self.root.after(4000, lambda: self.message.configure(text=""))

    def show_error(self, text: str) -> None:
        messagebox.showerror("ClickDeck", text, parent=self.root)
