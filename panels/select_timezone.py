import logging
import os
import gi
import netifaces
import subprocess

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    initialized = False

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.timezones = {}

        grid = self._gtk.HomogeneousGrid()
        region = ['Africa', 'America', 'Asia', 'Europe', 'Indian']
        self.labels['region'] = []
        for i, r in enumerate(region):
            i = i + 1
            button = self._gtk.Button(None,  r, "color1")
            button.connect("clicked", self.reload_timezones, r)
            self.labels["region"].append(button)
            grid.attach(button, 0, i, 1, 1)

        self.langs = {}
        
        self.labels['back'] = self._gtk.Button("arrow-left", None, "color1", .66)
        self.labels['back'].connect("clicked", self.on_back_click)
        grid.attach(self.labels['back'], 0, 0, 1, 1)

        self.labels['tip'] = Gtk.Label()
        self.labels['tip'].set_text("Choose a timezone")
        grid.attach(self.labels['tip'], 1, 0, 3, 1)

        self.labels['next'] = self._gtk.Button("arrow-right", None, "color1", .66)
        self.labels['next'].connect("clicked", self.on_next_click)
        # self.labels['next'].set_sensitive(False)
        grid.attach(self.labels['next'], 4, 0, 1, 1)

        timezone_dir = "/usr/share/zoneinfo"
        all_timezones = []
        for root, dirs, files in os.walk(timezone_dir):
            for file in files:
                tz = os.path.relpath(os.path.join(root, file), timezone_dir)
                all_timezones.append(tz)

        for r in region:
            if r not in self.timezones:
                self.timezones[r] = []
        for tz in all_timezones:
            for r in region:
                if tz.startswith(r):
                    self.timezones[r].append(tz)

        self.labels['lang_menu'] = self._gtk.ScrolledWindow()
        self.labels['lang'] = Gtk.Grid()
        self.labels['lang_menu'].add(self.labels['lang'])
        for lang in self.timezones[region[0]]:
            self.langs[lang] = {
                "name": lang,
                "type": "lang",
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        grid.attach(self.labels['lang_menu'], 1, 1, 4, 5)
        self.content.add(grid)
        self.initialized = True


    def on_back_click(self, widget=None):
        self._screen.show_panel("setup_wizard", "Choose Language", remove_all=True)

    def on_next_click(self, widget=None):
        self._screen.setup_init = 3
        self._screen.save_init_step()
        self._screen.show_panel("zcalibrate_mesh", "Leveling", remove_all=True)        

    def change_timezone(self, widget, new_timezone):
        # Command to change the system timezone
        command = f"sudo ln -sf /usr/share/zoneinfo/{new_timezone} /etc/localtime"

        # Execute the command to change the timezone
        try:
            subprocess.run(command, shell=True, check=True)
            self.labels['tip'].set_markup(f"Current timezone: {new_timezone}")
            # self.labels['next'].set_sensitive(True)
            logging.info(f"System timezone set to {new_timezone}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error: {e}")

    def list_timezones(path):
        timezones = []
        for root, dirs, files in os.walk(path):
            for file in files:
                tz = os.path.relpath(os.path.join(root, file), path)
                timezones.append(tz)
        return timezones

    def add_option(self, boxname, opt_array, opt_name, option):
        if option['type'] is None:
            return
        name = Gtk.Label()
        name.set_markup(f"<big><b>{option['name']}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.get_style_context().add_class("frame-item")
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)

        dev.add(labels)        

        if option['type'] == "lang":
            select = self._gtk.Button("load", style="color3")
            select.connect("clicked", self.change_timezone, option['name'])
            select.set_hexpand(False)
            select.set_halign(Gtk.Align.END)
            dev.add(select)        

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()            

    def reload_timezones(self, widget, region_name):
        self.labels['lang'].remove_column(0)
        for lang in self.timezones[region_name]:
            self.langs[lang] = {
                "name": lang,
                "type": "lang",
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])
        