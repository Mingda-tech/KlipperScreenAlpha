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
        
        self.base_path = os.path.join(klipperscreendir, "ks_includes", "locales")
        self.current_lang = self._config.get_main_config().get("language", "en")
        self.printer_model = self.get_printer_model()
        self.image_path = self.get_image_path("remove_foam1.jpg")
        
        # Only initialize UI if image exists
        if os.path.exists(self.image_path):
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

        # Image display - adjust position to prevent offset
        self.image = Gtk.Image()
        self.update_image()
        grid.attach(self.image, 0, 1, 5, 4)  # Changed from (0, 2, 5, 8) to (0, 2, 5, 4)
        
        tip_label = Gtk.Label()
        tip_label.set_markup(f'<span foreground="red">{_("Please remove the extruder foam and take out the door handle.")}</span>')
        # 设置自动换行以防止文字越界
        tip_label.set_line_wrap(True)
        tip_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        tip_label.set_justify(Gtk.Justification.CENTER)
        tip_label.set_hexpand(True)
        tip_label.set_halign(Gtk.Align.CENTER)
        grid.attach(tip_label, 0, 5, 5, 1)
        
        self.content.add(grid)
    
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
    
    def get_image_path(self, image_name):
        # 如果没有识别到机型，直接返回不存在的路径
        if self.printer_model is None:
            return ""
            
        # 首先尝试获取当前语言和机型的图片路径
        lang_model_path = os.path.join(self.base_path, self.current_lang, "manual", self.printer_model, image_name)
        if os.path.exists(lang_model_path):
            return lang_model_path
        
        # 如果当前语言的图片不存在，尝试使用英语图片
        en_model_path = os.path.join(self.base_path, "en", "manual", self.printer_model, image_name)
        if os.path.exists(en_model_path):
            return en_model_path
            
        # 如果都不存在，返回空路径
        return ""

    def scale_image(self, filename, new_width, new_height):
        # Load the image from the file
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
        
        # Scale the Pixbuf
        scaled_pixbuf = pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)
        
        return scaled_pixbuf

    def on_next_click(self, widget):
        # Check if remove_foam2.jpg exists before moving to force move panel
        foam2_path = self.get_image_path("remove_foam2.jpg")
        if os.path.exists(foam2_path):
            # Move to the force move panel for Z axis
            if self._screen.setup_init < 3: 
                self._screen.setup_init = 3
            self._screen.save_init_step()
            self._screen.show_panel("setup_force_move", _("Remove Foam"), remove_all=True)
        else:
            # Skip to WiFi selection if remove_foam2.jpg doesn't exist
            if self._screen.setup_init < 4:
                self._screen.setup_init = 4
            self._screen.save_init_step()
            self._screen.show_panel("select_wifi", _("Select WiFi"), remove_all=True)
    
    def on_back_click(self, widget):
        # Go back to language selection
        self._screen.show_panel("setup_wizard", _("Choose Language"), remove_all=True)