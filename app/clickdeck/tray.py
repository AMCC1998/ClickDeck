"""Ícone na bandeja do sistema."""

import pystray
from .icon import make_icon


class Tray:
    def __init__(self, on_show, on_quit):
        menu = pystray.Menu(
            pystray.MenuItem("Abrir configuração", lambda icon, item: on_show(), default=True),
            pystray.MenuItem("Sair", lambda icon, item: on_quit()),
        )
        self._icon = pystray.Icon("ClickDeck", make_icon(64), "ClickDeck", menu)

    def start(self) -> None:
        self._icon.run_detached()

    def notify(self, message: str) -> None:
        try:
            self._icon.notify(message, "ClickDeck")
        except Exception:
            pass  # notificações são acessórias

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass
