import gi
import os
import pathlib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf
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
        
        # Empty space for first column (no back button since this is the first page)
        empty_space = Gtk.Label()
        grid.attach(empty_space, 0, 0, 1, 1)
        
        # Empty space for center columns (title is already in titlebar)
        empty_center = Gtk.Label()
        grid.attach(empty_center, 1, 0, 2, 1)
        
        # Next button
        next_btn = self._gtk.Button("arrow-right", None, "color1", .66)
        next_btn.connect("clicked", self.on_next_click)
        grid.attach(next_btn, 3, 0, 1, 1)
        
        # Image display
        self.image = Gtk.Image()
        self.update_image()
        grid.attach(self.image, 0, 1, 4, 5)
        
        self.content.add(grid)
    
    def update_image(self):
        if os.path.exists(self.image_path):
            new_width = 900
            new_height = 450
            if self._screen.width == 1280 and self._screen.height == 800:
                new_width = 1000
                new_height = 600
            elif self._screen.width == 800 and self._screen.height == 480:
                new_width = 600
                new_height = 320
            
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