"""Execução das ações dos botões. Qualquer falha levanta ActionError com mensagem legível."""

import ctypes
import subprocess
import time
import webbrowser
from ctypes import wintypes
from urllib.parse import urlparse

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
shell32.ShellExecuteW.restype = ctypes.c_void_p
shell32.ShellExecuteW.argtypes = [
    wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int,
]

CREATE_NO_WINDOW = 0x08000000
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
VK_MENU = 0x12


class ActionError(Exception):
    pass


def run(button: dict) -> None:
    kind = button.get("type", "none")
    target = (button.get("target") or "").strip()
    extra = (button.get("extra") or "").strip()
    handler = _HANDLERS.get(kind)
    if handler is None:
        raise ActionError(f"Tipo de ação desconhecido: {kind!r}.")
    handler(target, extra)


# ---- abrir programa / ficheiro ---------------------------------------------------

def _shell_open(target: str, args: str = "") -> None:
    result = shell32.ShellExecuteW(None, "open", target, args or None, None, 1)
    if (result or 0) <= 32:
        raise ActionError(f"Não foi possível abrir «{target}» (código {result or 0}). Verifica o caminho.")


def _program(target, extra):
    if not target:
        raise ActionError("Indica o programa ou ficheiro a abrir.")
    _shell_open(target, extra)


# ---- URL -------------------------------------------------------------------------

def _url(target, extra):
    if not target:
        raise ActionError("Indica o URL a abrir.")
    if "://" not in target and not target.startswith("mailto:"):
        target = "https://" + target
    parsed = urlparse(target)
    if parsed.scheme not in ("http", "https", "mailto") or (parsed.scheme != "mailto" and not parsed.netloc):
        raise ActionError(f"URL inválido: «{target}». Usa http:// ou https://.")
    if not webbrowser.open(target):
        raise ActionError("Não foi possível abrir o navegador.")


# ---- comando ---------------------------------------------------------------------

def _command(target, extra):
    if not target:
        raise ActionError("Indica o comando a executar.")
    try:
        subprocess.Popen(target, shell=True, creationflags=CREATE_NO_WINDOW)
    except OSError as e:
        raise ActionError(f"Falha ao executar o comando: {e}") from e


# ---- atalho de teclado -----------------------------------------------------------

_MODIFIERS = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "windows": 0x5B}
_NAMED = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C, "mute": 0xAD, "volumedown": 0xAE, "volumeup": 0xAF,
    "nexttrack": 0xB0, "prevtrack": 0xB1, "playpause": 0xB3,
}
_EXTENDED = {0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x5B, 0x2C}


def _vk(name: str) -> int:
    if name in _MODIFIERS:
        return _MODIFIERS[name]
    if name in _NAMED:
        return _NAMED[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x70 + int(name[1:]) - 1
    raise ActionError(f"Tecla desconhecida no atalho: «{name}».")


def _key_event(vk: int, up: bool) -> None:
    flags = (KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED else 0) | (KEYEVENTF_KEYUP if up else 0)
    user32.keybd_event(vk, 0, flags, 0)


def _hotkey(target, extra):
    if not target:
        raise ActionError("Indica o atalho (ex: ctrl+shift+m).")
    names = [p.strip().lower() for p in target.split("+") if p.strip()]
    if not names:
        raise ActionError("Atalho vazio.")
    keys = [_vk(n) for n in names]  # valida tudo antes de enviar
    for vk in keys:
        _key_event(vk, up=False)
    for vk in reversed(keys):
        _key_event(vk, up=True)


# ---- abrir ou focar --------------------------------------------------------------

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _find_window(title: str):
    needle = title.lower()
    found = []

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if needle in buf.value.lower():
                    found.append(hwnd)
                    return False
        return True

    user32.EnumWindows(_WNDENUMPROC(callback), 0)
    return found[0] if found else None


def _focus(target, extra):
    if not extra:
        raise ActionError("Indica parte do título da janela a procurar.")
    hwnd = _find_window(extra)
    if hwnd:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        # Um toque em ALT permite ao Windows aceitar o SetForegroundWindow.
        _key_event(VK_MENU, up=False)
        _key_event(VK_MENU, up=True)
        time.sleep(0.02)
        user32.SetForegroundWindow(hwnd)
        return
    if not target:
        raise ActionError(f"Janela com «{extra}» no título não encontrada e não há programa para abrir.")
    _shell_open(target)


_HANDLERS = {
    "none": lambda t, e: (_ for _ in ()).throw(ActionError("Este botão não tem ação configurada.")),
    "program": _program,
    "url": _url,
    "command": _command,
    "hotkey": _hotkey,
    "focus": _focus,
}
