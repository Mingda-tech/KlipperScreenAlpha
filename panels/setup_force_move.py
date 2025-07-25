import logging
import gi
import os
import pathlib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Pango
from ks_includes.screen_panel import ScreenPanel

klipperscreendir = pathlib.Path(__file__).parent.resolve().parent

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
        self.image_path = os.path.join(klipperscreendir, "ks_includes", "locales", "en", "manual", "remove_foam2.jpg")
        self.init_ui()

    def init_ui(self):
        grid = self._gtk.HomogeneousGrid()
        
        # Row 0: Previous button (1/6) + empty space + Next button (1/6)
        prev_btn = self._gtk.Button("arrow-left", None, "color1", .66)
        prev_btn.connect("clicked", self.on_previous_click)
        grid.attach(prev_btn, 0, 0, 1, 1)
        
        z_up_image = "z-farther"
        z_up_label = _("Z Raise")
        if "MD_400D" in self._printer.get_gcode_macros():
            z_up_image = "bed_down"
            z_up_label = _("Bed Lower")
            
        self.z_raise_btn = self._gtk.Button(z_up_image, z_up_label, "color3", scale=1.5)
        self.z_raise_btn.connect("clicked", self.move_z_up)
        grid.attach(self.z_raise_btn, 2, 0, 1, 1)
        
        self.next_btn = self._gtk.Button("arrow-right", None, "color1", .66)
        self.next_btn.connect("clicked", self.on_next_click)
        grid.attach(self.next_btn, 4, 0, 1, 1)
        
        self.image = Gtk.Image()
        self.update_image()
        grid.attach(self.image, 0, 1, 5, 4)

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
        grid.attach(tip_label, 0, 5, 5, 1)
        
        if self._screen.setup_init == 3:
            self.next_btn.set_sensitive(False)
            self.z_raise_btn.set_sensitive(True)
        else:
            self.next_btn.set_sensitive(True)
            self.z_raise_btn.set_sensitive(False)
        
        self.content.add(grid)

    def change_distance(self, widget, dist):
        logging.info(f"Changing distance to {dist}")
        self.labels[self.distance].get_style_context().remove_class("distbutton_active")
        self.labels[dist].get_style_context().add_class("distbutton_active")
        self.distance = dist

    def move_z_up(self, widget):
        dist = 70.0
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
        
        # Disable the z_raise button after clicking
        self.z_raise_btn.set_sensitive(False)
        # Enable the next button
        self.next_btn.set_sensitive(True)

    def on_previous_click(self, widget):
        # Go back to the setup image
        self._screen.save_init_step()
        self._screen.show_panel("setup_image", _("Remove Foam"), remove_all=True)
        
    def on_next_click(self, widget):
        # Continue to language selection
        if self._screen.setup_init < 4:
            self._screen.setup_init = 4
        self._screen.save_init_step()
        self._screen.show_panel("select_wifi", _("Select WiFi"), remove_all=True)

    def update_image(self):
        if os.path.exists(self.image_path):
            # Reduce image sizes to prevent overflow
            new_width = 700
            new_height = 350
            if self._screen.width == 1280 and self._screen.height == 800:
                new_width = 1000
                new_height = 480
            elif self._screen.width == 800 and self._screen.height == 480:
                new_width = 500
                new_height = 250
            
            scaled_pixbuf = self.scale_image(self.image_path, new_width, new_height)
            self.image.set_from_pixbuf(scaled_pixbuf)
        else:
            # If image not found, show a placeholder
            self.image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
    
    def scale_image(self, filename, new_width, new_height):
        # Load the image from the file
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
        
        # Scale the Pixbuf
        scaled_pixbuf = pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)
        
        return scaled_pixbuf        