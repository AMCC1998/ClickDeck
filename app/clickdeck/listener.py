"""Captação dos botões: hotkeys globais (HID), porta série ou simulação.

O Listener só chama on_button(n) (n = 1..6) e on_status(texto). Ambos são chamados
a partir de threads de fundo, por isso quem os recebe deve passar o trabalho para a sua thread.
"""

import ctypes
import threading
from ctypes import wintypes

from .config import NUM_BUTTONS

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
VK_F13 = 0x7C

BAUD = 9600
RECONNECT_SECONDS = 2.0


class Listener:
    def __init__(self, on_button, on_status):
        self._on_button = on_button
        self._on_status = on_status
        self._thread = None
        self._stop = threading.Event()
        self._tid = None

    def start(self, mode: str, serial_port: str = "auto") -> None:
        self.stop()
        self._stop.clear()
        if mode == "hid":
            target = self._run_hid
        elif mode == "serial":
            target = lambda: self._run_serial(serial_port)  # noqa: E731
        else:
            self._on_status("Modo simulação: usa os botões «Simular» da janela.")
            return
        self._thread = threading.Thread(target=target, name="clickdeck-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)
        self._thread = None
        self._tid = None

    # ---- HID: RegisterHotKey, não precisa de administrador ---------------------

    def _run_hid(self) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        failed = []
        for i in range(NUM_BUTTONS):
            if not user32.RegisterHotKey(None, i + 1, MOD_NOREPEAT, VK_F13 + i):
                failed.append(f"F{13 + i}")
        if len(failed) == NUM_BUTTONS:
            self._on_status(f"Não foi possível registar F13–F{12 + NUM_BUTTONS} (outra app já as usa?).")
            return
        if failed:
            self._on_status("À escuta, mas já em uso por outra app: " + ", ".join(failed))
        else:
            self._on_status(f"À escuta de F13–F{12 + NUM_BUTTONS} (HID).")
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and 1 <= msg.wParam <= NUM_BUTTONS:
                    self._on_button(int(msg.wParam))
        finally:
            for i in range(NUM_BUTTONS):
                user32.UnregisterHotKey(None, i + 1)

    # ---- Série: pyserial com reconexão -----------------------------------------

    def _run_serial(self, configured_port: str) -> None:
        try:
            import serial
            from serial.tools import list_ports
        except ImportError:
            self._on_status("Falta o pyserial: pip install pyserial")
            return

        last_status = None

        def status(text):
            nonlocal last_status
            if text != last_status:  # evita repetir a mesma mensagem a cada tentativa
                last_status = text
                self._on_status(text)

        while not self._stop.is_set():
            port = configured_port if configured_port.lower() != "auto" else _detect_port(list_ports)
            if not port:
                status("Nenhuma porta COM encontrada. A tentar de novo…")
                self._stop.wait(RECONNECT_SECONDS)
                continue
            try:
                with serial.Serial(port, BAUD, timeout=0.5) as ser:
                    status(f"Ligado em {port}.")
                    while not self._stop.is_set():
                        line = ser.readline().decode("ascii", errors="ignore").strip()
                        if len(line) == 2 and line[0] == "D" and line[1].isdigit():
                            n = int(line[1])
                            if 1 <= n <= NUM_BUTTONS:
                                self._on_button(n)
            except (serial.SerialException, OSError) as e:
                status(f"Porta {port} indisponível ({_short(e)}). A tentar de novo…")
                self._stop.wait(RECONNECT_SECONDS)


def _short(err) -> str:
    return str(err).splitlines()[0][:80]


def _detect_port(list_ports):
    ports = list(list_ports.comports())
    for p in ports:
        text = f"{p.description} {p.manufacturer or ''}".lower()
        if p.vid in (0x2341, 0x2A03, 0x1B4F, 0x1A86, 0x0403) or any(
            k in text for k in ("arduino", "ch340", "usb serial", "sparkfun")
        ):
            return p.device
    return ports[0].device if len(ports) == 1 else None


def port_labels():
    """Portas COM como «COM11 · Arduino Micro», para o seletor da janela."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [f"{p.device} · {p.description.split(' (COM')[0]}" for p in list_ports.comports()]


def available_ports():
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except ImportError:
        return []
