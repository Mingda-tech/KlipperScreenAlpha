import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    distances = ['10', '50']
    distance = distances[0]

    def __init__(self, screen, title):
        super().__init__(screen, title)

        # Enable Z stepper if not homed
        toolhead_status = self._printer.get_stat("toolhead")
        if toolhead_status:
            homed_axes = toolhead_status.get("homed_axes", "").upper()
            if "Z" not in homed_axes:
                logging.info("Setup Force Move: Z axis is not homed. Enabling stepper_z.")
                self._screen._send_action(None, "printer.gcode.script", {"script": "SET_STEPPER_ENABLE STEPPER=stepper_z ENABLE=1"})
                self._screen._send_action(None, "printer.gcode.script", {"script": "G4 P2000"})

        self.init_ui()

    def init_ui(self):
        grid = self._gtk.HomogeneousGrid()
        
        # Skip button
        skip_btn = self._gtk.Button(None, _("Skip"), "color1", .66)
        skip_btn.connect("clicked", self.on_skip_click)
        grid.attach(skip_btn, 0, 0, 1, 1)
        
        # Next button
        next_btn = self._gtk.Button("arrow-right", None, "color1", .66)
        next_btn.connect("clicked", self.on_next_click)
        grid.attach(next_btn, 4, 0, 1, 1)
        
        # Main instruction label with Chinese text
        instruction_text = "请点击Z raise按钮，以便取出泡棉"
        # Check if current language is not Chinese, use English
        if self._config.get_main_config().get("language", "en") not in ["zh", "zh_CN", "zh_TW"]:
            instruction_text = "Please click Z raise button to remove foam"
            
        instruction_label = Gtk.Label()
        instruction_label.set_markup(f"<big><b>{instruction_text}</b></big>")
        instruction_label.set_line_wrap(True)
        instruction_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        instruction_label.set_halign(Gtk.Align.CENTER)
        instruction_label.set_valign(Gtk.Align.CENTER)
        grid.attach(instruction_label, 0, 1, 5, 2)
        
        # Z axis raise button
        z_up_image = "z-farther"
        z_up_label = _("Z Raise")
        if "MD_400D" in self._printer.get_gcode_macros():
            z_up_image = "bed_down"
            z_up_label = _("Bed Lower")
            
        self.z_raise_btn = self._gtk.Button(z_up_image, z_up_label, "color3", scale=2)
        self.z_raise_btn.connect("clicked", self.move_z_up)
        grid.attach(self.z_raise_btn, 1, 3, 3, 2)
        
        # Distance selection label
        dist_label = Gtk.Label()
        distance_text = "距离:" if self._config.get_main_config().get("language", "en") in ["zh", "zh_CN", "zh_TW"] else "Distance:"
        dist_label.set_text(distance_text)
        dist_label.set_halign(Gtk.Align.END)
        grid.attach(dist_label, 0, 5, 2, 1)
        
        # Distance buttons
        dist_grid = self._gtk.HomogeneousGrid()
        for i, dist in enumerate(self.distances):
            self.labels[f"dist{dist}"] = self._gtk.Button(label=f"{dist}mm")
            self.labels[f"dist{dist}"].connect("clicked", self.change_distance, dist)
            if dist == self.distance:
                self.labels[f"dist{dist}"].get_style_context().add_class("button_active")
            dist_grid.attach(self.labels[f"dist{dist}"], i, 0, 1, 1)
        grid.attach(dist_grid, 2, 5, 2, 1)
        
        self.content.add(grid)

    def change_distance(self, widget, dist):
        logging.info(f"Changing distance to {dist}")
        self.labels[f"dist{self.distance}"].get_style_context().remove_class("button_active")
        self.labels[f"dist{dist}"].get_style_context().add_class("button_active")
        self.distance = dist

    def move_z_up(self, widget):
        dist = float(self.distance)
        speed = 2  # Z speed in mm/s
        
        # Check if Z is homed
        toolhead_status = self._printer.get_stat("toolhead")
        if toolhead_status:
            homed_axes = toolhead_status.get("homed_axes", "").upper()
            if "Z" in homed_axes:
                # Use normal G-code if homed
                logging.info(f"Moving Z up by {dist}mm at {speed}mm/s (homed)")
                self._screen._send_action(None, "printer.gcode.script", 
                    {"script": f"G91\nG0 Z{dist} F{speed*60}\nG90"})
            else:
                # Use force move if not homed
                logging.info(f"Force moving Z up by {dist}mm at {speed}mm/s (not homed)")
                if dist >= 2:
                    accel = 60
                    self._screen._send_action(None, "printer.gcode.script",
                        {"script": f"FORCE_MOVE STEPPER=stepper_z DISTANCE={dist} VELOCITY={speed} ACCEL={accel}"})
                else:
                    self._screen._send_action(None, "printer.gcode.script",
                        {"script": f"FORCE_MOVE STEPPER=stepper_z DISTANCE={dist} VELOCITY={speed}"})

    def on_skip_click(self, widget):
        self._screen.show_panel("main_menu", None, remove_all=True, items=self._config.get_menu_items("__main"))
        
    def on_next_click(self, widget):
        # Continue to language selection
        self._screen.setup_init = 3
        self._screen.save_init_step()
        self._screen.show_panel("setup_wizard", _("Choose Language"), remove_all=True)