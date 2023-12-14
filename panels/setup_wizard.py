import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.printers = self.settings = self.langs = {}
        options = self._config.get_configurable_options().copy()
        options.append({"lang": {
            "name": _("Language"),
            "type": "menu",
            "menu": "lang"
        }})


        grid = self._gtk.HomogeneousGrid()

        self.labels['skip'] = self._gtk.Button(None, "Skip All", "color1", .66)
        self.labels['skip'].connect("clicked", self.on_skip_click)
        grid.attach(self.labels['skip'], 0, 0, 1, 1)

        self.labels['tip'] = Gtk.Label()
        self.labels['tip'].set_text("Choose a language")
        grid.attach(self.labels['tip'], 1, 0, 3, 1)

        self.labels['next'] = self._gtk.Button("arrow-right", None, "color1", .66)
        self.labels['next'].connect("clicked", self.on_next_click)
        grid.attach(self.labels['next'], 4, 0, 1, 1)
        # self.labels['next'].set_sensitive(False)
        
        self.labels['lang_menu'] = self._gtk.ScrolledWindow()
        self.labels['lang'] = Gtk.Grid()
        self.labels['lang_menu'].add(self.labels['lang'])
        language_dict = {
            'ps': 'Pashto',
            'es': 'Español',
            'en': 'English',
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
            'it': 'Italiano',
            'ja': '日本語',
            'sw': 'Kiswahili',
            'ms': 'Bahasa Melayu',
            'nl': 'Nederlands',
            'mi': 'Te Reo Māori',
            'ur': 'پاکستان',
            'fil': 'Filipino ',
            'pl': 'Polski',
            'ru': 'Русский',
            'zu': 'isiZulu',
            'ko': '한국어',
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
            self.langs[lang] = {
                "name": language_dict[lang],
                "type": "lang",
                "code": lang,
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        grid.attach(self.labels['lang_menu'], 0, 1, 5, 5)
        self.content.add(grid)

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
            # select.connect("clicked", self._screen.change_language, option['code'])
            select.connect("clicked", self.change_language, option['name'], option['code'])
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

    def on_next_click(self, widget=None):
        self._screen.setup_init = 2
        self._screen.save_init_step()
        self._screen.show_panel("select_timezone", "Choose Timezone", remove_all=True)
        
    def change_language(self, widget, lang_name, lang_code):
        self.labels['tip'].set_markup(f"Current language: {lang_name}")
        self._screen.change_language_without_reload(widget, lang_code)
        # self.labels['next'].set_sensitive(True)
    
    def on_skip_click(self, widget):
        self._screen.show_panel("main_menu", None, remove_all=True, items=self._config.get_menu_items("__main"))       