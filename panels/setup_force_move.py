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
        
        # Row 0: Previous button (1/6) + empty space + Next button (1/6)
        prev_btn = self._gtk.Button("arrow-left", None, "color1", .66)
        prev_btn.connect("clicked", self.on_previous_click)
        grid.attach(prev_btn, 0, 0, 1, 1)
        
        next_btn = self._gtk.Button("arrow-right", None, "color1", .66)
        next_btn.connect("clicked", self.on_next_click)
        grid.attach(next_btn, 4, 0, 1, 1)
        
        # Row 1: Z axis raise button (1/6 width, centered)
        z_up_image = "z-farther"
        z_up_label = _("Z Raise")
        if "MD_400D" in self._printer.get_gcode_macros():
            z_up_image = "bed_down"
            z_up_label = _("Bed Lower")
            
        self.z_raise_btn = self._gtk.Button(z_up_image, z_up_label, "color3", scale=1.5)
        self.z_raise_btn.connect("clicked", self.move_z_up)
        # Center the button by using columns 2-3 (middle third)
        grid.attach(self.z_raise_btn, 0, 1, 5, 2)
        
        # Row 3: Instruction text (2/6 width, centered)
        # Check if current language is not Chinese, use English
        instruction_text = _("Please click the Z raise button to raise the Z axis to remove the foam around the bottom of the case.")
            
        tip_label = Gtk.Label()
        tip_label.set_markup(f'<span foreground="red">{instruction_text}</span>')
        # 设置自动换行以防止文字越界
        tip_label.set_line_wrap(True)
        tip_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        tip_label.set_justify(Gtk.Justification.CENTER)
        tip_label.set_hexpand(True)
        tip_label.set_halign(Gtk.Align.CENTER)
        # Center the text using columns 2-3 (2/6 width)
        grid.attach(tip_label, 0, 3, 5, 3)
        

        
        self.content.add(grid)

    def change_distance(self, widget, dist):
        logging.info(f"Changing distance to {dist}")
        self.labels[self.distance].get_style_context().remove_class("distbutton_active")
        self.labels[dist].get_style_context().add_class("distbutton_active")
        self.distance = dist

    def move_z_up(self, widget):
        dist = 50.0
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

    def on_previous_click(self, widget):
        # Go back to the setup image
        self._screen.setup_init = 1
        self._screen.save_init_step()
        self._screen.show_panel("setup_image", _("Setup Wizard"), remove_all=True)
        
    def on_next_click(self, widget):
        # Continue to language selection
        self._screen.setup_init = 2
        self._screen.save_init_step()
        self._screen.show_panel("setup_wizard", _("Choose Language"), remove_all=True)