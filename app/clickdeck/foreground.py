"""Janela ativa do Windows e escolha do perfil que lhe corresponde."""

import ctypes
import os
import re
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def exe_path(pid: int) -> str:
    """Caminho completo do .exe do processo, ou "" se não for possível ler."""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    size = wintypes.DWORD(1040)
    path = ctypes.create_unicode_buffer(1040)
    ok = kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    return path.value if ok else ""


def foreground_full():
    """(pid, caminho completo do .exe, título) da janela ativa. Valores vazios quando não for possível ler."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0, "", ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    length = user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title, length + 1)
    return pid.value, exe_path(pid.value), title.value


def foreground():
    """(pid, nome do .exe, título) da janela ativa. Valores vazios quando não for possível ler."""
    pid, path, title = foreground_full()
    return pid, os.path.basename(path), title


def matches(match: str, exe: str, title: str) -> bool:
    """`match` pode ter várias entradas separadas por ; ou , — basta uma estar no .exe ou no título."""
    exe_l, title_l = exe.lower(), title.lower()
    for token in re.split(r"[;,]", match):
        token = token.strip().lower()
        if token and (token in exe_l or token in title_l):
            return True
    return False


def pick_profile(profiles: list, exe: str, title: str) -> int:
    """Índice do primeiro perfil (a seguir ao Geral) que corresponde à janela; 0 se nenhum."""
    for i in range(1, len(profiles)):
        if matches(profiles[i]["match"], exe, title):
            return i
    return 0
