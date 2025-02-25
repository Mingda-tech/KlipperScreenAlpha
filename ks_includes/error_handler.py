import logging
from typing import Dict, List, Optional
from gi.repository import Gtk

class ErrorHandler:
    """处理KlipperScreen中的错误并提供修复指导"""
    
    def __init__(self, screen):
        self._screen = screen
        # 定义常见错误类型及其解决方案
        self.error_solutions: Dict[str, Dict] = {
            "bed_leveling": {
                "patterns": [
                    "probe failed to trigger",
                    "bed leveling failed",
                    "out of range",
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
                "help_link": "https://www.klipper3d.org/Bed_Level.html"
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
                "help_link": "https://www.klipper3d.org/Config_Reference.html#temperature_sensor"
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
                ],
                "help_link": "https://www.klipper3d.org/Config_Reference.html#stepper"
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
                "help_link": "https://www.klipper3d.org/Config_Reference.html#mcu"
            }
        }

    def identify_error(self, error_message: str) -> Optional[Dict]:
        """识别错误类型并返回相应的解决方案"""
        error_message = error_message.lower()
        
        for error_type, error_info in self.error_solutions.items():
            for pattern in error_info["patterns"]:
                if pattern.lower() in error_message:
                    return error_info
        return None

    def show_error_guide(self, error_message: str):
        """显示错误引导对话框"""
        error_info = self.identify_error(error_message)
        if not error_info:
            # 如果无法识别错误类型，显示通用错误信息
            self._screen.show_error_modal("未知错误", error_message)
            return

        # 创建错误引导对话框内容
        content = f"<b>{error_info['title']}</b>\n\n"
        content += f"错误信息: {error_message}\n\n"
        content += "可能的解决方案:\n\n"
        content += "\n".join(error_info["solutions"])
        content += f"\n\n详细文档: {error_info['help_link']}"

        # 显示带有解决方案的对话框
        buttons = [
            {"name": "确定", "response": Gtk.ResponseType.OK},
            {"name": "取消", "response": Gtk.ResponseType.CANCEL}
        ]
        
        label = Gtk.Label(label="") # 创建一个空的标签
        label.set_markup(content)
        label.set_line_wrap(True)
        
        self._screen.gtk.Dialog(
            error_info["title"],
            buttons,
            label,
            self.error_guide_response
        )

    def error_guide_response(self, dialog, response_id):
        """处理错误引导对话框的响应"""
        self._screen.gtk.remove_dialog(dialog)
        # 这里可以添加更多的响应处理逻辑 