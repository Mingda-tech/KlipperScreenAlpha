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
        
        # 获取AI相关的配置选项，只显示服务开关和阈值设置
        options = self._config.get_ai_options()
        filtered_options = []
        for option in options:
            name = list(option)[0]
            if name in ['ai_service', 'ai_confidence_threshold']:
                filtered_options.append(option)

        # 创建主滚动窗口
        self.labels['ai_settings_menu'] = self._gtk.ScrolledWindow()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)

        # 添加说明文本
        description = Gtk.Label()
        description.set_line_wrap(True)
        description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        description.set_markup(_(
            "Configure basic AI service settings. Enable the AI service to monitor your prints "
            "and adjust the confidence threshold for detection sensitivity."
        ))
        description.set_halign(Gtk.Align.START)
        description.set_valign(Gtk.Align.CENTER)
        description.get_style_context().add_class("temperature_entry")
        main_box.pack_start(description, False, False, 0)

        # 创建设置网格
        self.labels['settings'] = Gtk.Grid()
        main_box.pack_start(self.labels['settings'], False, False, 0)

        # 只添加过滤后的AI选项（服务开关和阈值）
        for option in filtered_options:
            name = list(option)[0]
            self.add_option('settings', self.settings, name, option[name])

        self.labels['ai_settings_menu'].add(main_box)
        self.content.add(self.labels['ai_settings_menu'])


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
            switch.connect("notify::active", self.on_setting_changed, option['section'], opt_name,
                           option['callback'] if "callback" in option else None)
            dev.add(switch)
            
            # 保存AI服务开关的引用
            if opt_name == "ai_service":
                self.ai_service_switch = switch
                
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.on_scale_changed, option['section'], opt_name)
            dev.add(scale)
            
            # 保存阈值滑块的引用
            if opt_name == "ai_confidence_threshold":
                self.threshold_scale = scale
                # 根据AI服务状态设置初始启用状态和样式
                ai_service_enabled = self._config.get_config().getboolean('main', 'ai_service', fallback=False)
                scale.set_sensitive(ai_service_enabled)
                
                # 设置初始CSS样式类
                style_context = scale.get_style_context()
                if ai_service_enabled:
                    style_context.add_class("enabled")
                else:
                    style_context.add_class("disabled")

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()

    def on_setting_changed(self, switch, active, section, option, callback=None):
        self.switch_config_option(switch, active, section, option, callback)
        
        # 当AI服务开关变化时，更新阈值滑块的启用状态和样式
        if option == "ai_service" and hasattr(self, 'threshold_scale'):
            is_enabled = switch.get_active()
            self.threshold_scale.set_sensitive(is_enabled)
            
            # 更新CSS样式类
            style_context = self.threshold_scale.get_style_context()
            if is_enabled:
                style_context.remove_class("disabled")
                style_context.add_class("enabled")
            else:
                style_context.remove_class("enabled")
                style_context.add_class("disabled")

    def on_scale_changed(self, widget, event, section, option):
        self.scale_moved(widget, event, section, option)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return