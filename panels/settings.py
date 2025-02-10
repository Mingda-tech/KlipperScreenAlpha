import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.printers = self.settings = self.langs = {}
        self.menu = ['settings_menu']
        options = self._config.get_configurable_options().copy()
        # options.append({"printers": {
        #     "name": _("Printer Connections"),
        #     "type": "menu",
        #     "menu": "printers"
        # }})
        options.append({"lang": {
            "name": _("Language"),
            "type": "menu",
            "menu": "lang"
        }})

        self.labels['settings_menu'] = self._gtk.ScrolledWindow()
        self.labels['settings'] = Gtk.Grid()
        self.labels['settings_menu'].add(self.labels['settings'])
        for option in options:
            name = list(option)[0]
            if name == "filament_box_power" and "SET_FILAMENT_BOX_POWER" not in self._printer.get_gcode_macros():
                continue

            if name == "auto_extruder_switch" and not self._screen.check_auto_extruder_switch():
                continue

            script_file = "/home/mingda/printer_data/script/print_end.sh"
            if name == "shutdown_print_end" and ("SHUTDOWN_PRINT_END" not in self._printer.get_gcode_macros() or not os.path.exists(script_file)):
                continue

            script_file = "/home/mingda/printer_data/script/voice_notify.sh"
            if (name == "voice_notify") and ("VOICE_NOTIFY" not in self._printer.get_gcode_macros() or not os.path.exists(script_file)):
                continue

            self.add_option('settings', self.settings, name, option[name])

        self.labels['lang_menu'] = self._gtk.ScrolledWindow()
        self.labels['lang'] = Gtk.Grid()
        self.labels['lang_menu'].add(self.labels['lang'])
        language_dict = {
            'bg': 'Български',
            'ps': 'Pashto',
            'es': 'Español',
            'en': 'English',
            'et': 'Eesti',
            'pt': 'Português',
            'zh': '中文',
            'ar': 'العربية',
            'fr': 'Français',
            'de': 'Deutsch',
            'el': 'Ελληνικά',
            'hi': 'हिन्दी',
            'id': 'Bahasa Indonesia',
            'fa': 'فارسی',
            'ga': 'Gaeilge',
            'gu': 'ગુજરાતી',
            'it': 'Italiano',
            'ja': '日本語',
            'sw': 'Kiswahili',
            'ms': 'Bahasa Melayu',
            'nl': 'Nederlands',
            'mi': 'Te Reo Māori',
            'ur': 'پاکستان',
            'fil': 'Filipino ',
            'pl': 'Polski',
            'pt_BR': 'Português (Brasil)',
            'ru': 'Русский',
            'zu': 'isiZulu',
            'ko': '한국어',
            'sl': 'Slovenščina',
            'sv': 'Svenska',
            'th': 'ไทย',
            'tr': 'Türkçe',
            'vi': 'Tiếng Việt',
            'fi': 'Suomi',
            'no': 'Norsk',
            'cs': 'Čeština',
            'da': 'Dansk',
            'he': 'עברית',
            'hu': 'Magyar',
            'jp': '日本語',
            'uk': 'Українська',
            'zh_CN': '简体中文',
            'zh_TW': '繁體中文',
            'de_formal': 'Deutsch (Formal)',
            'lt': 'lietuvių',
        }        
        for lang in self._config.lang_list:
            if lang not in language_dict:
                continue
            self.langs[lang] = {
                "code": lang,
                "type": "lang",
                "name": language_dict[lang],
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        self.labels['printers_menu'] = self._gtk.ScrolledWindow()
        self.labels['printers'] = Gtk.Grid()
        self.labels['printers_menu'].add(self.labels['printers'])
        for printer in self._config.get_printers():
            pname = list(printer)[0]
            self.printers[pname] = {
                "name": pname,
                "section": f"printer {pname}",
                "type": "printer",
                "moonraker_host": printer[pname]['moonraker_host'],
                "moonraker_port": printer[pname]['moonraker_port'],
            }
            self.add_option("printers", self.printers, pname, self.printers[pname])

        self.content.add(self.labels['settings_menu'])

    def activate(self):
        while len(self.menu) > 1:
            self.unload_menu()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

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
        if option['type'] == "binary":
            switch = Gtk.Switch()
            switch.set_active(self._config.get_config().getboolean(option['section'], opt_name))
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name,
                           option['callback'] if "callback" in option else None)
            dev.add(switch)
        elif option['type'] == "dropdown":
            dropdown = Gtk.ComboBoxText()
            for i, opt in enumerate(option['options']):
                dropdown.append(opt['value'], opt['name'])
                if opt['value'] == self._config.get_config()[option['section']].get(opt_name, option['value']):
                    dropdown.set_active(i)
            dropdown.connect("changed", self.on_dropdown_change, option['section'], opt_name,
                             option['callback'] if "callback" in option else None)
            dropdown.set_entry_text_column(0)
            dev.add(dropdown)
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            dev.add(scale)
        elif option['type'] == "printer":
            box = Gtk.Box()
            box.set_vexpand(False)
            label = Gtk.Label(f"{option['moonraker_host']}:{option['moonraker_port']}")
            box.add(label)
            dev.add(box)
        elif option['type'] == "menu":
            open_menu = self._gtk.Button("settings", style="color3")
            open_menu.connect("clicked", self.load_menu, option['menu'], option['name'])
            open_menu.set_hexpand(False)
            open_menu.set_halign(Gtk.Align.END)
            dev.add(open_menu)
        elif option['type'] == "lang":
            select = self._gtk.Button("load", style="color3")
            select.connect("clicked", self._screen.change_language, option['code'])
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
