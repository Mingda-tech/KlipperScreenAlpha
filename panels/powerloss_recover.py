# -*- coding: utf-8 -*-
import logging
import gi
import os
import configparser

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.menu = ['powerloss_recover']
        self.filename = None
        self.print_state_file = "/home/mingda/printer_data/config/print_state.cfg"
        
        # Calculate sizes based on screen resolution
        self.width = screen.width
        self.height = screen.height
        
        # Calculate optimal sizes
        self.preview_size = min(self.width // 3, self.height // 2)  # 预览图尺寸不超过屏幕宽度的1/3和高度的1/2
        self.button_height = self.height // 12  # 按钮高度为屏幕高度的1/12
        self.margin = min(20, self.width // 50)  # 边距最大20，或屏幕宽度的1/50
        
        # Create main grid layout
        main_grid = Gtk.Grid()
        main_grid.set_row_spacing(self.margin // 2)
        main_grid.set_column_spacing(self.margin)
        main_grid.set_margin_start(self.margin)
        main_grid.set_margin_end(self.margin)
        main_grid.set_margin_top(self.margin)
        main_grid.set_margin_bottom(self.margin)

        # Left preview area and button container
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.margin)
        left_box.set_halign(Gtk.Align.CENTER)
        
        # Preview frame
        preview_frame = Gtk.Frame()
        preview_frame.set_size_request(self.preview_size, self.preview_size)
        
        # Create preview container
        preview_box = Gtk.Box()
        preview_box.set_size_request(self.preview_size, self.preview_size)
        preview_box.set_halign(Gtk.Align.CENTER)
        preview_box.set_valign(Gtk.Align.CENTER)
        
        # Create preview image
        self.preview_image = Gtk.Image()
        self.preview_image.set_size_request(self.preview_size - self.margin, 
                                          self.preview_size - self.margin)
        
        preview_box.pack_start(self.preview_image, True, True, self.margin // 2)
        preview_frame.add(preview_box)
        left_box.pack_start(preview_frame, False, False, 0)

        # Resume print button
        resume_button = self._gtk.Button("resume", _("Resume Print"), "color2")
        resume_button.connect("clicked", self.resume_print)
        resume_button.set_size_request(min(self.preview_size, 200), self.button_height)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.pack_start(resume_button, False, False, 0)
        left_box.pack_start(button_box, False, False, 0)

        main_grid.attach(left_box, 0, 0, 1, 6)

        # Right info area
        info_grid = Gtk.Grid()
        info_grid.set_row_spacing(self.margin)
        info_grid.set_column_spacing(self.margin)
        info_grid.set_margin_start(self.margin)
        info_grid.set_vexpand(True)  # 允许垂直扩展
        info_grid.set_valign(Gtk.Align.FILL)  # 填充整个可用空间
        info_grid.set_size_request(-1, self.preview_size)  # 设置与预览图相同的高度
        
        # Calculate label sizes
        label_width = (self.width - self.preview_size - self.margin * 6) // 2
        info_height = self.preview_size  # 与预览图等高
        row_height = (info_height - self.margin * 5) // 6  # 6行信息，5个间隔
        
        # Filename (占用两列宽度)
        filename_label = Gtk.Label(label=_("Filename:"), halign=Gtk.Align.START)
        filename_label.set_size_request(label_width, -1)
        filename_label.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(filename_label, 0, 0, 2, 1)
        
        self.filename_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.filename_value.set_size_request(label_width * 2, -1)  # 两倍宽度
        self.filename_value.set_line_wrap(True)
        self.filename_value.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.filename_value.set_justify(Gtk.Justification.LEFT)
        self.filename_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(self.filename_value, 0, 1, 2, 1)  # 占用下一行的两列

        # Print height
        height_label = Gtk.Label(label=_("Print Height:"), halign=Gtk.Align.START)
        height_label.set_size_request(label_width, -1)
        height_label.set_vexpand(True)  # 允许垂直扩展
        self.height_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.height_value.set_size_request(label_width, -1)
        self.height_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(height_label, 0, 2, 1, 1)
        info_grid.attach(self.height_value, 1, 2, 1, 1)

        # Nozzle temperature
        nozzle_label = Gtk.Label(label=_("Nozzle Temp:"), halign=Gtk.Align.START)
        nozzle_label.set_size_request(label_width, -1)
        nozzle_label.set_vexpand(True)  # 允许垂直扩展
        self.nozzle_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.nozzle_value.set_size_request(label_width, -1)
        self.nozzle_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(nozzle_label, 0, 3, 1, 1)
        info_grid.attach(self.nozzle_value, 1, 3, 1, 1)

        # Bed temperature
        bed_label = Gtk.Label(label=_("Bed Temp:"), halign=Gtk.Align.START)
        bed_label.set_size_request(label_width, -1)
        bed_label.set_vexpand(True)  # 允许垂直扩展
        self.bed_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.bed_value.set_size_request(label_width, -1)
        self.bed_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(bed_label, 0, 4, 1, 1)
        info_grid.attach(self.bed_value, 1, 4, 1, 1)

        # Active extruder
        extruder_label = Gtk.Label(label=_("Active Extruder:"), halign=Gtk.Align.START)
        extruder_label.set_size_request(label_width, -1)
        extruder_label.set_vexpand(True)  # 允许垂直扩展
        self.extruder_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.extruder_value.set_size_request(label_width, -1)
        self.extruder_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(extruder_label, 0, 5, 1, 1)
        info_grid.attach(self.extruder_value, 1, 5, 1, 1)

        # Set properties for all labels
        for child in info_grid.get_children():
            if isinstance(child, Gtk.Label):
                child.set_line_wrap(True)
                child.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                child.set_valign(Gtk.Align.CENTER)  # 垂直居中对齐

        main_grid.attach(info_grid, 1, 0, 1, 6)

        # Tip message (占满整行)
        tip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tip_box.set_hexpand(True)  # 水平方向扩展
        tip_box.set_halign(Gtk.Align.FILL)
        
        tip_label = Gtk.Label()
        tip_label.set_markup(
            f"<span foreground='orange'>{_('Tip: Please ensure the nozzle is about 0.1mm above the model')}</span>"
        )
        tip_label.set_halign(Gtk.Align.CENTER)
        tip_label.set_hexpand(True)  # 标签也设置为扩展
        tip_label.set_line_wrap(True)
        tip_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        tip_label.set_justify(Gtk.Justification.CENTER)
        
        tip_box.pack_start(tip_label, True, True, 0)
        main_grid.attach(tip_box, 0, 6, 2, 1)

        # Make the main grid expand to fill available space
        main_grid.set_vexpand(True)
        main_grid.set_hexpand(True)
        
        self.content.add(main_grid)
        
        # Load power loss recovery info on initialization
        self.load_powerloss_info()

    def load_powerloss_info(self):
        """Load power loss recovery information"""
        if not os.path.exists(self.print_state_file):
            logging.error(f"Print state file not found: {self.print_state_file}")
            return
            
        try:
            config = configparser.ConfigParser()
            config.read(self.print_state_file)
            
            # Get file information
            self.filename = config.get("print_state", "file_path")
            self.filename_value.set_label(os.path.basename(self.filename))
            
            # Get position information
            z_position = float(config.get("position", "z"))
            self.height_value.set_label(f"{z_position:.2f} mm")
            
            # Get temperature information
            # 检查配置文件中的温度节点名称
            if config.has_option("temperatures", "extruder1"):
                extruder_temp = int(float(config.get("temperatures", "extruder1")))
            elif config.has_option("temperatures", "extruder"):
                extruder_temp = int(float(config.get("temperatures", "extruder")))
            else:
                extruder_temp = 0
            self.nozzle_value.set_label(f"{extruder_temp}℃")
            
            bed_temp = int(float(config.get("temperatures", "bed", fallback="0")))
            self.bed_value.set_label(f"{bed_temp}℃")
            
            # Get active extruder
            active_extruder = config.get("extruder", "active_extruder", fallback="extruder")
            self.extruder_value.set_label(active_extruder)
            
            # Update preview image
            self.update_preview_image()
            
        except Exception as e:
            logging.exception(f"Failed to load power loss recovery info: {str(e)}")

    def get_file_image(self, filename, width, height):
        """Get file preview image"""
        if filename is None:
            return None
            
        # Try to get thumbnail
        if self._files.has_thumbnail(filename):
            return self._files.get_thumbnail(filename, width, height)
        return None

    def update_preview_image(self):
        """Update preview image"""
        try:
            if self.filename is None:
                self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
                return
                
            # Get preview image
            pixbuf = self.get_file_image(self.filename, self.preview_size - self.margin,
                                        self.preview_size - self.margin)
            if pixbuf is not None:
                self.preview_image.set_from_pixbuf(pixbuf)
            else:
                self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
        except Exception as e:
            logging.exception(f"Failed to load preview image: {str(e)}")
            self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

    def resume_print(self, widget):
        """Resume printing"""
        if self.filename is None:
            return
            
        logging.info("Starting to resume print...")
        
        # Send resume print command
        self._screen._ws.klippy.gcode_script(
            f"RESTORE_PRINT"
        )
        
        # Switch to print status panel
        self._screen._menu_go_back() 