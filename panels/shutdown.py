import logging
import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)

        scroll = self._gtk.ScrolledWindow()

        self.content.add(scroll)
    def poweroff(self):
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label(label=_("Are you sure you wish to shutdown the system?"))
        vbox.add(label)
        scroll.add(vbox)
        buttons = [
            {"name": _("Reboot"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Poweroff"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        title = _("Shutdown")
        self._gtk.Dialog(title, buttons, scroll, self.poweroff_confirm)

    def poweroff_confirm(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        self._screen._menu_go_back()
        if response_id == Gtk.ResponseType.OK:
            os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.APPLY:
            os.system("systemctl reboot -i")

    def activate(self):
        self.poweroff()