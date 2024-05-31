import logging
import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    widgets = {}
    distances = ['.01', '.05', '.1', '.5', '1', '5']
    distance = distances[-2]
    step_index = 0
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.z_offset = None
        if self._screen.klippy_config is not None:
            try:
                self.z_offset = self._screen.klippy_config.getfloat("Variables", "e1_zoffset")
                self.zendstop = self._screen.klippy_config.getfloat("Variables", "zendstop", fallback=0)
            except Exception as e:
                logging.error(f"Read {self._screen.klippy_config_path} error:\n{e}")

            logging.info(f"Z offset: {self.z_offset}")
        self.widgets['zposition'] = Gtk.Label(label="Z: ?")
        self.is_start_calibrate = False

        self.pos = {}
        self.pos['z'] = 100
        self.pos['l_z'] = None
        self.pos['r_z'] = None
        self.bed_mesh_profile = None
        self.zmax = float(self._printer.get_config_section("stepper_z")['position_max'])
        pos = self._gtk.HomogeneousGrid()
        pos.attach(self.widgets['zposition'], 0, 1, 2, 1)
        if self.z_offset is not None:
            self.widgets['zoffset'] = Gtk.Label(label="?")
            pos.attach(Gtk.Label(_("Right Extruder Z Offset") + ": "), 0, 2, 2, 1)
            pos.attach(Gtk.Label(_("Saved")), 0, 3, 1, 1)
            pos.attach(Gtk.Label(_("New")), 1, 3, 1, 1)
            pos.attach(Gtk.Label(f"{self.z_offset:.3f}"), 0, 4, 1, 1)
            pos.attach(self.widgets['zoffset'], 1, 4, 1, 1)
        self.buttons = {
            'zpos': self._gtk.Button('z-farther', _("Raise Nozzle"), 'color4'),
            'zneg': self._gtk.Button('z-closer', _("Lower Nozzle"), 'color1'),
            'start': self._gtk.Button('resume', _("Start"), 'color3'),
            'complete': self._gtk.Button('complete', _('Accept'), 'color3'),
            'cancel': self._gtk.Button('cancel', _('Abort'), 'color2'),
        }
        self.buttons['zpos'].connect("clicked", self.move, "+")
        self.buttons['zneg'].connect("clicked", self.move, "-")
        self.buttons['complete'].connect("clicked", self.accept)
        self.buttons['cancel'].connect("clicked", self.abort)
        self.buttons['start'].connect("clicked", self.start_calibration)

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

    def start_calibration(self, widget):
        self.pos['z'] = 100
        self.pos['l_z'] = None
        self.pos['r_z'] = None
        try:
            self.z_offset = self._screen.klippy_config.getfloat("Variables", "e1_zoffset")
        except Exception as e:
                logging.error(f"Read {self._screen.klippy_config_path} error:\n{e}")        
        self.buttons_not_calibrating()
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen.show_popup_message(_("Need home axis"), level=1)
            self._screen._ws.klippy.gcode_script("G28")
            return
        if self.bed_mesh_profile is not None:
            self.send_clear_mesh(widget)

        self.buttons['start'].set_sensitive(False)
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        if current_extruder != "extruder":
            self.change_extruder(widget=None, extruder="extruder")
        self._calculate_position()
        self.is_start_calibrate = True
        self._screen._ws.klippy.gcode_script("QUERY_BUTTON button=zoffset_button")

    def activate(self):
        self.buttons_not_calibrating()
        self.bed_mesh_profile = self._printer.get_stat("bed_mesh", "profile_name")

    def deactivate(self):
        prifile_name = self._printer.get_stat("bed_mesh", "profile_name")
        if prifile_name != self.bed_mesh_profile and self.bed_mesh_profile is not None and self.bed_mesh_profile != "":
            self.send_load_mesh(widget=None, profile=self.bed_mesh_profile)

    def process_update(self, action, data):
        if action == "notify_status_update":
            if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.widgets['zposition'].set_text("Z: ?")
            elif "gcode_move" in data and "gcode_position" in data['gcode_move']:
                self.update_position(data['gcode_move']['gcode_position'])
                                   
        elif action == "notify_gcode_response":
            if "out of range" in data.lower():
                self._screen.show_popup_message(data)
                logging.info(data)
            elif "fail" in data.lower() and "use testz" in data.lower():
                self._screen.show_popup_message(_("Failed, adjust position first"))
                logging.info(data)
            elif "zoffset_button:" in data.lower():
                if self.zendstop > float(self.pos['z']):
                    return
                button_state = data.split()[-1].lower()
                if self.is_start_calibrate:
                    change_extruder_flag = False
                    if button_state == "pressed":
                        if True:
                            current_extruder = self._printer.get_stat("toolhead", "extruder")
                            if current_extruder == "extruder":
                                self.pos['l_z'] = self.pos['z']
                                change_extruder_flag = True
                            else:
                                self.pos['r_z'] = self.pos['z']
                            logging.info(f"{current_extruder} {self.pos['z']:.3f}")
                        script = f"G0 Z{10+self.pos['z']:.3f} F1200"
                        self._screen._send_action(None, "printer.gcode.script", {"script": script})
                    else:
                        script = f"G0 Z{-0.1 + self.pos['z']:.3f} F180"
                        self._screen._send_action(None, "printer.gcode.script", {"script": script})
                    if self.pos['l_z'] is None or self.pos['r_z'] is None:
                        if change_extruder_flag:
                            self.change_extruder(widget=None, extruder="extruder1")
                            self._calculate_position()
                    else:
                        self.is_start_calibrate = False
                        offset = self.pos['r_z'] - self.pos['l_z']
                        if self.z_offset is not None:
                            self.z_offset += offset
                        self.buttons_calibrating()
                    self._screen._ws.klippy.gcode_script("QUERY_BUTTON button=zoffset_button")            
        return

    def update_position(self, position):
        self.pos['z'] = position[2]
        self.widgets['zposition'].set_text(f"Z: {position[2]:.3f}")
        if self.z_offset is not None:
            self.widgets['zoffset'].set_text(f"{self.z_offset:.3f}")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.widgets[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.widgets[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move_to_target(self, widget, direction, distance):
        dist = f"{direction}{distance}"
        script = f"{KlippyGcodes.MOVE_RELATIVE}\nG0 Z{dist} F60"
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

    def move(self, widget, direction):
        self.move_to_target(widget, direction, self.distance)
        self.z_offset = self.z_offset - self.distance if direction == '-' else self.z_offset + self.distance

    def abort(self, widget):
        logging.info("Aborting calibration")
        self._screen._ws.klippy.gcode_script("ABORT")
        self.buttons_not_calibrating()
        self._screen._menu_go_back()

    def accept(self, widget):
        if self.z_offset is None or self._screen.klippy_config is None:
            return
        logging.info("Accepting right extruder Z offset")
        try:
            self._screen.klippy_config.set("Variables", "e1_zoffset", f"{self.z_offset:.2f}")
            logging.info(f"z offset change to z: {self.z_offset:.2f}")
            with open(self._screen.klippy_config_path, 'w') as file:
                self._screen.klippy_config.write(file)
                self.save_config()                    
                self._screen._menu_go_back()
        except Exception as e:
            logging.error(f"Error writing configuration file in {self._screen.klippy_config_path}:\n{e}")

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

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")        
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"T{self._printer.get_tool_number(extruder)}"})
        
    def _calculate_position(self):
        try:
            x_position = self._screen.klippy_config.getfloat("Variables", "switch_xpos")
            y_position = self._screen.klippy_config.getfloat("Variables", "switch_ypos")
            z_position = self._screen.klippy_config.getfloat("Variables", "switch_zpos")            
        except:
            logging.error("Couldn't get the calibration camera position.")
            self._screen.show_popup_message(_("Couldn't get the calibration camera position."), level=2)
            return

        logging.info(f"Moving to X:{x_position} Y:{y_position}")
        self._screen._ws.klippy.gcode_script(f'G0 Z{z_position} F3000')
        self._screen._ws.klippy.gcode_script(f'G0 X{x_position} Y{y_position} F3000')
        self.pos['z'] = z_position    
        
    def save_config(self):
        script = {"script": "SAVE_CONFIG"}
        self._screen._confirm_send_action(
            None,
            _("Saved successfully!") + "\n\n" + _("Need reboot, relaunch immediately?"),
            "printer.gcode.script",
            script
        )             

    def send_clear_mesh(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "BED_MESH_CLEAR"})    

    def send_load_mesh(self, widget, profile):
        self._screen._send_action(widget, "printer.gcode.script", {"script": KlippyGcodes.bed_mesh_load(profile)})        