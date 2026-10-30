"""ClickDeck - ponto de entrada. Uso: python main.py [--hidden]"""

import os
import queue
import sys
import threading
import customtkinter as ctk

from clickdeck import actions, autostart, config, foreground
from clickdeck.gui import ConfigWindow
from clickdeck.leds import LedController
from clickdeck.singleton import SingleInstance
from clickdeck.listener import Listener, port_labels
from clickdeck.tray import Tray


class App:
    def __init__(self, root: ctk.CTk, hidden: bool, instance: SingleInstance = None):
        self.root = root
        self.instance = instance
        self.events = queue.Queue()
        self.cfg, warning = config.load()
        self.cfg["autostart"] = autostart.is_enabled()

        self.listener = Listener(
            on_button=lambda n: self.events.put(("press", n)),
            on_status=lambda text: self.events.put(("listener_status", text)),
        )
        self.leds = LedController(on_status=lambda text: self.events.put(("led_status", text)))
        self.win = ConfigWindow(
            root, self.cfg, port_labels(),
            on_change=self.save, on_test=self.test, on_simulate=self.simulate,
        )
        self.tray = Tray(on_show=lambda: self.events.put(("show", None)),
                         on_quit=lambda: self.events.put(("quit", None)))
        self.tray.start()
        self.leds.start()
        self.leds.apply(self.cfg)

        root.protocol("WM_DELETE_WINDOW", root.withdraw)  # fechar = ficar na bandeja
        self.listener.start(self.cfg["mode"], self.cfg["serial_port"])
        self.win.set_listener_status("a iniciar…")
        if warning:
            self.win.set_status(warning, error=True)
        if hidden:
            root.withdraw()
        self._ticks = 0
        root.after(100, self.poll)

    # ---- execução de ações -----------------------------------------------------

    def _execute(self, n: int, button: dict, popup_errors: bool, profile: str = "") -> None:
        where = f"Botão {n}" + (f" ({profile})" if profile else "")
        def worker():
            try:
                actions.run(button)
            except actions.ActionError as e:
                self.events.put(("error", (f"{where}: {e}", popup_errors)))
            except Exception as e:  # nunca deixar uma ação inesperada matar a app
                self.events.put(("error", (f"{where}: erro inesperado ({e}).", popup_errors)))
            else:
                self.events.put(("status", f"{where}: executado."))
        threading.Thread(target=worker, daemon=True).start()

    def test(self, n: int, button: dict) -> None:
        self._execute(n, button, popup_errors=True)

    def simulate(self, n: int) -> None:
        """Duplo clique: usa o perfil que está aberto na janela."""
        profiles, idx = self.win.profiles, self.win.profile_index
        self._execute(n, config.resolve(profiles, idx, n), popup_errors=False, profile=profiles[idx]["name"])

    def _press(self, n: int) -> None:
        """Botão físico: usa o perfil da app que está à frente (ou o aberto na janela, se for o ClickDeck)."""
        pid, exe, title = foreground.foreground()
        if pid == os.getpid():
            profiles, idx = self.win.profiles, self.win.profile_index
        else:
            profiles = self.cfg["profiles"]
            idx = foreground.pick_profile(profiles, exe, title)
        self._execute(n, config.resolve(profiles, idx, n), popup_errors=False, profile=profiles[idx]["name"])

    def _update_active_profile(self) -> None:
        pid, exe, title = foreground.foreground()
        if pid and pid != os.getpid():
            profiles = self.cfg["profiles"]
            self.win.set_active_profile(profiles[foreground.pick_profile(profiles, exe, title)]["name"])

    # ---- guardar ---------------------------------------------------------------

    def save(self, new_cfg: dict) -> None:
        errors = []
        try:
            config.save(new_cfg)
        except OSError as e:
            self.win.set_status(f"Não foi possível guardar a configuração: {e}", error=True)
            return
        try:
            autostart.set_enabled(new_cfg["autostart"])
        except OSError as e:
            errors.append(f"Iniciar com o Windows não foi alterado ({e}).")
            new_cfg["autostart"] = autostart.is_enabled()
        restart = (new_cfg["mode"], new_cfg["serial_port"]) != (self.cfg["mode"], self.cfg["serial_port"])
        self.cfg = new_cfg
        self.leds.apply(new_cfg)
        if restart:
            self.listener.start(new_cfg["mode"], new_cfg["serial_port"])
        self.win.set_status(" ".join(["Guardado ✓"] + errors), error=bool(errors))

    # ---- eventos vindos de outras threads ---------------------------------------

    def poll(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "press":
                    self.win.flash(data)
                    self._press(data)
                elif kind == "listener_status":
                    self.win.set_listener_status(data)
                elif kind == "led_status":
                    self.win.set_led_status(data)
                elif kind == "status":
                    self.win.set_status(data)
                elif kind == "error":
                    text, popup = data
                    self.win.set_status(text, error=True)
                    if popup:
                        self.win.show_error(text)
                    elif self.root.state() == "withdrawn":
                        self.tray.notify(text)
                elif kind == "show":
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self._ticks += 1
        if self.instance and self.instance.show_requested():
            self.events.put(("show", None))
        if self._ticks % 5 == 0:
            self._update_active_profile()
        self.root.after(100, self.poll)

    def quit(self) -> None:
        self.listener.stop()
        self.leds.stop()
        self.tray.stop()
        self.root.destroy()


def main() -> None:
    instance = SingleInstance()
    if instance.already_running:        # já há um ClickDeck aberto: mostra essa janela e sai
        instance.ask_existing_to_show()
        return
    root = ctk.CTk()
    App(root, hidden="--hidden" in sys.argv, instance=instance)
    root.mainloop()


if __name__ == "__main__":
    main()
