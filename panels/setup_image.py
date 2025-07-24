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
        
        # Title - centered across the top
        title_label = Gtk.Label()
        title_label.set_text(_("Setup Wizard"))
        title_label.set_line_wrap(True)
        grid.attach(title_label, 1, 0, 3, 1)
        
        # Next button (no previous button since this is the first page)
        next_btn = self._gtk.Button("arrow-right", _("Next"), "color1", .66)
        next_btn.connect("clicked", self.on_next_click)
        grid.attach(next_btn, 4, 0, 1, 1)
        
        # Image display
        image = Gtk.Image()
        
        # Try to load image, if not found, show a placeholder
        if os.path.exists(self.image_path):
            new_width = 900
            new_height = 450
            if self._screen.width == 1280 and self._screen.height == 800:
                new_width = 1000
                new_height = 600
            elif self._screen.width == 800 and self._screen.height == 480:
                new_width = 600
                new_height = 320
            
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.image_path)
            # Scale the image to fit
            scaled_pixbuf = pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)
            image.set_from_pixbuf(scaled_pixbuf)
        else:
            # If image not found, show a placeholder text
            placeholder = Gtk.Label()
            placeholder.set_text(_("Setup image not found"))
            grid.attach(placeholder, 0, 1, 5, 5)
            self.content.add(grid)
            return
        
        grid.attach(image, 0, 1, 5, 5)
        self.content.add(grid)

    def on_next_click(self, widget):
        # Move to the force move panel for Z axis
        self._screen.setup_init = 2
        self._screen.save_init_step()
        self._screen.show_panel("setup_force_move", _("Remove Foam"), remove_all=True)