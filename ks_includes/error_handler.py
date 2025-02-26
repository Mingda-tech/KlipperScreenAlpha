import logging
import os
from typing import Dict, List, Optional
from gi.repository import Gtk, Pango, GdkPixbuf, GLib

class ErrorHandler:
    """处理KlipperScreen中的错误并提供修复指导"""
    
    def __init__(self, screen):
        self._screen = screen
        self.resource_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resource/error_resolution")
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

    def create_image_box(self, image_dir: str) -> Gtk.Box:
        """创建包含图片的滚动框"""
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_homogeneous(False)
        
        # 获取图片目录
        img_path = os.path.join(self.resource_path, image_dir)
        if not os.path.exists(img_path):
            return None
            
        # 加载并显示所有图片
        images = sorted([f for f in os.listdir(img_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
        for img_file in images:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    os.path.join(img_path, img_file),
                    300,  # 宽度
                    200,  # 高度
                    True   # 保持比例
                )
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                box.pack_start(image, False, False, 0)
            except GLib.Error as e:
                logging.error(f"无法加载图片 {img_file}: {str(e)}")
                continue
        
        scroll.add(box)
        return scroll

    def show_error_guide(self, error_message: str):
        """显示错误引导对话框"""
        error_info = self.identify_error(error_message)
        
        # 创建主容器
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # 创建错误引导对话框内容
        if error_info:
            title = error_info["title"]
            content = f"<b>{title}</b>\n\n"
            content += f"错误信息: {error_message}\n\n"
            content += "可能的解决方案:\n\n"
            content += "\n".join(error_info["solutions"])
            content += f"\n\n联系方式:\n{error_info['contact']}"
            
            # 添加文字说明
            label = Gtk.Label(label="")
            label.set_markup(content)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            main_box.pack_start(label, False, False, 0)
            
            # 添加图片指引
            if "image_dir" in error_info:
                image_box = self.create_image_box(error_info["image_dir"])
                if image_box:
                    main_box.pack_start(image_box, True, True, 10)
        else:
            title = "未知错误"
            content = f"<b>{title}</b>\n\n"
            content += f"错误信息: {error_message}\n\n"
            content += "建议解决方案:\n\n"
            content += "1. 检查打印机的物理连接\n"
            content += "2. 查看打印机日志获取详细信息\n"
            content += "3. 检查printer.cfg配置文件\n"
            content += "4. 如果问题持续，请联系技术支持\n\n"
            content += "联系方式:\n"
            content += "售后邮箱: support@3dmingda.com\n"
            content += "WhatsApp: (+86）13530306290"
            
            label = Gtk.Label(label="")
            label.set_markup(content)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            main_box.pack_start(label, False, False, 0)

        # 显示带有解决方案的对话框
        buttons = [
            {"name": "确定", "response": Gtk.ResponseType.OK},
            {"name": "取消", "response": Gtk.ResponseType.CANCEL}
        ]
        
        # 设置对话框大小
        main_box.set_size_request(800, -1)  # 设置固定宽度
        
        self._screen.gtk.Dialog(
            title,
            buttons,
            main_box,
            self.error_guide_response
        )

    def error_guide_response(self, dialog, response_id):
        """处理错误引导对话框的响应"""
        self._screen.gtk.remove_dialog(dialog)
        # 这里可以添加更多的响应处理逻辑 