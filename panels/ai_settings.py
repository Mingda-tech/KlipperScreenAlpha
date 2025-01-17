import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.menu = ['ai_settings_menu']
        
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

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        
        # 如果有任何状态更新需要处理，在这里添加代码 