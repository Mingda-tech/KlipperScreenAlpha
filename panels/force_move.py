import re
import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    distances = ['.02', '.1', '.2', '.5', '1', '5', '10']
    distance = distances[-2]

    # Constants for movement
    AXIS_SETTINGS = {
        'X': {'stepper': 'stepper_x', 'speed': 50},
        'Y': {'stepper': 'stepper_y', 'speed': 50},
        'Z': {'stepper': 'stepper_z', 'speed': 10}
    }
    LARGE_MOVE_THRESHOLD = 2
    DEFAULT_ACCEL = 100

    def __init__(self, screen, title):
        super().__init__(screen, title)

        if self.ks_printer_cfg is not None:
            dis = self.ks_printer_cfg.get("move_distances", '0.02, 0.1, 0.2, 0.5, 1, 5, 10')
            if re.match(r'^[0-9,\.\s]+$', dis):
                dis = [str(i.strip()) for i in dis.split(',')]
                if 1 < len(dis) <= 7:
                    self.distances = dis
                    self.distance = self.distances[0]

        macros = self._printer.get_config_section_list("gcode_macro ")
        logging.info(f"111111111111### macros: {macros}")
        self.force_move = any("FORCE_MOVE" in macro.upper() for macro in macros)

        self.settings = {}
        self.menu = ['move_menu']
        z_up_image = "z-farther"
        z_down_image = "z-closer"
        z_up_label = _("Raise") 
        z_down_label = _("Lower")
        if "MD_400D" in self._printer.get_gcode_macros():
            z_up_image = "bed_down"
            z_down_image = "bed_up"
            z_up_label = _("Lower")
            z_down_label = _("Raise")
        self.buttons = {
            'x+': self._gtk.Button("arrow-right", "X+", "color1"),
            'x-': self._gtk.Button("arrow-left", "X-", "color1"),
            'y+': self._gtk.Button("arrow-up", "Y+", "color2"),
            'y-': self._gtk.Button("arrow-down", "Y-", "color2"),
            'z+': self._gtk.Button(z_up_image, z_up_label, "color3"),
            'z-': self._gtk.Button(z_down_image, z_down_label, "color3"),
        }
        self.buttons['x+'].connect("clicked", self.move, "X", "+")
        self.buttons['x-'].connect("clicked", self.move, "X", "-")
        self.buttons['y+'].connect("clicked", self.move, "Y", "+")
        self.buttons['y-'].connect("clicked", self.move, "Y", "-")
        self.buttons['z+'].connect("clicked", self.move, "Z", "+")
        self.buttons['z-'].connect("clicked", self.move, "Z", "-")

        adjust = self._gtk.Button("settings", None, "color2", 1, Gtk.PositionType.LEFT, 1)
        adjust.connect("clicked", self.load_menu, 'options', _('Settings'))
        adjust.set_hexpand(False)
        grid = self._gtk.HomogeneousGrid()
        if self._screen.vertical_mode:
            if self._screen.lang_ltr:
                grid.attach(self.buttons['x+'], 2, 1, 1, 1)
                grid.attach(self.buttons['x-'], 0, 1, 1, 1)
                grid.attach(self.buttons['z+'], 2, 2, 1, 1)
                grid.attach(self.buttons['z-'], 0, 2, 1, 1)
            else:
                grid.attach(self.buttons['x+'], 0, 1, 1, 1)
                grid.attach(self.buttons['x-'], 2, 1, 1, 1)

                grid.attach(self.buttons['z+'], 0, 2, 1, 1)
                grid.attach(self.buttons['z-'], 2, 2, 1, 1)
            # grid.attach(adjust, 1, 2, 1, 1)
            grid.attach(self.buttons['y+'], 1, 0, 1, 1)
            grid.attach(self.buttons['y-'], 1, 1, 1, 1)

        else:
            if self._screen.lang_ltr:
                grid.attach(self.buttons['x+'], 2, 1, 1, 1)
                grid.attach(self.buttons['x-'], 0, 1, 1, 1)
            else:
                grid.attach(self.buttons['x+'], 0, 1, 1, 1)
                grid.attach(self.buttons['x-'], 2, 1, 1, 1)
            grid.attach(self.buttons['y+'], 1, 0, 1, 1)
            grid.attach(self.buttons['y-'], 1, 1, 1, 1)
            if "MD_400D" in self._printer.get_gcode_macros():
                grid.attach(self.buttons['z-'], 3, 0, 1, 1)
                grid.attach(self.buttons['z+'], 3, 1, 1, 1)
            else:
                grid.attach(self.buttons['z+'], 3, 0, 1, 1)
                grid.attach(self.buttons['z-'], 3, 1, 1, 1)

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.labels[i] = self._gtk.Button(label=i)
            self.labels[i].set_direction(Gtk.TextDirection.LTR)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 0, 1, 1)

        for p in ('pos_x', 'pos_y', 'pos_z'):
            self.labels[p] = Gtk.Label()
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))

        bottomgrid = self._gtk.HomogeneousGrid()
        bottomgrid.set_direction(Gtk.TextDirection.LTR)
        bottomgrid.attach(self.labels['move_dist'], 0, 1, 1, 1)

        self.labels['move_menu'] = self._gtk.HomogeneousGrid()
        self.labels['move_menu'].attach(grid, 0, 0, 1, 3)
        self.labels['move_menu'].attach(bottomgrid, 0, 3, 1, 1)
        self.labels['move_menu'].attach(distgrid, 0, 4, 1, 1)

        self.content.add(self.labels['move_menu'])

        printer_cfg = self._printer.get_config_section("printer")
        # The max_velocity parameter is not optional in klipper config.
        max_velocity = int(float(printer_cfg["max_velocity"]))
        if max_velocity <= 1:
            logging.error(f"Error getting max_velocity\n{printer_cfg}")
            max_velocity = 50
        if "max_z_velocity" in printer_cfg:
            max_z_velocity = max(int(float(printer_cfg["max_z_velocity"])), 10)
        else:
            max_z_velocity = max_velocity

        configurable_options = [
            {"invert_x": {"section": "main", "name": _("Invert X"), "type": "binary", "value": "False"}},
            {"invert_y": {"section": "main", "name": _("Invert Y"), "type": "binary", "value": "False"}},
            {"invert_z": {"section": "main", "name": _("Invert Z"), "type": "binary", "value": "False"}},
            {"move_speed_xy": {
                "section": "main", "name": _("XY Speed (mm/s)"), "type": "scale", "value": "50",
                "range": [1, max_velocity], "step": 1}},
            {"move_speed_z": {
                "section": "main", "name": _("Z Speed (mm/s)"), "type": "scale", "value": "10",
                "range": [1, max_z_velocity], "step": 1}}
        ]

        self.labels['options_menu'] = self._gtk.ScrolledWindow()
        self.labels['options'] = Gtk.Grid()
        self.labels['options_menu'].add(self.labels['options'])
        for option in configurable_options:
            name = list(option)[0]
            self.add_option('options', self.settings, name, option[name])

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def _build_z_movement_script(self, axis, dist, speed):
        """构建Z轴移动的G代码脚本"""
        return [
            f"SET_KINEMATIC_POSITION_Z Z=10.0",
            f"{KlippyGcodes.MOVE_RELATIVE}",
            f"G1 {axis}{dist} F{speed * 60}",
            "M400",
            f"{KlippyGcodes.MOVE_ABSOLUTE}"
        ]

    def _execute_movement(self, widget, axis, script, distance, show_confirm=True):
        """执行移动命令，根据距离决定是否需要确认"""
        try:
            is_large_move = abs(float(distance)) > self.LARGE_MOVE_THRESHOLD
            script_data = {"script": script if isinstance(script, str) else "\n".join(script)}
            
            if is_large_move and show_confirm:
                self._show_move_confirmation(axis, distance, script_data)
            else:
                self._screen._send_action(
                    widget,
                    "printer.gcode.script",
                    script_data
                )
        except ValueError as ve:
            logging.exception(f"Invalid distance value: {distance}")
        except Exception as e:
            logging.exception(f"Error executing movement: {str(e)}")

    def _show_move_confirmation(self, axis, distance, script_data):
        """显示移动确认对话框"""
        sign = "+" if float(distance) > 0 else ""
        label = Gtk.Label()
        label.set_label(_("Force move: ") + f"{axis}{sign}{distance}mm?")
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = self._gtk.HomogeneousGrid()
        grid.attach(label, 0, 0, 1, 1)

        buttons = [
            {"name": _("Move"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        
        self._gtk.Dialog(_("Confirm Movement"), buttons, grid, self._handle_movement_confirm, script_data)

    def _handle_movement_confirm(self, dialog, response_id, script_data):
        """处理移动确认对话框的回调"""
        self._gtk.remove_dialog(dialog)
        try:
            if response_id == Gtk.ResponseType.OK:
                self._screen._send_action(
                    None,
                    "printer.gcode.script",
                    script_data
                )
        except Exception as e:
            logging.exception(f"Error handling movement confirmation: {str(e)}")

    def move(self, widget, axis, direction):
        """处理轴移动请求"""
        try:
            # 检查轴反转设置
            if self._config.get_config()['main'].getboolean(f"invert_{axis.lower()}", False):
                direction = "-" if direction == "+" else "+"

            # 计算移动距离和获取轴设置
            dist = f"{direction}{self.distance}"
            axis_config = self.AXIS_SETTINGS.get(axis)
            if not axis_config:
                logging.error(f"Invalid axis: {axis}")
                return

            if self.force_move:
                if axis == 'Z':
                    script = self._build_z_movement_script(axis, dist, axis_config['speed'])
                else:
                    script = f"FORCE_MOVE_BACE STEPPER={axis_config['stepper']} DISTANCE={dist} VELOCITY={axis_config['speed']} ACCEL={self.DEFAULT_ACCEL}"
            else:
                script = f"FORCE_MOVE STEPPER={axis_config['stepper']} DISTANCE={dist} VELOCITY={axis_config['speed']} ACCEL={self.DEFAULT_ACCEL}"

            self._execute_movement(widget, axis, script, self.distance)

        except Exception as e:
            logging.exception(f"Error during axis movement: {str(e)}")

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup(f"<big><b>{option['name']}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.get_style_context().add_class("frame-item")
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)
        dev.add(name)

        if option['type'] == "binary":
            box = Gtk.Box()
            box.set_vexpand(False)
            switch = Gtk.Switch()
            switch.set_hexpand(False)
            switch.set_vexpand(False)
            switch.set_active(self._config.get_config().getboolean(option['section'], opt_name))
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name)
            switch.set_property("width-request", round(self._gtk.font_size * 7))
            switch.set_property("height-request", round(self._gtk.font_size * 3.5))
            box.add(switch)
            dev.add(box)
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

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False
