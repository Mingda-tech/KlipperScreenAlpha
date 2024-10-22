import logging
import gi
from gi.repository import Gtk, GLib, Pango, Gdk
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.nozzle_height_difference = None
        self.update_nozzle_height_difference()
        logging.info(f"nozzle height difference: {self.nozzle_height_difference}")

        grid = self._gtk.HomogeneousGrid()
        grid.set_column_homogeneous(True)

        self.labels = {
            'height_diff': Gtk.Label(label=_("Current nozzle height difference: ") + f"{self.nozzle_height_difference:.3f} mm" if self.nozzle_height_difference is not None else _("Current nozzle height difference: ?")),
            'pei_reminder': Gtk.Label(label=_("If your calibration device is under the PEI, please lift the PEI after homing."))
        }

        # 设置红色字体和自动换行
        for label in self.labels.values():
            label.set_line_wrap(True)
            label.set_max_width_chars(40)  # 设置最大字符宽度，可以根据需要调整

        self.labels['pei_reminder'].override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 0, 0, 1))  # 红色
        self.labels['pei_reminder'].override_font(Pango.FontDescription("Bold"))  # 加粗

        self.buttons = {
            'start': self._gtk.Button('resume', _("Start"), 'color3')
        }
        self.buttons['start'].connect("clicked", self.start_calibration)

        # 调整网格布局，将 start 按钮放在最上方
        grid.attach(self.buttons['start'], 0, 0, 1, 1)
        grid.attach(self.labels['height_diff'], 0, 1, 1, 1)
        grid.attach(self.labels['pei_reminder'], 0, 2, 1, 1)

        self.content.add(grid)

    def update_nozzle_height_difference(self):
        self.nozzle_height_difference = None
        if self._screen.klippy_config is not None:
            try:
                self.nozzle_height_difference = self._screen.klippy_config.getfloat("Variables", "e1_zoffset")
            except Exception as e:
                logging.error(f"Read {self._screen.klippy_config_path} error:\n{e}")        

    def start_calibration(self, widget):
        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes != "xyz":
            self._screen.show_popup_message(_("Homing the printer..."), level=1)
            self._screen._ws.klippy.gcode_script("G28")
            GLib.idle_add(self.labels['pei_reminder'].set_text, _("If your calibration device is under the PEI, please lift the PEI after homing."))
        else:
            self._screen.show_popup_message(_("Starting dual nozzle height calibration..."), level=1)
            self._screen._ws.klippy.gcode_script("DUAL_NOZZLE_HEIGHT_CALIBRATION")
            # 禁用 start 按钮
            self.buttons['start'].set_sensitive(False)
            # 更改 pei_reminder 的文本
            GLib.idle_add(self.labels['pei_reminder'].set_text, _("Please observe if the nozzle is positioned above the probe."))

    def process_update(self, action, data):
        if action == "notify_status_update":
            if "gcode_move" in data and "gcode_position" in data['gcode_move']:
                self.update_position(data['gcode_move']['gcode_position'])
        elif action == "notify_gcode_response":
            if "nozzle height calibration completed" in data.lower():
                # 直接从校准输出中获取新的值
                try:
                    new_value = float(data.split(":")[-1].strip())
                    self.nozzle_height_difference = new_value
                    self.calibration_completed()
                except ValueError:
                    logging.error("Failed to parse new nozzle height difference from calibration output")
                    self.calibration_completed()

    def update_position(self, position):
        # This method is kept for potential future use
        pass

    def calibration_completed(self):
        if self.nozzle_height_difference is not None and self.nozzle_height_difference < 0:
            # 如果是负数，更新 pei_reminder 的文本为警告信息
            GLib.idle_add(self.labels['pei_reminder'].set_text, _("Warning: Negative value detected. This is dangerous and may damage the machine. Please recalibrate."))
            # 更新显示，但不提供保存选项
            GLib.idle_add(self.labels['height_diff'].set_text, f"Dangerous nozzle height difference: {self.nozzle_height_difference:.3f} mm")
            # 重新启用 start 按钮以允许重新校准
            GLib.idle_add(self.buttons['start'].set_sensitive, True)
        else:
            # 正常情况下的处理
            GLib.idle_add(self.labels['height_diff'].set_text, f"New nozzle height difference: {self.nozzle_height_difference:.3f} mm" if self.nozzle_height_difference is not None else "New nozzle height difference: ?")
            GLib.idle_add(self.buttons['start'].set_sensitive, True)
            # 显示保存配置的确认对话框
            self._screen._confirm_send_action(
                None,
                _("New nozzle height difference is: ") + f"{self.nozzle_height_difference:.3f} mm" + "\n\n" + _("Need reboot, relaunch immediately?"),
                "printer.gcode.script",
                {"script": "SAVE_CONFIG"} # 保存配置
            )

    def activate(self):
        self.update_nozzle_height_difference()
        GLib.idle_add(self.labels['height_diff'].set_text, _("Current nozzle height difference: ") + f"{self.nozzle_height_difference:.3f} mm" if self.nozzle_height_difference is not None else _("Current nozzle height difference: ?"))
        # 检查是否为负值，如果是，显示警告
        if self.nozzle_height_difference is not None and self.nozzle_height_difference < 0:
            GLib.idle_add(self.labels['pei_reminder'].set_text, _("Warning: Current value is negative. This is dangerous and may damage the machine. Please recalibrate."))
        else:
            GLib.idle_add(self.labels['pei_reminder'].set_text, _("If your calibration device is under the PEI, please lift the PEI after homing."))
        self.buttons['start'].set_sensitive(True)
