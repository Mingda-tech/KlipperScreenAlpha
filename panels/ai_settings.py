import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.menu = ['ai_settings_menu']
        self.settings = {}
        
        # 获取AI相关的配置选项
        options = []
        for option in self._config.get_configurable_options():
            name = list(option)[0]
            if name.startswith('ai_'):
                options.append(option)

        # 创建滚动窗口
        self.labels['ai_settings_menu'] = self._gtk.ScrolledWindow()
        self.labels['settings'] = Gtk.Grid()
        self.labels['ai_settings_menu'].add(self.labels['settings'])

        # 添加所有AI相关选项
        for option in options:
            name = list(option)[0]
            self.add_option('settings', self.settings, name, option[name])

        # 添加说明文本
        description = Gtk.Label()
        description.set_line_wrap(True)
        description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        description.set_markup(_(
            "Configure AI service settings here. The AI service can monitor your prints "
            "and detect potential issues. You can adjust the confidence threshold and "
            "choose whether to automatically pause prints when issues are detected."
        ))
        description.set_halign(Gtk.Align.START)
        description.set_valign(Gtk.Align.CENTER)
        description.get_style_context().add_class("temperature_entry")

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)
        main.set_hexpand(True)
        main.pack_start(description, False, False, 5)
        main.pack_start(self.labels['ai_settings_menu'], True, True, 0)

        self.content.add(main)

    def add_option(self, boxname, opt_array, opt_name, option):
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
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            dev.add(scale)

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()

    def process_update(self, action, data):
        if action != "notify_status_update":
            return 