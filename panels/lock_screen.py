import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    """Lock screen panel with PIN entry"""
    
    def __init__(self, screen, title, default_pin="1234"):
        super().__init__(screen, title)
        self.default_pin = default_pin
        self.entered_pin = ""
        
        # Main container
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main.set_halign(Gtk.Align.CENTER)
        main.set_valign(Gtk.Align.CENTER)
        main.set_vexpand(True)
        main.set_hexpand(True)
        
        # Lock icon
        lock_icon = self._gtk.Image("lock", self._gtk.content_width * .15, self._gtk.content_height * .25)
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon_box.pack_start(lock_icon, False, False, 20)
        
        # Title label
        self.labels['title'] = Gtk.Label(_("Screen Locked"))
        self.labels['title'].set_line_wrap(True)
        self.labels['title'].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.labels['title'].set_halign(Gtk.Align.CENTER)
        self.labels['title'].set_valign(Gtk.Align.CENTER)
        title_ctx = self.labels['title'].get_style_context()
        title_ctx.add_class("lock-screen-title")
        
        # PIN display (masked)
        self.labels['pin_display'] = Gtk.Label("")
        self.labels['pin_display'].set_halign(Gtk.Align.CENTER)
        self.labels['pin_display'].set_valign(Gtk.Align.CENTER)
        pin_ctx = self.labels['pin_display'].get_style_context()
        pin_ctx.add_class("lock-screen-pin")
        self.update_pin_display()
        
        # Info label
        self.labels['info'] = Gtk.Label(_("Enter PIN to unlock"))
        self.labels['info'].set_halign(Gtk.Align.CENTER)
        self.labels['info'].set_valign(Gtk.Align.CENTER)
        info_ctx = self.labels['info'].get_style_context()
        info_ctx.add_class("lock-screen-info")
        
        # Create numpad
        numpad = self.create_numpad()
        
        # Pack everything
        main.pack_start(icon_box, False, False, 0)
        main.pack_start(self.labels['title'], False, False, 0)
        main.pack_start(self.labels['pin_display'], False, False, 10)
        main.pack_start(self.labels['info'], False, False, 0)
        main.pack_start(numpad, False, False, 20)
        
        self.content.add(main)
    
    def create_numpad(self):
        """Create numeric keypad for PIN entry"""
        numpad = Gtk.Grid()
        numpad.set_row_spacing(10)
        numpad.set_column_spacing(10)
        numpad.set_halign(Gtk.Align.CENTER)
        numpad.set_valign(Gtk.Align.CENTER)
        
        # Button size
        button_size = min(self._gtk.content_width, self._gtk.content_height) // 5
        
        # Number buttons 1-9
        for i in range(1, 10):
            button = Gtk.Button(label=str(i))
            button.set_size_request(button_size, button_size)
            button.connect('clicked', self.on_number_clicked, str(i))
            ctx = button.get_style_context()
            ctx.add_class("lock-screen-button")
            row = (i - 1) // 3
            col = (i - 1) % 3
            numpad.attach(button, col, row, 1, 1)
        
        # Bottom row: Clear, 0, Enter
        clear_button = Gtk.Button(label=_("Clear"))
        clear_button.set_size_request(button_size, button_size)
        clear_button.connect('clicked', self.on_clear_clicked)
        ctx = clear_button.get_style_context()
        ctx.add_class("lock-screen-button")
        numpad.attach(clear_button, 0, 3, 1, 1)
        
        zero_button = Gtk.Button(label="0")
        zero_button.set_size_request(button_size, button_size)
        zero_button.connect('clicked', self.on_number_clicked, "0")
        ctx = zero_button.get_style_context()
        ctx.add_class("lock-screen-button")
        numpad.attach(zero_button, 1, 3, 1, 1)
        
        enter_button = Gtk.Button(label=_("Enter"))
        enter_button.set_size_request(button_size, button_size)
        enter_button.connect('clicked', self.on_enter_clicked)
        ctx = enter_button.get_style_context()
        ctx.add_class("lock-screen-button")
        ctx.add_class("color3")
        numpad.attach(enter_button, 2, 3, 1, 1)
        
        return numpad
    
    def on_number_clicked(self, widget, number):
        """Handle number button click"""
        if len(self.entered_pin) < 6:  # Limit PIN length to 6 digits
            self.entered_pin += number
            self.update_pin_display()
    
    def on_clear_clicked(self, widget):
        """Handle clear button click"""
        self.entered_pin = ""
        self.update_pin_display()
        self.labels['info'].set_text(_("Enter PIN to unlock"))
        info_ctx = self.labels['info'].get_style_context()
        info_ctx.remove_class("lock-screen-error")
    
    def on_enter_clicked(self, widget):
        """Handle enter button click - validate PIN"""
        if self.entered_pin == self.default_pin:
            # PIN correct, unlock screen
            self._screen.close_lock_screen()
        else:
            # PIN incorrect, show error
            self.labels['info'].set_text(_("Incorrect PIN"))
            info_ctx = self.labels['info'].get_style_context()
            info_ctx.add_class("lock-screen-error")
            self.entered_pin = ""
            self.update_pin_display()
    
    def update_pin_display(self):
        """Update PIN display with masked characters"""
        # Show dots for each entered digit
        display = "● " * len(self.entered_pin)
        self.labels['pin_display'].set_text(display.strip())
