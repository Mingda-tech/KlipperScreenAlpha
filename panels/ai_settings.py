import gi
import logging
import threading

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GLib

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.menu = ['ai_settings_menu']
        self.settings = {}
        
        # 获取AI相关的配置选项
        options = self._config.get_ai_options()

        # 创建主滚动窗口
        self.labels['ai_settings_menu'] = self._gtk.ScrolledWindow()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)

        # 添加说明文本
        description = Gtk.Label()
        description.set_line_wrap(True)
        description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        description.set_markup(_(
            "Configure AI service settings here. The AI service can monitor your prints "
            "and detect potential issues like spaghetti failures, layer cracks, and warping. "
            "You can adjust the confidence threshold and choose whether to automatically pause "
            "prints when issues are detected."
        ))
        description.set_halign(Gtk.Align.START)
        description.set_valign(Gtk.Align.CENTER)
        description.get_style_context().add_class("temperature_entry")
        main_box.pack_start(description, False, False, 0)

        # 创建设置网格
        self.labels['settings'] = Gtk.Grid()
        main_box.pack_start(self.labels['settings'], False, False, 0)

        # 添加所有AI相关选项
        for option in options:
            name = list(option)[0]
            self.add_option('settings', self.settings, name, option[name])

        # 添加缺陷类型选择
        defect_types_frame = self.create_defect_types_selection()
        main_box.pack_start(defect_types_frame, False, False, 0)

        # 添加连接测试区域
        connection_test_frame = self.create_connection_test_section()
        main_box.pack_start(connection_test_frame, False, False, 0)

        # 添加统计信息区域
        stats_frame = self.create_stats_section()
        main_box.pack_start(stats_frame, False, False, 0)

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
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.on_scale_changed, option['section'], opt_name)
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

    def on_setting_changed(self, switch, active, section, option, callback=None):
        self.switch_config_option(switch, active, section, option, callback)

    def on_scale_changed(self, widget, event, section, option):
        self.scale_moved(widget, event, section, option)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return 
    
    def create_defect_types_selection(self):
        """创建缺陷类型选择界面"""
        frame = Gtk.Frame(label=_("Defect Types"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        
        # 获取当前启用的缺陷类型
        enabled_types = self._config.get_enabled_defect_types()
        
        # 所有可用的缺陷类型
        all_defect_types = [
            ("spaghetti", _("Spaghetti (炒面)")),
            ("head_burst", _("Head Burst (爆头)")),
            ("misalignment", _("Misalignment (错位)")),
            ("layer_crack", _("Layer Crack (层间开裂)")),
            ("warping", _("Warping (翘曲变形)")),
            ("porosity", _("Porosity (孔隙)"))
        ]
        
        self.defect_type_switches = {}
        
        for defect_id, defect_name in all_defect_types:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            
            label = Gtk.Label(defect_name)
            label.set_halign(Gtk.Align.START)
            label.set_hexpand(True)
            
            switch = Gtk.Switch()
            switch.set_active(defect_id in enabled_types)
            switch.connect("notify::active", self.on_defect_type_changed, defect_id)
            
            self.defect_type_switches[defect_id] = switch
            
            row.pack_start(label, True, True, 0)
            row.pack_start(switch, False, False, 0)
            
            box.pack_start(row, False, False, 0)
        
        frame.add(box)
        return frame

    def on_defect_type_changed(self, switch, gparam, defect_id):
        """缺陷类型选择变更处理"""
        current_types = self._config.get_enabled_defect_types()
        
        if switch.get_active():
            if defect_id not in current_types:
                current_types.append(defect_id)
        else:
            if defect_id in current_types:
                current_types.remove(defect_id)
        
        # 更新配置
        types_str = ','.join(current_types)
        self._config.get_config().set('main', 'ai_defect_types', types_str)
        self._config.save_user_config_options()

    def create_connection_test_section(self):
        """创建连接测试区域"""
        frame = Gtk.Frame(label=_("Connection Test"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        
        # 测试按钮
        test_button = self._gtk.Button("refresh", _("Test Connection"), "color2")
        test_button.connect("clicked", self.test_ai_connection)
        
        # 状态显示
        self.connection_status = Gtk.Label(_("Not tested"))
        self.connection_status.set_halign(Gtk.Align.CENTER)
        
        box.pack_start(test_button, False, False, 0)
        box.pack_start(self.connection_status, False, False, 0)
        
        frame.add(box)
        return frame

    def test_ai_connection(self, widget):
        """测试AI服务器连接"""
        def test_worker():
            try:
                # 检查是否有AI管理器
                if hasattr(self._screen, 'ai_manager'):
                    ai_manager = self._screen.ai_manager
                    result = ai_manager.test_connection()
                    
                    if result["server_connection"] and result["camera_connection"]:
                        server_status = result.get("server_status")
                        if server_status and server_status.get("success"):
                            model_count = len(server_status.get("model_status", {}))
                            result_text = _("✅ Connected - {} models loaded").format(model_count)
                            result_class = "success"
                        else:
                            result_text = _("✅ Server connected, camera OK")
                            result_class = "success"
                    elif result["server_connection"]:
                        result_text = _("⚠️ Server OK, camera failed")
                        result_class = "warning"
                    elif result["camera_connection"]:
                        result_text = _("⚠️ Camera OK, server failed")
                        result_class = "warning"
                    else:
                        errors = "; ".join(result["error_messages"])
                        result_text = _("❌ Connection failed: {}").format(errors)
                        result_class = "error"
                else:
                    result_text = _("❌ AI manager not initialized")
                    result_class = "error"
                
                # 更新UI
                GLib.idle_add(self.update_connection_status, result_text, result_class)
                
            except Exception as e:
                error_text = _("❌ Error: {}").format(str(e))
                GLib.idle_add(self.update_connection_status, error_text, "error")
        
        # 显示测试中状态
        self.connection_status.set_text(_("🔄 Testing..."))
        
        # 在后台线程执行测试
        threading.Thread(target=test_worker, daemon=True).start()

    def update_connection_status(self, text, css_class):
        """更新连接状态显示"""
        self.connection_status.set_text(text)
        
        # 清除旧的样式类
        style_context = self.connection_status.get_style_context()
        for old_class in ["success", "warning", "error"]:
            style_context.remove_class(old_class)
        
        # 添加新的样式类
        style_context.add_class(css_class)

    def create_stats_section(self):
        """创建统计信息区域"""
        frame = Gtk.Frame(label=_("Detection Statistics"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        
        # 统计标签
        self.stats_labels = {}
        
        stats_info = [
            ("total_detections", _("Total Detections")),
            ("defect_detections", _("Defect Detections")),
            ("defect_rate", _("Defect Rate")),
            ("avg_inference_time", _("Avg Inference Time")),
        ]
        
        for stat_id, stat_name in stats_info:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            
            label = Gtk.Label(stat_name + ":")
            label.set_halign(Gtk.Align.START)
            label.set_hexpand(True)
            
            value_label = Gtk.Label("N/A")
            value_label.set_halign(Gtk.Align.END)
            
            self.stats_labels[stat_id] = value_label
            
            row.pack_start(label, True, True, 0)
            row.pack_start(value_label, False, False, 0)
            
            box.pack_start(row, False, False, 0)
        
        # 刷新按钮
        refresh_button = self._gtk.Button("refresh", _("Refresh Stats"), "color1")
        refresh_button.connect("clicked", self.refresh_stats)
        box.pack_start(refresh_button, False, False, 5)
        
        frame.add(box)
        return frame

    def refresh_stats(self, widget=None):
        """刷新统计信息"""
        try:
            if hasattr(self._screen, 'ai_manager'):
                ai_manager = self._screen.ai_manager
                stats = ai_manager.result_handler.get_detection_stats()
                
                # 更新统计标签
                self.stats_labels["total_detections"].set_text(str(stats.get("total_detections", 0)))
                self.stats_labels["defect_detections"].set_text(str(stats.get("defect_detections", 0)))
                self.stats_labels["defect_rate"].set_text(f"{stats.get('defect_rate', 0):.1f}%")
                self.stats_labels["avg_inference_time"].set_text(f"{stats.get('avg_inference_time', 0):.3f}s")
            else:
                for label in self.stats_labels.values():
                    label.set_text("N/A")
        except Exception as e:
            logging.error(f"刷新AI统计信息失败: {e}")

    def activate(self):
        """面板激活时调用"""
        # 刷新统计信息
        self.refresh_stats()