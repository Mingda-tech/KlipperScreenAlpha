import logging
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Shutdown")
        super().__init__(screen, title)

        estop = self._gtk.Button("emergency", _("Emergency Stop"), "color2")
        estop.connect("clicked", self.emergency_stop)

        poweroff = self._gtk.Button("shutdown", _("Shutdown"), "color1")
        poweroff.connect("clicked", self.reboot_poweroff, "shutdown")

        restart = self._gtk.Button("refresh", _("Restart"), "color3")
        restart.connect("clicked", self.reboot_poweroff, "reboot")

        restart_ks = self._gtk.Button("refresh", _("Restart") + " Screen", "color3")
        restart_ks.connect("clicked", self._screen.restart_ks)

        self.main = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        if self._printer and self._printer.state not in {'disconnected', 'startup', 'shutdown', 'error'}:
            self.main.attach(estop, 0, 0, 1, 1)
        self.main.attach(restart_ks, 1, 0, 1, 1)
        self.main.attach(poweroff, 0, 1, 1, 1)
        self.main.attach(restart, 1, 1, 1, 1)
        self.content.add(self.main)

    def reboot_poweroff(self, widget, method):
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        if method == "reboot":
            label = Gtk.Label(label=_("Are you sure you wish to reboot the system?"))
        else:
            label = Gtk.Label(label=_("Are you sure you wish to shutdown the system?"))
        vbox.add(label)
        scroll.add(vbox)
        buttons = [
            {"name": _("Confirm"), "response": Gtk.ResponseType.OK},
            # {"name": _("Printer"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        if method == "reboot":
            title = _("Restart")
        else:
            title = _("Shutdown")
        self._gtk.Dialog(title, buttons, scroll, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot -i")
            else:
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self._screen._ws.send_method("machine.shutdown")
