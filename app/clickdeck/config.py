"""Configuração em JSON (%APPDATA%\\ClickDeck\\config.json)."""

import copy
import ctypes
import json
import os
import re
import shutil
import time
from pathlib import Path

APP_NAME = "ClickDeck"
NUM_BUTTONS = 8  # 8 botões = F13–F20 e pinos D2–D9 (para 6: F13–F18 e D2–D7, mudar também no firmware)

MODES = {
    "hid": f"Teclado HID (F13–F{12 + NUM_BUTTONS})",
    "serial": "Série (COM)",
    "sim": "Simulação (sem hardware)",
}

# tipo -> (nome, rótulo do campo 1, rótulo do campo 2 ou None)
ACTION_TYPES = {
    "none": ("(sem ação)", None, None),
    "program": ("Abrir programa ou ficheiro", "Caminho", "Argumentos"),
    "url": ("Abrir URL", "URL", None),
    "command": ("Executar comando", "Comando", None),
    "hotkey": ("Enviar atalho de teclado", "Atalho — vários separados por «;», espera em segundos a seguir à vírgula\nex: ctrl+alt+shift+m,0.5; ctrl+alt+shift+n", None),
    "click": ("Clicar na janela", "Cliques (x,y desde o canto da janela)", None),
    "focus": ("Abrir ou focar app", "Programa a abrir", "Título da janela ou nome do .exe"),
}


# Cores das capas (nome, hex). A cor guardada pode também ser qualquer #rrggbb personalizado.
PALETTE = [
    ("Laranja", "#ff7850"), ("Amarelo", "#ffbe46"), ("Verde", "#6ed278"), ("Azul", "#50b4f0"),
    ("Roxo", "#9682fa"), ("Rosa", "#f06eb4"), ("Turquesa", "#2dd4bf"), ("Vermelho", "#ef4444"),
    ("Branco", "#e5e7eb"), ("Cinzento", "#9ca3af"), ("Preto", "#2b2f3a"),
]
COLORS = [hex_ for _, hex_ in PALETTE]
COLOR_NAMES = {hex_: name for name, hex_ in PALETTE}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


MAX_PROFILES = 12

LED_MODES = {
    "keys": "Cores das teclas",
    "custom": "Cores personalizadas",
    "solid": "Cor única",
    "rainbow": "Arco-íris",
    "breathe": "Respirar",
    "off": "Desligadas",
}
LED_COUNT = 8
DEFAULT_LEDS = {"mode": "keys", "brightness": 40, "color": "#ffffff", "reactive": True,
                "colors": [COLORS[i % len(COLORS)] for i in range(LED_COUNT)]}


def empty_button():
    return {"type": "none", "target": "", "extra": "", "label": ""}


def empty_profile(name, match=""):
    return {"name": name, "match": match, "buttons": [empty_button() for _ in range(NUM_BUTTONS)]}


def _default_profile():
    profile = empty_profile("Geral")
    profile["buttons"][0] = {"type": "url", "target": "https://claude.ai/new", "extra": "", "label": "Claude"}
    profile["buttons"][1] = {"type": "program", "target": "calc.exe", "extra": "", "label": "Calculadora"}
    return profile


DEFAULT_CONFIG = {
    "mode": "hid",
    "serial_port": "auto",
    "autostart": False,
    # a cor é da capa física, por isso é a mesma em todos os perfis
    "colors": [COLORS[i % len(COLORS)] for i in range(NUM_BUTTONS)],
    "leds": copy.deepcopy(DEFAULT_LEDS),
    "profiles": [_default_profile()],
}


def resolve(profiles: list, index: int, n: int) -> dict:
    """Ação da tecla n (1..) no perfil `index`; uma tecla vazia herda a do perfil Geral."""
    button = profiles[index]["buttons"][n - 1]
    if button["type"] == "none" and index != 0:
        return profiles[0]["buttons"][n - 1]
    return button


def config_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / APP_NAME / "config.json"


