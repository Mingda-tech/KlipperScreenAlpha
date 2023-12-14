#add by Sampson
import gi
import os
import pathlib
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)

        self.screen = screen
        self.bts = self._gtk.bsidescale
        self.themedir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", screen.theme, "images")
        self.cursor = screen.show_cursor
        self.font_size_type = screen._config.get_main_config().get("font_size", "medium")
        self.width = screen.width
        self.height = screen.height
        self.font_ratio = [33, 49] if self.screen.vertical_mode else [43, 29]
        self.font_size = min(self.width / self.font_ratio[0], self.height / self.font_ratio[1])
        self.img_scale = self.font_size * 2
        self.button_image_scale = 1.38
        self.bsidescale = .65  # Buttons with image at the side

        if self.font_size_type == "max":
            self.font_size = self.font_size * 1.2
            self.bsidescale = .7
        elif self.font_size_type == "extralarge":
            self.font_size = self.font_size * 1.14
            self.img_scale = self.img_scale * 0.7
            self.bsidescale = 1
        elif self.font_size_type == "large":
            self.font_size = self.font_size * 1.09
            self.img_scale = self.img_scale * 0.9
            self.bsidescale = .8
        elif self.font_size_type == "small":
            self.font_size = self.font_size * 0.91
            self.bsidescale = .55
        self.img_width = self.font_size * 3
        self.img_height = self.font_size * 3
        # self.print_mode = self._screen.klippy_config.getint("Variables", "printmode", fallback=0)

        # Create gtk items here
        self.buttons = {
            'autonomous': self._gtk.Button("autonomous", "Auto-park Mode", "color1"),
            'copy': self._gtk.Button("copy_disable", "Copy Mode", "color2"),
            'mirror': self._gtk.Button("mirror_disable", "Mirror Mode", "color3"),
        }

        self.buttons['autonomous'].connect("clicked", self.change_mode, 0)
        self.buttons['copy'].connect("clicked", self.change_mode, 1)
        self.buttons['mirror'].connect("clicked", self.change_mode, 2)

        grid = self._gtk.HomogeneousGrid()
        # grid.set_valign(Gtk.Align.CENTER)
        grid.attach(self.buttons['autonomous'], 0, 0, 1, 1)
        grid.attach(self.buttons['copy'], 0, 1, 1, 1)
        grid.attach(self.buttons['mirror'], 0, 2, 1, 1)    

        # self.change_mode(None, int(self.print_mode))
        self.change_mode(None, 0)
            
        self.content.add(grid)

        #self.content.add(Gtk.Box())

    def change_mode(self, widget, mode):
        filenames = ['autonomous', 'copy', 'mirror']
        for i in range(0,3):
            filename = filenames[i]
            if i == mode:
                filename += '.svg'
                # script = {"script": f'SET_PRINT_MODE MODE={i}'}
                script = {"script": f'M605 S{i+1}'}
                self.screen._send_action(None, "printer.gcode.script", script)
            else:
                filename += '_disable.svg'

            refresh_icon_filepath = os.path.join(self.themedir, filename)
            width = self.img_width
            height = self.img_height
            pixbuf =  GdkPixbuf.Pixbuf.new_from_file_at_size(refresh_icon_filepath, int(width), int(height))
            self.buttons[filenames[i]].set_image(Gtk.Image.new_from_pixbuf(pixbuf))
            logging.debug(f'width = {width}, height = {height}')
         