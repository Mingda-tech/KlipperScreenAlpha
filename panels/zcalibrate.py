import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    widgets = {}
    distances = ['.01', '.05', '.1', '.5', '1', '5']
    distance = distances[-2]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.z_offset = None
        self.probe = self._printer.get_probe()
        if self.probe:
            self.z_offset = float(self.probe['z_offset'])
        logging.info(f"Z offset: {self.z_offset}")
        self.widgets['zposition'] = Gtk.Label(label="Z: ?")

        pos = self._gtk.HomogeneousGrid()
        pos.attach(self.widgets['zposition'], 0, 1, 2, 1)
        z_up_image = "z-farther"
        z_down_image = "z-closer"
        z_up_label = _("Raise")  
        z_down_label = _("Lower")
        if "MD_400D" in self._printer.get_gcode_macros():
            z_up_image = "bed_down"
            z_down_image = "bed_up"
            z_up_label = _("Lower")
            z_down_label = _("Raise")
        if self.z_offset is not None:
            self.widgets['zoffset'] = Gtk.Label(label="?")
            pos.attach(Gtk.Label(_("Probe Offset") + ": "), 0, 2, 2, 1)
            pos.attach(Gtk.Label(_("Saved")), 0, 3, 1, 1)
            pos.attach(Gtk.Label(_("New")), 1, 3, 1, 1)
            pos.attach(Gtk.Label(f"{self.z_offset:.3f}"), 0, 4, 1, 1)
            pos.attach(self.widgets['zoffset'], 1, 4, 1, 1)
        self.buttons = {
            'zpos': self._gtk.Button(z_up_image, z_up_label, 'color4'),
            'zneg': self._gtk.Button(z_down_image, z_down_label, 'color1'),
            'start': self._gtk.Button('resume', _("Start"), 'color3'),
            'complete': self._gtk.Button('complete', _('Accept'), 'color3'),
            'cancel': self._gtk.Button('cancel', _('Abort'), 'color2'),
        }
        self.buttons['zpos'].connect("clicked", self.move, "+")
        self.buttons['zneg'].connect("clicked", self.move, "-")
        self.buttons['complete'].connect("clicked", self.accept)
        self.buttons['cancel'].connect("clicked", self.abort)

        functions = []
        pobox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        if "MD_DIST_CALIBRATE" in self._printer.available_commands:
            self._add_button("Probe", "probe", pobox)
            functions.append("md_dist")
        else:
            # if "Z_ENDSTOP_CALIBRATE" in self._printer.available_commands:
            #     self._add_button("Endstop", "endstop", pobox)
            #     functions.append("endstop")
            if "PROBE_CALIBRATE" in self._printer.available_commands:
                self._add_button("Probe", "probe", pobox)
                functions.append("probe")
            if "BED_MESH_CALIBRATE" in self._printer.available_commands and "probe" not in functions:
                # This is used to do a manual bed mesh if there is no probe
                self._add_button("Bed mesh", "mesh", pobox)
                functions.append("mesh")
            if "DELTA_CALIBRATE" in self._printer.available_commands:
                if "probe" in functions:
                    self._add_button("Delta Automatic", "delta", pobox)
                    functions.append("delta")
                # Since probes may not be accturate enough for deltas, always show the manual method
                self._add_button("Delta Manual", "delta_manual", pobox)
                functions.append("delta_manual")

        logging.info(f"Available functions for calibration: {functions}")

        self.labels['popover'] = Gtk.Popover()
        self.labels['popover'].add(pobox)
        self.labels['popover'].set_position(Gtk.PositionType.BOTTOM)

        if len(functions) > 1:
            self.buttons['start'].connect("clicked", self.on_popover_clicked)
        else:
            self.buttons['start'].connect("clicked", self.start_calibration, functions[0])

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.widgets[i] = self._gtk.Button(label=i)
            self.widgets[i].set_direction(Gtk.TextDirection.LTR)
            self.widgets[i].connect("clicked", self.change_distance, i)
            ctx = self.widgets[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.widgets[i], j, 0, 1, 1)

        self.widgets['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distances = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        distances.pack_start(self.widgets['move_dist'], True, True, 0)
        distances.pack_start(distgrid, True, True, 0)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        if self._screen.vertical_mode:
            grid.attach(self.buttons['zpos'], 0, 1, 1, 1)
            grid.attach(self.buttons['zneg'], 0, 2, 1, 1)
            grid.attach(self.buttons['start'], 0, 0, 1, 1)
            grid.attach(pos, 1, 0, 1, 1)
            grid.attach(self.buttons['complete'], 1, 1, 1, 1)
            grid.attach(self.buttons['cancel'], 1, 2, 1, 1)
            grid.attach(distances, 0, 3, 2, 1)
        else:
            if "MD_400D" in self._printer.get_gcode_macros():
                grid.attach(self.buttons['zneg'], 0, 0, 1, 1)
                grid.attach(self.buttons['zpos'], 0, 1, 1, 1)
            else:            
                grid.attach(self.buttons['zpos'], 0, 0, 1, 1)
                grid.attach(self.buttons['zneg'], 0, 1, 1, 1)
            grid.attach(self.buttons['start'], 1, 0, 1, 1)
            grid.attach(pos, 1, 1, 1, 1)
            grid.attach(self.buttons['complete'], 2, 0, 1, 1)
            grid.attach(self.buttons['cancel'], 2, 1, 1, 1)
            grid.attach(distances, 0, 2, 3, 1)
        self.content.add(grid)

    def _add_button(self, label, method, pobox):
        popover_button = self._gtk.Button(label=label)
        popover_button.connect("clicked", self.start_calibration, method)
        pobox.pack_start(popover_button, True, True, 5)

    def on_popover_clicked(self, widget):
        self.labels['popover'].set_relative_to(widget)
        self.labels['popover'].show_all()

    def start_calibration(self, widget, method):
        self.labels['popover'].popdown()
        self.buttons['start'].set_sensitive(False)
        if method == "md_dist":
            if "z" in self._printer.get_stat("toolhead", "homed_axes"):
                self._screen._ws.klippy.gcode_script("M18")            
            self._screen._ws.klippy.gcode_script("MD_DIST_CALIBRATE")
            return
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script("G28")
        if method == "probe":
            self._move_to_position()
            self._screen._ws.klippy.gcode_script("PROBE_CALIBRATE")
        elif method == "mesh":
            self._screen._ws.klippy.gcode_script("BED_MESH_CALIBRATE")
        elif method == "delta":
            self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE")
        elif method == "delta_manual":
            self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE METHOD=manual")
        elif method == "endstop":
            self._screen._ws.klippy.gcode_script("Z_ENDSTOP_CALIBRATE")

    def _move_to_position(self):
        x_position = y_position = None
        z_hop = speed = None
        # Get position from config
        if self.ks_printer_cfg is not None:
            x_position = self.ks_printer_cfg.getfloat("calibrate_x_position", None)
            y_position = self.ks_printer_cfg.getfloat("calibrate_y_position", None)

        if self.probe:
            if "sample_retract_dist" in self.probe:
                z_hop = self.probe['sample_retract_dist']
            if "speed" in self.probe:
                speed = self.probe['speed']

        # Use safe_z_home position
        if "safe_z_home" in self._printer.get_config_section_list():
            safe_z = self._printer.get_config_section("safe_z_home")
            safe_z_xy = safe_z['home_xy_position']
            safe_z_xy = [str(i.strip()) for i in safe_z_xy.split(',')]
            if x_position is None:
                x_position = float(safe_z_xy[0])
                logging.debug(f"Using safe_z x:{x_position}")
            if y_position is None:
                y_position = float(safe_z_xy[1])
                logging.debug(f"Using safe_z y:{y_position}")
            if 'z_hop' in safe_z:
                z_hop = safe_z['z_hop']
            if 'z_hop_speed' in safe_z:
                speed = safe_z['z_hop_speed']

        speed = 15 if speed is None else speed
        z_hop = 5 if z_hop is None else z_hop
        self._screen._ws.klippy.gcode_script(f"G91\nG0 Z{z_hop} F{float(speed) * 60}")
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

        if x_position is not None and y_position is not None:
            logging.debug(f"Configured probing position X: {x_position} Y: {y_position}")
            self._screen._ws.klippy.gcode_script(f'G0 X{x_position} Y{y_position} F3000')
        elif "delta" in self._printer.get_config_section("printer")['kinematics']:
            logging.info("Detected delta kinematics calibrating at 0,0")
            self._screen._ws.klippy.gcode_script('G0 X0 Y0 F3000')
        else:
            self._calculate_position()

    def _calculate_position(self):
        logging.debug("Position not configured, probing the middle of the bed")
        try:
            xmax = float(self._printer.get_config_section("stepper_x")['position_max'])
            ymax = float(self._printer.get_config_section("stepper_y")['position_max'])
        except KeyError:
            logging.error("Couldn't get max position from stepper_x and stepper_y")
            return
        x_position = xmax / 2
        y_position = ymax / 2
        logging.info(f"Center position X:{x_position} Y:{y_position}")

        # Find probe offset
        x_offset = y_offset = None
        if self.probe:
            if "x_offset" in self.probe:
                x_offset = float(self.probe['x_offset'])
            if "y_offset" in self.probe:
                y_offset = float(self.probe['y_offset'])
        logging.info(f"Offset X:{x_offset} Y:{y_offset}")
        if x_offset is not None:
            x_position = x_position - x_offset
        if y_offset is not None:
            y_position = y_position - y_offset

        logging.info(f"Moving to X:{x_position} Y:{y_position}")
        self._screen._ws.klippy.gcode_script(f'G0 X{x_position} Y{y_position} F3000')

    def activate(self):
        if self._printer.get_stat("manual_probe", "is_active"):
            self.buttons_calibrating()
        else:
            self.buttons_not_calibrating()

    def process_update(self, action, data):
        if action == "notify_status_update":
            if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.widgets['zposition'].set_text("Z: ?")
            elif "gcode_move" in data and "gcode_position" in data['gcode_move']:
                self.update_position(data['gcode_move']['gcode_position'])
            if "manual_probe" in data:
                if data["manual_probe"]["is_active"]:
                    self.buttons_calibrating()
                else:
                    self.buttons_not_calibrating()
        elif action == "notify_gcode_response":
            if "out of range" in data.lower():
                self._screen.show_popup_message(data)
                logging.info(data)
            elif "fail" in data.lower() and "use testz" in data.lower():
                self._screen.show_popup_message(_("Failed, adjust position first"))
                logging.info(data)
        return

    def update_position(self, position):
        self.widgets['zposition'].set_text(f"Z: {position[2]:.3f}")
        if self.z_offset is not None:
            self.widgets['zoffset'].set_text(f"{abs(position[2] - self.z_offset):.3f}")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.widgets[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.widgets[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move(self, widget, direction):
        self._screen._ws.klippy.gcode_script(f"TESTZ Z={direction}{self.distance}")

    def abort(self, widget):
        logging.info("Aborting calibration")
        self._screen._ws.klippy.gcode_script("ABORT")
        self.buttons_not_calibrating()
        self._screen._menu_go_back()

    def accept(self, widget):
        logging.info("Accepting Z position")
        self._screen._ws.klippy.gcode_script("ACCEPT")

    def buttons_calibrating(self):
        self.buttons['start'].get_style_context().remove_class('color3')
        self.buttons['start'].set_sensitive(False)

        self.buttons['zpos'].set_sensitive(True)
        self.buttons['zpos'].get_style_context().add_class('color4')
        self.buttons['zneg'].set_sensitive(True)
        self.buttons['zneg'].get_style_context().add_class('color1')
        self.buttons['complete'].set_sensitive(True)
        self.buttons['complete'].get_style_context().add_class('color3')
        self.buttons['cancel'].set_sensitive(True)
        self.buttons['cancel'].get_style_context().add_class('color2')
        for i in self.distances:
            self.widgets[i].set_sensitive(True)

    def buttons_not_calibrating(self):
        self.buttons['start'].get_style_context().add_class('color3')
        self.buttons['start'].set_sensitive(True)

        self.buttons['zpos'].set_sensitive(False)
        self.buttons['zpos'].get_style_context().remove_class('color4')
        self.buttons['zneg'].set_sensitive(False)
        self.buttons['zneg'].get_style_context().remove_class('color1')
        self.buttons['complete'].set_sensitive(False)
        self.buttons['complete'].get_style_context().remove_class('color3')
        self.buttons['cancel'].set_sensitive(False)
        self.buttons['cancel'].get_style_context().remove_class('color2')
        for i in self.distances:
            self.widgets[i].set_sensitive(False)
