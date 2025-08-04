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
        
        self.base_path = os.path.join(klipperscreendir, "ks_includes", "locales")
        self.current_lang = self._config.get_main_config().get("language", "en")
        self.printer_model = self.get_printer_model()
        self.folder_path = self.get_manual_path()
        self.image_files = self.load_images()
        self.current_image_index = 0
        if self.image_files:
            self.init_ui()

    def get_printer_model(self):
        # 获取打印机型号
        if "MD_1000D" in self._printer.available_commands:
            return "1000D"
        elif "MD_600D" in self._printer.available_commands:
            return "600D"
        elif "MD_600PRO" in self._printer.available_commands:
            return "600PRO"
        elif "MD_1000PRO" in self._printer.available_commands:
            return "1000PRO"
        elif "MD_400D" in self._printer.available_commands:
            return "400D"
        return None  # 没有识别到的机型

    def get_manual_path(self):
        # 如果没有识别到机型，返回不存在的路径
        if self.printer_model is None:
            return ""
            
        # 首先尝试获取当前语言和机型的手册路径
        lang_model_path = os.path.join(self.base_path, self.current_lang, "manual", self.printer_model)
        if os.path.exists(lang_model_path):
            return lang_model_path
        
        # 如果当前语言的手册不存在，尝试使用英语手册
        en_model_path = os.path.join(self.base_path, "en", "manual", self.printer_model)
        if os.path.exists(en_model_path):
            return en_model_path
            
        # 如果都不存在，返回空路径
        return ""

    def update_language(self, lang_code):
        """当语言改变时更新手册"""
        self.current_lang = lang_code
        self.folder_path = self.get_manual_path()
        self.image_files = self.load_images()
        self.current_image_index = 0
        if self.image_files:
            self.update_image()
            self.update_label()

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
            if self._screen.width == 1280 and self._screen.height == 800:
                new_width = 1000
                new_height = 600
            elif self._screen.width == 800 and self._screen.height == 480:
                new_width = 600
                new_height = 320
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
        if self.current_image_index == len(self.image_files) - 1 and self._screen.setup_init == 1 and self._screen.is_show_manual:
            self._screen.is_show_manual = False
            self._screen.show_panel("setup_wizard", _("Choose Language"), remove_all=True)
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