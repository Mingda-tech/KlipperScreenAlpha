import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.buttons = {}
        
        # Create a grid for all buttons
        self.labels['buttons'] = Gtk.Grid()
        self.labels['buttons'].set_valign(Gtk.Align.CENTER)
        self.labels['buttons'].set_column_spacing(10)
        self.labels['buttons'].set_row_spacing(10)
        
        self.load_gcode_buttons()
        
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['buttons'])
        
        self.content.add(scroll)
    
    def load_gcode_buttons(self):
        # Get all gcode_button sections from config
        gcode_buttons = self.get_gcode_buttons()
        
        if not gcode_buttons:
            label = Gtk.Label(_("No Gcode Buttons configured"))
            label.set_hexpand(True)
            label.set_vexpand(True)
            label.set_halign(Gtk.Align.CENTER)
            label.set_valign(Gtk.Align.CENTER)
            self.labels['buttons'].attach(label, 0, 0, 1, 1)
            return
            
        col = 0
        row = 0
        for button_name in gcode_buttons:
            # Support for hiding buttons by name
            if button_name.startswith("_"):
                continue
            self.add_button(button_name, row, col)
            col += 1
            if col >= 2:  # 2 columns layout
                col = 0
                row += 1
    
    def get_gcode_buttons(self):
        """Get list of gcode_button sections from printer config"""
        buttons = []
        config_sections = self._printer.get_config_section_list("gcode_button ")
        for section in config_sections:
            # Extract button name from section (e.g., "gcode_button t0_cutter_sensor" -> "t0_cutter_sensor")
            button_name = section.replace("gcode_button ", "")
            buttons.append(button_name)
        return buttons
    
    def add_button(self, button_name, row, col):
        logging.info(f"Adding gcode button: {button_name}")
        
        # Create button container
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        button_box.set_hexpand(True)
        button_box.set_vexpand(True)
        
        # Button label
        label = Gtk.Label()
        label.set_markup(f'<b>{button_name}</b>')
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        button_box.add(label)
        
        # Get button state from printer
        button_state = self.get_button_state(button_name)
        
        # Create action buttons
        btn_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_container.set_halign(Gtk.Align.CENTER)
        
        # Press button
        press_btn = self._gtk.Button("arrow-down", _("Press"), "color2", self.bts)
        press_btn.connect("clicked", self.trigger_button, button_name, "press")
        btn_container.add(press_btn)
        
        # Release button
        release_btn = self._gtk.Button("arrow-up", _("Release"), "color3", self.bts)
        release_btn.connect("clicked", self.trigger_button, button_name, "release")
        btn_container.add(release_btn)
        
        button_box.add(btn_container)
        
        # Status label
        status_label = Gtk.Label()
        status_label.set_markup(f'<small>{_("State")}: {button_state}</small>')
        button_box.add(status_label)
        
        self.buttons[button_name] = {
            "box": button_box,
            "status": status_label,
            "press_btn": press_btn,
            "release_btn": release_btn
        }
        
        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")
        frame.add(button_box)
        
        self.labels['buttons'].attach(frame, col, row, 1, 1)
        self.labels['buttons'].show_all()
    
    def get_button_state(self, button_name):
        """Get current state of gcode button"""
        # Check if button state is available in printer data
        button_key = f"gcode_button {button_name}"
        if button_key in self._printer.data:
            state = self._printer.data[button_key].get("state", "UNKNOWN")
            return _("Pressed") if state == "PRESSED" else _("Released")
        return _("Unknown")
    
    def trigger_button(self, widget, button_name, action):
        """Trigger press or release gcode for button"""
        logging.info(f"Triggering {action} for button {button_name}")
        
        # Get the gcode from config
        section = f"gcode_button {button_name}"
        config = self._printer.get_config_section(section)
        
        if config:
            gcode_key = f"{action}_gcode"
            if gcode_key in config:
                # Execute the gcode
                gcode = config[gcode_key]
                if gcode and gcode.strip():
                    # Parse multiline gcode
                    for line in gcode.split('\n'):
                        line = line.strip()
                        if line:
                            self._screen._ws.klippy.gcode_script(line)
            else:
                self._screen.show_popup_message(
                    _(f"No {action} gcode configured for {button_name}"),
                    level=2
                )
    
    def process_update(self, action, data):
        """Handle printer status updates"""
        if action != "notify_status_update":
            return
        
        # Update button states
        for button_name in self.buttons:
            button_key = f"gcode_button {button_name}"
            if button_key in data:
                state = data[button_key].get("state", "UNKNOWN")
                state_text = _("Pressed") if state == "PRESSED" else _("Released")
                self.buttons[button_name]["status"].set_markup(
                    f'<small>{_("State")}: {state_text}</small>'
                )