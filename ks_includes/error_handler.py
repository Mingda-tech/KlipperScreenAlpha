import logging
import os
from typing import Dict, List, Optional
from gi.repository import Gtk, Pango, GdkPixbuf, GLib, Gdk

class ErrorHandler:
    """处理KlipperScreen中的错误并提供修复指导"""
    
    def __init__(self, screen):
        self._screen = screen
        self.resource_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resource/error_resolution")
        
        # 获取屏幕分辨率
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display else None
        if monitor:
            geometry = monitor.get_geometry()
            self.screen_width = geometry.width
            self.screen_height = geometry.height
        else:
            # 如果无法获取屏幕分辨率，使用默认值
            self.screen_width = 1024
            self.screen_height = 600
            
        # 计算图片显示尺寸（屏幕宽度的75%）
        self.image_width = int(self.screen_width * 0.75)
        self.image_height = int(self.screen_height * 0.75)
        
        # 定义常见错误类型及其解决方案
        self.error_solutions: Dict[str, Dict] = {
            "bed_leveling": {
                "patterns": [
                    "probe failed to trigger",
                    "bed leveling failed",
                    "z-probe",
                ],
                "title": "调平错误",
                "solutions": [
                    "1. 检查Z探针是否正确安装和连接",
                    "2. 确保打印平台表面清洁",
                    "3. 调整Z探针的触发高度",
                    "4. 检查调平点是否在打印平台范围内",
                    "5. 校准Z偏移值"
                ],
                "contact": "售后邮箱: support@3dmingda.com\nWhatsApp: (+86）13530306290",
                "image_dir": "bed_leveling"
            },
            "temperature": {
                "patterns": [
                    "temperature too high",
                    "temperature too low", 
                    "thermal runaway",
                    "heating failed"
                ],
                "title": "温度错误",
                "solutions": [
                    "1. 检查加热器和热敏电阻连接",
                    "2. 确认PID参数是否正确",
                    "3. 检查风扇是否正常工作",
                    "4. 执行PID校准",
                    "5. 检查温度传感器是否损坏"
                ],
                "contact": "售后邮箱: support@3dmingda.com\nWhatsApp: (+86）13530306290",
                "image_dir": "temperature"
            },
            "movement": {
                "patterns": [
                    "Move out of range",
                    "move out of range",
                    "endstop not triggered",
                    "homing failed",
                    "motor stalled"
                ],
                "title": "运动错误",
                "solutions": [
                    "1. 确保已经执行回零操作",
                    "2. 检查打印机配置中的最大行程设置",
                    "3. 检查移动命令中的坐标值是否正确",
                    "4. 检查限位开关状态和连接",
                    "5. 检查步进电机和驱动器",
                    "6. 确认皮带张紧度",
                    "7. 检查运动系统是否有卡阻",
                    "8. 如果需要，可以修改printer.cfg中的position_max和position_min参数"
                ],
                "contact": "售后邮箱: support@3dmingda.com\nWhatsApp: (+86）13530306290",
                "image_dir": "movement"
            },
            "firmware": {
                "patterns": [
                    "mcu 'mcu' shutdown",
                    "Lost communication with MCU",
                    "Unable to connect",
                    "firmware error"
                ],
                "title": "固件错误",
                "solutions": [
                    "1. 检查USB连接",
                    "2. 重新编译并刷写固件",
                    "3. 检查主控板供电",
                    "4. 确认串口配置正确",
                    "5. 尝试重启打印机"
                ],
                "contact": "售后邮箱: support@3dmingda.com\nWhatsApp: (+86）13530306290",
                "image_dir": "firmware"
            }
        }

    def identify_error(self, error_message: str) -> Optional[Dict]:
        """识别错误类型并返回相应的解决方案"""
        error_message = error_message.lower()
        
        # 优先检查移动超范围错误
        if "move out of range" in error_message:
            return self.error_solutions["movement"]
            
        # 然后检查其他错误类型
        for error_type, error_info in self.error_solutions.items():
            for pattern in error_info["patterns"]:
                if pattern.lower() in error_message and not (
                    error_type == "bed_leveling" and "move out of range" in error_message
                ):
                    return error_info
        return None

    def create_step_box(self, step: str, image_path: str = None) -> Gtk.Box:
        """创建单个步骤的容器，包含文字说明和可选的图片"""
        step_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        step_box.set_margin_top(10)
        step_box.set_margin_bottom(10)
        step_box.set_margin_start(10)
        step_box.set_margin_end(10)
        
        # 添加步骤文字
        label = Gtk.Label(label=step)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_halign(Gtk.Align.START)
        step_box.pack_start(label, False, False, 0)
        
        # 如果有对应的图片，添加图片
        if image_path and os.path.exists(image_path):
            try:
                # 先加载原始图片
                original_pixbuf = GdkPixbuf.Pixbuf.new_from_file(image_path)
                original_width = original_pixbuf.get_width()
                original_height = original_pixbuf.get_height()
                
                # 计算缩放比例
                width_ratio = self.image_width / original_width
                height_ratio = self.image_height / original_height
                scale_ratio = min(width_ratio, height_ratio)
                
                # 计算缩放后的尺寸
                new_width = int(original_width * scale_ratio)
                new_height = int(original_height * scale_ratio)
                
                # 创建缩放后的图片
                pixbuf = original_pixbuf.scale_simple(
                    new_width,
                    new_height,
                    GdkPixbuf.InterpType.BILINEAR
                )
                
                # 创建图片容器
                image_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
                image_box.set_halign(Gtk.Align.CENTER)  # 水平居中
                
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                image.set_margin_top(5)
                image_box.pack_start(image, False, False, 0)
                
                step_box.pack_start(image_box, False, False, 0)
                
            except GLib.Error as e:
                logging.error(f"无法加载图片 {image_path}: {str(e)}")
        
        return step_box

    def show_error_guide(self, error_message: str):
        """显示错误引导对话框"""
        error_info = self.identify_error(error_message)
        
        # 创建主滚动窗口
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # 创建主容器
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        
        if error_info:
            # 添加错误标题和信息
            error_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            error_header.get_style_context().add_class('error-header')
            error_header.set_margin_bottom(20)
            error_header.set_margin_start(10)
            error_header.set_margin_end(10)
            
            title_label = Gtk.Label()
            title_label.set_markup(f"<b>{error_info['title']}</b>")
            title_label.set_halign(Gtk.Align.START)
            error_header.pack_start(title_label, False, False, 0)
            
            error_label = Gtk.Label(label=error_message)
            error_label.set_line_wrap(True)
            error_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            error_label.set_halign(Gtk.Align.START)
            error_header.pack_start(error_label, False, False, 0)
            
            main_box.pack_start(error_header, False, False, 0)
            
            # 添加解决步骤
            steps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            img_path = os.path.join(self.resource_path, error_info.get("image_dir", ""))
            
            for i, solution in enumerate(error_info["solutions"], 1):
                img_file = f"{i}.png"
                img_full_path = os.path.join(img_path, img_file) if os.path.exists(os.path.join(img_path, img_file)) else None
                step_box = self.create_step_box(solution, img_full_path)
                steps_box.pack_start(step_box, False, False, 0)
            
            main_box.pack_start(steps_box, True, True, 0)
            
            # 添加联系方式
            contact_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            contact_box.set_margin_top(20)
            contact_box.set_margin_start(10)
            contact_box.set_margin_end(10)
            
            contact_label = Gtk.Label()
            contact_label.set_markup(f"<b>联系方式</b>\n{error_info['contact']}")
            contact_label.set_halign(Gtk.Align.START)
            contact_box.pack_start(contact_label, False, False, 0)
            
            main_box.pack_start(contact_box, False, False, 0)
        else:
            # 处理未知错误
            title = "未知错误"
            unknown_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            unknown_box.set_margin_start(10)
            unknown_box.set_margin_end(10)
            
            title_label = Gtk.Label()
            title_label.set_markup(f"<b>{title}</b>")
            title_label.set_halign(Gtk.Align.START)
            unknown_box.pack_start(title_label, False, False, 0)
            
            error_label = Gtk.Label(label=error_message)
            error_label.set_line_wrap(True)
            error_label.set_halign(Gtk.Align.START)
            unknown_box.pack_start(error_label, False, False, 0)
            
            solutions = [
                "1. 检查打印机的物理连接",
                "2. 查看打印机日志获取详细信息",
                "3. 检查printer.cfg配置文件",
                "4. 如果问题持续，请联系技术支持"
            ]
            
            for solution in solutions:
                step_box = self.create_step_box(solution)
                unknown_box.pack_start(step_box, False, False, 0)
            
            contact_label = Gtk.Label()
            contact_label.set_markup("\n<b>联系方式</b>\n售后邮箱: support@3dmingda.com\nWhatsApp: (+86）13530306290")
            contact_label.set_halign(Gtk.Align.START)
            unknown_box.pack_start(contact_label, False, False, 0)
            
            main_box.pack_start(unknown_box, True, True, 0)
        
        scroll.add(main_box)
        
        # 设置对话框大小为屏幕的80%
        dialog_width = int(self.screen_width * 0.8)
        dialog_height = int(self.screen_height * 0.8)
        scroll.set_size_request(dialog_width, dialog_height)
        
        # 显示对话框
        buttons = [
            {"name": "确定", "response": Gtk.ResponseType.OK}
        ]
        
        self._screen.gtk.Dialog(
            "错误修复指南",
            buttons,
            scroll,
            self.error_guide_response
        )

    def error_guide_response(self, dialog, response_id):
        """处理错误引导对话框的响应"""
        self._screen.gtk.remove_dialog(dialog) 