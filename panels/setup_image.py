import gi
import os
import pathlib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Pango
from ks_includes.screen_panel import ScreenPanel

klipperscreendir = pathlib.Path(__file__).parent.resolve().parent

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        
        # You can change this path to your desired image
        self.image_path = os.path.join(klipperscreendir, "ks_includes", "locales", "en", "manual", "setup.jpg")
        self.init_ui()

    def init_ui(self):
        grid = self._gtk.HomogeneousGrid()        
        
        # Back button
        back_btn = self._gtk.Button("arrow-left", None, "color1", .66)
        back_btn.connect("clicked", self.on_back_click)
        grid.attach(back_btn, 0, 0, 1, 1)
        
        # Next button
        next_btn = self._gtk.Button("arrow-right", None, "color1", .66)
        next_btn.connect("clicked", self.on_next_click)
        grid.attach(next_btn, 4, 0, 1, 1)
        
        tip_label = Gtk.Label()
        tip_label.set_markup(f'<span foreground="red">{_("Please remove the extruder foam and take out the door handle.")}</span>')
        # 设置自动换行以防止文字越界
        tip_label.set_line_wrap(True)
        tip_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        tip_label.set_justify(Gtk.Justification.CENTER)
        tip_label.set_hexpand(True)
        tip_label.set_halign(Gtk.Align.CENTER)
        grid.attach(tip_label, 1, 1, 3, 1)

        # Image display - adjust position to prevent offset
        self.image = Gtk.Image()
        self.update_image()
        grid.attach(self.image, 0, 2, 5, 4)  # Changed from (0, 2, 5, 8) to (0, 2, 5, 4)
        
        self.content.add(grid)
    
    def update_image(self):
        if os.path.exists(self.image_path):
            # Reduce image sizes to prevent overflow
            new_width = 700
            new_height = 350
            if self._screen.width == 1280 and self._screen.height == 800:
                new_width = 800
                new_height = 400
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

    def on_next_click(self, widget):
        # Move to the force move panel for Z axis
        self._screen.setup_init = 2
        self._screen.save_init_step()
        self._screen.show_panel("setup_force_move", _("Remove Foam"), remove_all=True)
    
    def on_back_click(self, widget):
        # Go back to language selection
        self._screen.show_panel("setup_wizard", _("Choose Language"), remove_all=True)