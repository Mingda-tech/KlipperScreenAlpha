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
        
        # Create main grid layout
        main_grid = Gtk.Grid()
        main_grid.set_row_spacing(5)
        main_grid.set_column_spacing(5)
        main_grid.set_margin_start(20)
        main_grid.set_margin_end(20)
        main_grid.set_margin_top(20)
        main_grid.set_margin_bottom(20)

        # Left preview area
        preview_frame = Gtk.Frame()
        preview_frame.set_size_request(300, 300)
        
        # Create preview container
        preview_box = Gtk.Box()
        preview_box.set_size_request(300, 300)
        preview_box.set_halign(Gtk.Align.CENTER)
        preview_box.set_valign(Gtk.Align.CENTER)
        
        # Create preview image
        self.preview_image = Gtk.Image()
        self.preview_image.set_size_request(280, 280)  # Leave some margin
        
        preview_box.pack_start(self.preview_image, True, True, 10)
        preview_frame.add(preview_box)
        main_grid.attach(preview_frame, 0, 0, 1, 5)

        # Right info area
        info_grid = Gtk.Grid()
        info_grid.set_row_spacing(10)
        info_grid.set_column_spacing(10)
        info_grid.set_margin_start(20)

        # Filename
        filename_label = Gtk.Label(label=_("Filename:"), halign=Gtk.Align.START)
        self.filename_value = Gtk.Label(label="", halign=Gtk.Align.START)
        info_grid.attach(filename_label, 0, 0, 1, 1)
        info_grid.attach(self.filename_value, 1, 0, 1, 1)

        # Print height
        height_label = Gtk.Label(label=_("Print Height:"), halign=Gtk.Align.START)
        self.height_value = Gtk.Label(label="", halign=Gtk.Align.START)
        info_grid.attach(height_label, 0, 1, 1, 1)
        info_grid.attach(self.height_value, 1, 1, 1, 1)

        # Nozzle temperature
        nozzle_label = Gtk.Label(label=_("Nozzle Temp:"), halign=Gtk.Align.START)
        self.nozzle_value = Gtk.Label(label="", halign=Gtk.Align.START)
        info_grid.attach(nozzle_label, 0, 2, 1, 1)
        info_grid.attach(self.nozzle_value, 1, 2, 1, 1)

        # Bed temperature
        bed_label = Gtk.Label(label=_("Bed Temp:"), halign=Gtk.Align.START)
        self.bed_value = Gtk.Label(label="", halign=Gtk.Align.START)
        info_grid.attach(bed_label, 0, 3, 1, 1)
        info_grid.attach(self.bed_value, 1, 3, 1, 1)

        # Active extruder
        extruder_label = Gtk.Label(label=_("Active Extruder:"), halign=Gtk.Align.START)
        self.extruder_value = Gtk.Label(label="", halign=Gtk.Align.START)
        info_grid.attach(extruder_label, 0, 4, 1, 1)
        info_grid.attach(self.extruder_value, 1, 4, 1, 1)

        main_grid.attach(info_grid, 1, 0, 1, 5)

        # Resume print button
        resume_button = self._gtk.Button("resume", _("Resume Print"), "color2")
        resume_button.connect("clicked", self.resume_print)
        resume_button.set_size_request(200, 60)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.pack_start(resume_button, False, False, 0)
        main_grid.attach(button_box, 0, 5, 2, 1)

        # Tip message
        tip_label = Gtk.Label()
        tip_label.set_markup(
            f"<span foreground='orange'>{_('Tip: Please ensure the nozzle is about 0.1mm above the model')}</span>"
        )
        tip_label.set_halign(Gtk.Align.CENTER)
        main_grid.attach(tip_label, 0, 6, 2, 1)

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
            extruder_temp = int(float(config.get("temperatures", "extruder")))
            self.nozzle_value.set_label(f"{extruder_temp}℃")
            
            bed_temp = int(float(config.get("temperatures", "bed")))
            self.bed_value.set_label(f"{bed_temp}℃")
            
            # Get active extruder
            active_extruder = config.get("extruder", "active_extruder")
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
            pixbuf = self.get_file_image(self.filename, 280, 280)
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