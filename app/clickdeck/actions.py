"""Execução das ações dos botões. Qualquer falha levanta ActionError com mensagem legível."""

import ctypes
import os
import re
import subprocess
import time
import webbrowser
from ctypes import wintypes
from urllib.parse import urlparse

from . import foreground

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


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


user32.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [_POINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]

VK_LBUTTON = 0x01
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
GA_ROOT = 2


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
    """Um ou mais atalhos separados por «;» (ex: «ctrl+alt+shift+m; ctrl+alt+shift+t»); «w300» espera 300 ms."""
    if not target:
        raise ActionError("Indica o atalho (ex: ctrl+shift+m).")
    steps = []
    for part in re.split(r"[;,]", target):
        part = part.strip().lower()
        if not part:
            continue
        if re.fullmatch(r"w\s*\d+", part):
            steps.append(int(part[1:]) / 1000)
        else:
            steps.append([_vk(n.strip()) for n in part.split("+") if n.strip()])  # valida tudo antes de enviar
    if not steps:
        raise ActionError("Atalho vazio.")
    for i, step in enumerate(steps):
        if isinstance(step, float):
            time.sleep(step)
            continue
        for vk in step:
            _key_event(vk, up=False)
        for vk in reversed(step):
            _key_event(vk, up=True)
        if i < len(steps) - 1 and not isinstance(steps[i + 1], float):
            time.sleep(0.15)


# ---- cliques numa janela ----------------------------------------------------------
# Sequência em texto, passos separados por «;»:
#   x,y        clique esquerdo em x,y desde o canto da janela
#   R x,y      o mesmo com o botão direito (L = esquerdo, é o por omissão)
#   @dx,dy     posição relativa ao clique anterior (para menus que abrem junto ao cursor)
#   w300       espera 300 ms
# Ex: «R 812,455; @34,88» = clique direito e depois no item do menu que aparece.

VK_RBUTTON = 0x02
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
STEP_PAUSE = 0.25
_STEP = re.compile(r"(?:(?P<btn>[LR])\s+)?(?P<rel>@)?\s*(?P<x>-?\d+)\s*,\s*(?P<y>-?\d+)", re.IGNORECASE)


def mouse_buttons() -> tuple:
    """(esquerdo premido, direito premido)."""
    return (bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000),
            bool(user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000))


def left_button_down() -> bool:
    return mouse_buttons()[0]


def cursor_info():
    """(pid, janela, (x, y) no ecrã, (x, y) desde o canto da janela) da janela sob o cursor, ou None."""
    pt = _POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    hwnd = user32.WindowFromPoint(pt)
    hwnd = user32.GetAncestor(hwnd, GA_ROOT) if hwnd else None
    if not hwnd:
        return None
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value, hwnd, (pt.x, pt.y), (pt.x - rect.left, pt.y - rect.top)


def _parse_steps(target: str) -> list:
    steps = []
    for raw in target.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        w = re.fullmatch(r"w\s*(\d+)", raw, re.IGNORECASE)
        if w:
            steps.append(("wait", int(w.group(1)) / 1000))
            continue
        m = _STEP.fullmatch(raw)
        if not m:
            raise ActionError(f"Passo inválido: «{raw}». Usa «x,y», «R x,y», «@dx,dy» ou «w300».")
        steps.append(("click", (m["btn"] or "L").upper(), bool(m["rel"]), int(m["x"]), int(m["y"])))
    if not any(s[0] == "click" for s in steps):
        raise ActionError("Grava com 🎯 ou escreve a posição (ex: 120,48).")
    return steps


def _click(target, extra):
    steps = _parse_steps(target)
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise ActionError("Não há nenhuma janela à frente onde clicar.")
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    old = _POINT()
    user32.GetCursorPos(ctypes.byref(old))
    last = (rect.left, rect.top)
    try:
        for n, step in enumerate(steps):
            if step[0] == "wait":
                time.sleep(step[1])
                continue
            _, button, relative, dx, dy = step
            x, y = (last[0] + dx, last[1] + dy) if relative else (rect.left + dx, rect.top + dy)
            if not relative and not (rect.left <= x < rect.right and rect.top <= y < rect.bottom):
                raise ActionError("A posição gravada fica fora da janela (tamanho diferente?). Grava-a de novo.")
            user32.SetCursorPos(x, y)
            time.sleep(0.05)                    # deixa a app ver o cursor por cima do botão
            down, up = ((MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP) if button == "R"
                        else (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))
            user32.mouse_event(down, 0, 0, 0, None)
            time.sleep(0.03)
            user32.mouse_event(up, 0, 0, 0, None)
            last = (x, y)
            if n < len(steps) - 1 and steps[n + 1][0] != "wait":
                time.sleep(STEP_PAUSE)          # tempo para o menu aparecer
    finally:
        time.sleep(0.05)
        user32.SetCursorPos(old.x, old.y)


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
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                exe = os.path.basename(foreground.exe_path(pid.value)).lower()
                if needle in buf.value.lower() or (needle.endswith(".exe") and needle == exe):
                    found.append(hwnd)
                    return False
        return True

    user32.EnumWindows(_WNDENUMPROC(callback), 0)
    return found[0] if found else None


def _focus(target, extra):
    if not extra:
        raise ActionError("Indica parte do título da janela ou o nome do .exe (ex: Fusion360.exe).")
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
    "click": _click,
    "focus": _focus,
}
