"""
AI Monitor Panel
Displays AI detection status, real-time images, history, and controls
"""

import gi
import logging
import time
import threading
from datetime import datetime

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Pango

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.ai_manager = None
        
        # 创建主布局
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main.set_vexpand(True)
        main.set_hexpand(True)
        
        # 状态显示区域
        self.create_status_section(main)
        
        # 实时图像显示区域
        self.create_image_section(main)
        
        # 检测历史区域
        self.create_history_section(main)
        
        # 控制按钮区域
        self.create_control_section(main)
        
        self.content.add(main)
        
        # 定时更新状态
        GLib.timeout_add(1000, self.update_status)
    
    def create_status_section(self, parent):
        """创建状态显示区域"""
        status_frame = Gtk.Frame(label=_("AI Detection Status"))
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        status_box.set_margin_start(10)
        status_box.set_margin_end(10)
        status_box.set_margin_top(5)
        status_box.set_margin_bottom(5)
        
        # 服务状态
        service_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        service_label = Gtk.Label(_("Service Status:"))
        service_label.set_halign(Gtk.Align.START)
        self.service_status = Gtk.Label("Unknown")
        self.service_status.set_halign(Gtk.Align.END)
        self.service_status.set_hexpand(True)
        service_box.pack_start(service_label, False, False, 0)
        service_box.pack_start(self.service_status, True, True, 0)
        
        # 监控状态  
        monitor_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        monitor_label = Gtk.Label(_("Monitoring:"))
        monitor_label.set_halign(Gtk.Align.START)
        self.monitor_status = Gtk.Label("Stopped")
        self.monitor_status.set_halign(Gtk.Align.END)
        self.monitor_status.set_hexpand(True)
        monitor_box.pack_start(monitor_label, False, False, 0)
        monitor_box.pack_start(self.monitor_status, True, True, 0)
        
        # 最后检测时间
        last_detection_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        last_detection_label = Gtk.Label(_("Last Detection:"))
        last_detection_label.set_halign(Gtk.Align.START)
        self.last_detection_time = Gtk.Label("Never")
        self.last_detection_time.set_halign(Gtk.Align.END)
        self.last_detection_time.set_hexpand(True)
        last_detection_box.pack_start(last_detection_label, False, False, 0)
        last_detection_box.pack_start(self.last_detection_time, True, True, 0)
        
        status_box.pack_start(service_box, False, False, 0)
        status_box.pack_start(monitor_box, False, False, 0)
        status_box.pack_start(last_detection_box, False, False, 0)
        
        status_frame.add(status_box)
        parent.pack_start(status_frame, False, False, 0)
    
    def create_image_section(self, parent):
        """创建实时图像显示区域"""
        image_frame = Gtk.Frame(label=_("Current Detection Image"))
        
        # 图像显示
        self.detection_image = Gtk.Image()
        self.detection_image.set_size_request(320, 240)
        
        # 图像信息
        image_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.image_timestamp = Gtk.Label("No Image")
        self.image_timestamp.set_halign(Gtk.Align.CENTER)
        self.detection_result = Gtk.Label("")
        self.detection_result.set_halign(Gtk.Align.CENTER)
        
        image_info_box.pack_start(self.detection_image, True, True, 0)
        image_info_box.pack_start(self.image_timestamp, False, False, 0)
        image_info_box.pack_start(self.detection_result, False, False, 0)
        
        image_frame.add(image_info_box)
        parent.pack_start(image_frame, True, True, 0)
    
    def create_history_section(self, parent):
        """创建检测历史区域"""
        history_frame = Gtk.Frame(label=_("Detection History"))
        
        # 创建滚动窗口
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(-1, 150)
        
        # 创建历史列表
        self.history_listbox = Gtk.ListBox()
        self.history_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        
        scrolled.add(self.history_listbox)
        history_frame.add(scrolled)
        parent.pack_start(history_frame, False, False, 0)
    
    def create_control_section(self, parent):
        """创建控制按钮区域"""
        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        control_box.set_halign(Gtk.Align.CENTER)
        
        # 开始/停止监控按钮
        self.monitor_button = self._gtk.Button("resume", _("Start Monitoring"), "color1")
        self.monitor_button.connect("clicked", self.toggle_monitoring)
        
        # 手动检测按钮
        self.manual_detect_button = self._gtk.Button("refresh", _("Manual Detection"), "color2")
        self.manual_detect_button.connect("clicked", self.manual_detection)
        
        # 清除历史按钮
        clear_history_button = self._gtk.Button("delete", _("Clear History"), "color3")
        clear_history_button.connect("clicked", self.clear_history)
        
        control_box.pack_start(self.monitor_button, True, True, 5)
        control_box.pack_start(self.manual_detect_button, True, True, 5)
        control_box.pack_start(clear_history_button, True, True, 5)
        
        parent.pack_start(control_box, False, False, 0)
    
    def activate(self):
        """面板激活时调用"""
        # 获取AI管理器实例
        if hasattr(self._screen, 'ai_manager'):
            self.ai_manager = self._screen.ai_manager
        
        # 立即更新状态
        self.update_status()
        
        # 刷新历史记录
        self.refresh_history()
    
    def update_status(self):
        """更新状态显示"""
        if not self.ai_manager:
            return True
        
        try:
            # 更新服务状态
            if self.ai_manager.ai_client.health_check():
                self.service_status.set_text(_("Connected"))
                self.service_status.get_style_context().remove_class("error")
                self.service_status.get_style_context().add_class("success")
            else:
                self.service_status.set_text(_("Disconnected"))
                self.service_status.get_style_context().remove_class("success")
                self.service_status.get_style_context().add_class("error")
            
            # 更新监控状态
            if self.ai_manager.is_monitoring:
                self.monitor_status.set_text(_("Running"))
                self.monitor_button.set_label(_("Stop Monitoring"))
                self.monitor_status.get_style_context().add_class("success")
            else:
                self.monitor_status.set_text(_("Stopped"))
                self.monitor_button.set_label(_("Start Monitoring"))
                self.monitor_status.get_style_context().remove_class("success")
            
            # 更新最后检测时间
            stats = self.ai_manager.result_handler.get_detection_stats()
            last_time = stats.get('last_detection_time')
            if last_time:
                last_detection_str = datetime.fromtimestamp(last_time).strftime("%H:%M:%S")
                self.last_detection_time.set_text(last_detection_str)
            else:
                self.last_detection_time.set_text(_("Never"))
                
        except Exception as e:
            logging.error(f"更新AI监控状态失败: {e}")
        
        return True  # 继续定时器
    
    def toggle_monitoring(self, widget):
        """切换监控状态"""
        if not self.ai_manager:
            return
        
        if self.ai_manager.is_monitoring:
            self.ai_manager.stop_monitoring()
        else:
            if not self.ai_manager.start_monitoring():
                self._screen.show_popup_message(_("Failed to start AI monitoring"), level=3)
    
    def manual_detection(self, widget):
        """手动检测"""
        if not self.ai_manager:
            return
        
        def detection_worker():
            try:
                # 获取图像
                image_path = self.ai_manager.camera.capture_snapshot()
                if not image_path:
                    GLib.idle_add(self._screen.show_popup_message, 
                                _("Failed to capture image"), 3)
                    return
                
                # 执行检测
                result = self.ai_manager.ai_client.detect_sync(
                    image_path=image_path,
                    defect_types=self._config.get_enabled_defect_types(),
                    task_id=f"manual_{int(time.time())}"
                )
                
                # 更新UI
                GLib.idle_add(self.update_detection_result, result, image_path)
                
            except Exception as e:
                GLib.idle_add(self._screen.show_popup_message, 
                            f"Detection failed: {str(e)}", 3)
        
        # 在后台线程执行
        threading.Thread(target=detection_worker, daemon=True).start()
    
    def update_detection_result(self, result, image_path):
        """更新检测结果显示"""
        try:
            # 显示图像
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                image_path, 320, 240, True
            )
            self.detection_image.set_from_pixbuf(pixbuf)
            
            # 显示时间戳
            self.image_timestamp.set_text(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # 显示检测结果
            if result.get("has_defect", False):
                detections = result.get("detections", [])
                if detections:
                    max_detection = max(detections, key=lambda x: x.get("confidence", 0))
                    result_text = f"⚠️ {max_detection.get('class_name', 'Unknown')} " \
                                f"({max_detection.get('confidence', 0):.1%})"
                    self.detection_result.get_style_context().add_class("error")
                else:
                    result_text = "⚠️ Defect detected"
            else:
                result_text = "✅ No defects found"
                self.detection_result.get_style_context().remove_class("error")
            
            self.detection_result.set_text(result_text)
            
            # 刷新历史记录
            self.refresh_history()
            
        except Exception as e:
            logging.error(f"更新检测结果显示失败: {e}")
    
    def refresh_history(self):
        """刷新历史记录"""
        if not self.ai_manager:
            return
        
        # 清除现有项目  
        for child in self.history_listbox.get_children():
            self.history_listbox.remove(child)
        
        # 添加历史记录
        history = self.ai_manager.result_handler.get_detection_history(10)
        for record in reversed(history):  # 最新的在前
            self.add_history_item(record)
    
    def add_history_item(self, record):
        """添加历史记录项"""
        row = Gtk.ListBoxRow()
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(5)
        box.set_margin_end(5)
        box.set_margin_top(2)
        box.set_margin_bottom(2)
        
        # 时间
        timestamp = datetime.fromtimestamp(record.get("timestamp", 0))
        time_label = Gtk.Label(timestamp.strftime("%H:%M:%S"))
        time_label.set_size_request(80, -1)
        
        # 结果
        if "error" in record:
            result_label = Gtk.Label(f"❌ {record['error']}")
            result_label.get_style_context().add_class("error")
        elif record.get("has_defect", False):
            detections = record.get("detections", [])
            if detections:
                max_detection = max(detections, key=lambda x: x.get("confidence", 0))
                result_text = f"⚠️ {max_detection.get('class_name', 'Unknown')}"
                result_label = Gtk.Label(result_text)
                result_label.get_style_context().add_class("warning")
            else:
                result_label = Gtk.Label("⚠️ Defect")
        else:
            result_label = Gtk.Label("✅ OK")
        
        result_label.set_hexpand(True)
        result_label.set_halign(Gtk.Align.START)
        
        box.pack_start(time_label, False, False, 0)
        box.pack_start(result_label, True, True, 0)
        
        row.add(box)
        self.history_listbox.add(row)
        
        # 显示所有新添加的组件
        row.show_all()
    
    def clear_history(self, widget):
        """清除历史记录"""
        if self.ai_manager:
            self.ai_manager.result_handler.detection_history = []
            self.refresh_history()