def normalize(raw) -> dict:
    """Junta a config lida com os valores por omissão, descartando valores inválidos."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(raw, dict):
        raise ValueError("o ficheiro não contém um objeto JSON")
    if raw.get("mode") in MODES:
        cfg["mode"] = raw["mode"]
    if isinstance(raw.get("serial_port"), str) and raw["serial_port"].strip():
        cfg["serial_port"] = raw["serial_port"].strip()
    cfg["autostart"] = bool(raw.get("autostart", False))
    colors = list(cfg["colors"])
    profiles = raw.get("profiles")
    if not isinstance(profiles, list):  # formato antigo: uma só lista de botões (com a cor dentro)
        old = raw.get("buttons")
        profiles = [{"name": "Geral", "buttons": old}] if isinstance(old, list) else []
        for i, b in enumerate(old if isinstance(old, list) else []):
            if i < NUM_BUTTONS and isinstance(b, dict) and isinstance(b.get("color"), str) and _HEX.match(b["color"]):
                colors[i] = b["color"].lower()
    if isinstance(raw.get("colors"), list):
        for i, c in enumerate(raw["colors"][:NUM_BUTTONS]):
            if isinstance(c, str) and _HEX.match(c):
                colors[i] = c.lower()
    cfg["colors"] = colors

    raw_leds = raw.get("leds") if isinstance(raw.get("leds"), dict) else {}
    leds = dict(DEFAULT_LEDS)
    if raw_leds.get("mode") in LED_MODES:
        leds["mode"] = raw_leds["mode"]
    if isinstance(raw_leds.get("brightness"), (int, float)) and not isinstance(raw_leds["brightness"], bool):
        leds["brightness"] = max(0, min(100, int(raw_leds["brightness"])))
    if isinstance(raw_leds.get("color"), str) and _HEX.match(raw_leds["color"]):
        leds["color"] = raw_leds["color"].lower()
    leds["reactive"] = bool(raw_leds.get("reactive", True))
    leds["colors"] = list(DEFAULT_LEDS["colors"])
    if isinstance(raw_leds.get("colors"), list):
        for i, c in enumerate(raw_leds["colors"][:LED_COUNT]):
            if isinstance(c, str) and _HEX.match(c):
                leds["colors"][i] = c.lower()
    cfg["leds"] = leds

    result = []
    for n, p in enumerate(profiles[:MAX_PROFILES]):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name", "")).strip()[:30] or ("Geral" if n == 0 else f"Perfil {n + 1}")
        prof = empty_profile(name, "" if n == 0 else str(p.get("match", "")).strip())
        buttons = p.get("buttons")
        for i in range(NUM_BUTTONS):
            if isinstance(buttons, list) and i < len(buttons) and isinstance(buttons[i], dict):
                b = buttons[i]
                prof["buttons"][i] = {
                    "type": b.get("type") if b.get("type") in ACTION_TYPES else "none",
                    "target": str(b.get("target", "")),
                    "extra": str(b.get("extra", "")),
                    "label": str(b.get("label", ""))[:24],
                }
        result.append(prof)
    if result:
        cfg["profiles"] = result
    return cfg


def load():
    """Devolve (config, aviso). Nunca levanta exceção: ficheiro estragado -> backup + defaults."""
    path = config_path()
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG), None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return normalize(json.load(f)), None
    except (OSError, ValueError) as e:
        warning = f"Configuração inválida ({e}); foram usados os valores por omissão."
        try:
            path.replace(path.with_suffix(".json.bak"))
            warning += " O ficheiro antigo ficou em config.json.bak."
        except OSError:
            pass
        return copy.deepcopy(DEFAULT_CONFIG), warning


BACKUP_EVERY = 600      # segundos entre cópias de segurança
BACKUP_KEEP = 30


def _backup(path: Path, force: bool = False) -> None:
    """Guarda a versão anterior em ClickDeck\backups (no máximo uma de 10 em 10 minutos, as últimas 30)."""
    if not path.exists():
        return
    folder = path.parent / "backups"
    try:
        folder.mkdir(exist_ok=True)
        old = sorted(folder.glob("config-*.json"))
        if old and not force and time.time() - old[-1].stat().st_mtime < BACKUP_EVERY:
            return
        shutil.copy2(path, folder / time.strftime("config-%Y%m%d-%H%M%S.json"))
        for stale in sorted(folder.glob("config-*.json"))[:-BACKUP_KEEP]:
            stale.unlink()
    except OSError:
        pass                                    # a cópia é um extra: nunca impede de gravar


def backup_now() -> None:
    """Cópia de segurança imediata da configuração atual (antes de importar outra)."""
    _backup(config_path(), force=True)


def documents_dir() -> Path:
    """Pasta Documentos do utilizador (segue o redirecionamento do OneDrive, se houver)."""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # CSIDL_PERSONAL
            return Path(buf.value)
    except (OSError, AttributeError):
        pass
    return Path.home() / "Documents"


EXPORT_KEYS = ("mode", "colors", "leds", "profiles")        # a porta COM e o arranque são de cada PC


def export_config(cfg: dict, path) -> None:
    data = {"clickdeck_config": 1, "config": {k: cfg[k] for k in EXPORT_KEYS}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def import_config(path) -> dict:
    """Lê um ficheiro exportado. Levanta ValueError se não for uma configuração do ClickDeck."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f"Não consegui ler o ficheiro ({e}).") from e
    if isinstance(raw, dict) and isinstance(raw.get("config"), dict):
        raw = raw["config"]
    if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), list) or not raw["profiles"]:
        raise ValueError("Este ficheiro não é uma configuração do ClickDeck.")
    return normalize(raw)


def save(cfg: dict) -> None:
    """Grava a config (levanta OSError se não conseguir)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())                    # garante que está no disco antes de trocar o ficheiro
    tmp.replace(path)
