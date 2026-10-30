"""Garante uma só instância da app (a porta da placa e as hotkeys só podem ter um dono)."""

import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.SetEvent.argtypes = [wintypes.HANDLE]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str = "ClickDeck"):
        self._mutex = kernel32.CreateMutexW(None, False, f"{name}.SingleInstance")
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        self._show = kernel32.CreateEventW(None, False, False, f"{name}.Show")   # reposto sozinho

    def ask_existing_to_show(self) -> None:
        kernel32.SetEvent(self._show)

    def show_requested(self) -> bool:
        return kernel32.WaitForSingleObject(self._show, 0) == 0
