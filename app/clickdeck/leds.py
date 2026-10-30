"""Controlo da barra de LEDs WS2812 ligada à Pro Micro (porta série virtual, linhas de texto)."""

import threading

BAUD = 115200
LED_COUNT = 8
# Só se experimentam portas de placas Arduino/SparkFun para não mexer noutros dispositivos série.
ARDUINO_VIDS = {0x2341, 0x2A03, 0x1B4F}
MODE_CODES = {"off": 0, "keys": 1, "custom": 1, "solid": 2, "rainbow": 3, "breathe": 4}


def build_lines(leds: dict, colors: list) -> list:
    """Estado completo das luzes como comandos para o firmware."""
    lines = [
        f"M{MODE_CODES.get(leds['mode'], 1)}",
        f"B{round(leds['brightness'] * 255 / 100)}",
        f"R{int(bool(leds['reactive']))}",
        f"C{leds['color'][1:]}",
    ]
    source = leds.get("colors", colors) if leds["mode"] == "custom" else colors
    lines += [f"K{i + 1}{c[1:]}" for i, c in enumerate(source[:LED_COUNT])]
    return lines


class LedController:
    def __init__(self, on_status):
        self._on_status = on_status
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._lines = []
        self._enabled = False
        self._dirty = False
        self._port = "auto"
        self._last_status = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="clickdeck-leds", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=3)

    def apply(self, cfg: dict) -> None:
        """Chamar sempre que a config muda: reenvia o estado das luzes."""
        with self._lock:
            self._lines = build_lines(cfg["leds"], cfg["colors"])
            self._enabled = cfg["mode"] != "serial"      # no modo série a porta é usada pelo listener
            self._port = cfg["serial_port"]
            self._dirty = True
        self._wake.set()

    def _status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self._on_status(text)

    # ---- thread ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            import serial
            from serial.tools import list_ports
        except ImportError:
            self._status("Falta o pyserial: pip install pyserial")
            return

        ser = None
        opened_for = None
        beat = 0
        while not self._stop.is_set():
            with self._lock:
                enabled, port, dirty, lines = self._enabled, self._port, self._dirty, list(self._lines)
            if not enabled:
                ser = self._close(ser)
                self._status("Luzes inativas no modo série.")
                self._pause(1.0)
                continue
            if ser is not None and port != opened_for:      # o utilizador escolheu outra porta
                ser = self._close(ser)
            if ser is None:
                ser = self._open(serial, list_ports, port)
                if ser is None:
                    self._pause(3.0)
                    continue
                opened_for = port
                dirty = True
            try:
                if dirty:
                    for line in lines:
                        ser.write((line + "\n").encode("ascii"))
                    with self._lock:
                        if self._lines == lines:
                            self._dirty = False
                else:
                    beat += 1
                    if beat % 2 == 0:                      # bate-papo para detetar o cabo a sair
                        ser.write(b"?\n")
                        ser.reset_input_buffer()
            except (serial.SerialException, OSError):
                ser = self._close(ser)
                self._status("Ligação às luzes perdida. A tentar de novo…")
                continue
            self._pause(1.0)

    def _pause(self, seconds: float) -> None:
        self._wake.wait(seconds)
        self._wake.clear()

    @staticmethod
    def _close(ser):
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        return None

    def _open(self, serial, list_ports, port: str):
        if port.lower() != "auto":
            candidates = [port]
        else:
            candidates = [p.device for p in list_ports.comports() if p.vid in ARDUINO_VIDS]
        if not candidates:
            self._status("Luzes: nenhuma placa Arduino encontrada. Escolhe a porta ao lado.")
            return None
        for dev in candidates:
            try:
                ser = serial.Serial(dev, BAUD, timeout=0.6, write_timeout=1.0)
            except (serial.SerialException, OSError) as e:
                msg = str(e).splitlines()[0][:60]
                self._status(f"Luzes: não consegui abrir {dev} ({msg}). A tentar de novo…")
                continue
            try:
                ser.write(b"?\n")
                if b"CLICKDECK" in ser.readline():
                    self._status(f"Luzes ligadas em {dev}.")
                    return ser
            except (serial.SerialException, OSError):
                pass
            ser.close()
            self._status(f"Luzes: {dev} não respondeu. O firmware tem as luzes? A tentar de novo…")
        return None
