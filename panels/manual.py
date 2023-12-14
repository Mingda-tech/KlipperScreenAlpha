import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)

        self.folder_path = "/home/mingda/printer_data/resources/manual"
        self.image_files = self.load_images()
        self.current_image_index = 0
        # self.bts = self._gtk.bsidescale
        if self.image_files:
            self.init_ui()       

    def init_ui(self):
        grid = self._gtk.HomogeneousGrid()
        back_btn = self._gtk.Button("arrow-left", None, "color1", .66)
        back_btn.connect("clicked", self.on_back_clicked)
        grid.attach(back_btn, 0, 0, 1, 1)        

        self.label = Gtk.Label()
        self.update_label()
        grid.attach(self.label, 1, 0, 2, 1)

        next_btn = self._gtk.Button("arrow-right", None, "color1", .66)
        next_btn.connect("clicked", self.on_next_clicked)
        grid.attach(next_btn, 3, 0, 1, 1)

        self.image = Gtk.Image()
        self.update_image()
        grid.attach(self.image, 0, 1, 4, 5)
        
        self.content.add(grid)

    def load_images(self):
        image_files = []
        if os.path.exists(self.folder_path):
            for filename in os.listdir(self.folder_path):
                if filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image_files.append(os.path.join(self.folder_path, filename))
            image_files.sort()
        return image_files

    def update_image(self):
        if self.image_files:
            filename = self.image_files[self.current_image_index]
            new_width = 900
            new_height = 450
            scaled_pixbuf = scale_image(filename, new_width, new_height)
            # pixbuf = GdkPixbuf.Pixbuf.new_from_file()
            self.image.set_from_pixbuf(scaled_pixbuf)

    def update_label(self):
        total_images = len(self.image_files)
        current_image_num = self.current_image_index + 1
        self.label.set_text(f"Page {current_image_num} of {total_images}")

    def on_back_clicked(self, widget):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.update_image()
            self.update_label()

    def on_next_clicked(self, widget):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.update_image()
            self.update_label()

def scale_image(filename, new_width, new_height):
    # Load the image from the file
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)

    # Calculate the scaling factors
    original_width = pixbuf.get_width()
    original_height = pixbuf.get_height()
    scale_x = float(new_width) / original_width
    scale_y = float(new_height) / original_height

    # Scale the Pixbuf
    scaled_pixbuf = pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)

    return scaled_pixbuf