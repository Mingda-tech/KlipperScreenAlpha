import logging
import gi
import json

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, Gdk
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title, message=None, result=None):
        super().__init__(screen, title)
        self.message = message
        self.result = result
        
        # Create main layout with padding
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main.set_vexpand(True)
        main.set_hexpand(True)
        main.set_margin_start(15)
        main.set_margin_end(15)
        main.set_margin_top(15)
        main.set_margin_bottom(15)
        
        # Add warning icon and title in a horizontal box
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.set_halign(Gtk.Align.CENTER)
        header.set_valign(Gtk.Align.CENTER)
        
        # Add warning icon
        warning_icon = self._gtk.Image("warning", 45, 45)
        header.add(warning_icon)
        
        # Add title with red color
        title_label = Gtk.Label()
        title_label.set_markup(f'<span foreground="#FF5555" font="Sans Bold 24">{_("AI Detection Warning")}</span>')
        title_label.set_line_wrap(True)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_valign(Gtk.Align.CENTER)
        header.add(title_label)
        
        main.add(header)
        
        # Add separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("separator")
        main.add(separator)
        
        # Add detection result info in a frame
        if message:
            info_frame = Gtk.Frame()
            info_frame.get_style_context().add_class("ai-info-frame")
            
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            info_box.set_margin_start(20)
            info_box.set_margin_end(20)
            info_box.set_margin_top(20)
            info_box.set_margin_bottom(20)
            
            info_label = Gtk.Label()
            info_label.set_markup(f'<span font="Sans 18">{message}</span>')
            info_label.set_line_wrap(True)
            info_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            info_label.set_halign(Gtk.Align.CENTER)
            info_label.set_valign(Gtk.Align.CENTER)
            info_box.add(info_label)
            
            info_frame.add(info_box)
            main.add(info_frame)
        
        # Add thumbnail if exists
        if result and "image_url" in result:
            image_frame = Gtk.Frame()
            image_frame.get_style_context().add_class("ai-image-frame")
            
            image = self._gtk.Image("file", self._gtk.content_width * .7, self._gtk.content_height * .4)
            image.set_from_url(result["image_url"])
            image_frame.add(image)
            main.add(image_frame)
        
        # Add action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_valign(Gtk.Align.CENTER)
        button_box.set_margin_top(10)
        button_box.set_hexpand(True)  # Make button box expandable
        
        # Resume print button
        self.resume_button = self._gtk.Button("resume", _("Resume Print"), "color1")
        self.resume_button.connect("clicked", self.resume_print)
        self.resume_button.set_hexpand(True)  # Make button expand horizontally
        button_box.add(self.resume_button)
        
        # Cancel print button
        self.cancel_button = self._gtk.Button("cancel", _("Cancel Print"), "color3")
        self.cancel_button.connect("clicked", self.cancel_print)
        self.cancel_button.set_hexpand(True)  # Make button expand horizontally
        button_box.add(self.cancel_button)
        
        main.add(button_box)
        
        # Add separator before feedback section
        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator2.get_style_context().add_class("separator")
        main.add(separator2)
        
        # Add user feedback options
        feedback_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        feedback_box.set_halign(Gtk.Align.CENTER)
        feedback_box.set_valign(Gtk.Align.CENTER)
        feedback_box.set_margin_top(10)
        feedback_box.set_hexpand(True)  # Make feedback box expandable
        
        feedback_label = Gtk.Label()
        feedback_label.set_markup(f'<span font="Sans Bold 18">{_("Is the detection result accurate?")}</span>')
        feedback_box.add(feedback_label)
        
        feedback_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        feedback_buttons.set_hexpand(True)  # Make feedback buttons box expandable
        
        self.yes_button = self._gtk.Button("complete", _("Accurate"), "color4")
        self.yes_button.connect("clicked", self.send_feedback, True)
        self.yes_button.set_hexpand(True)  # Make button expand horizontally
        feedback_buttons.add(self.yes_button)
        
        self.no_button = self._gtk.Button("error", _("False Alarm"), "color2")
        self.no_button.connect("clicked", self.send_feedback, False)
        self.no_button.set_hexpand(True)  # Make button expand horizontally
        feedback_buttons.add(self.no_button)
        
        feedback_box.add(feedback_buttons)
        main.add(feedback_box)
        
        # Add style classes
        main.get_style_context().add_class("ai-pause-panel")
        
        # Add custom CSS
        css = b"""
            .ai-info-frame {
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .ai-image-frame {
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .separator {
                margin: 10px 0;
            }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self.content.add(main)
        self._screen.show_all()

    def resume_print(self, widget):
        self._screen._ws.klippy.print_resume()
        # Return to print status page
        self._screen.show_panel("job_status", "job_status")

    def cancel_print(self, widget):
        self._screen._ws.klippy.print_cancel()
        # Return to main menu
        self._screen._menu_go_back()

    def send_feedback(self, widget, is_accurate):
        """Send user feedback to cloud service"""
        if self.result:
            feedback_data = {
                "task_id": self.result.get("task_id"),
                "is_accurate": is_accurate,
                "defect_type": self.result.get("defect_type"),
                "confidence": self.result.get("confidence")
            }
            # Send feedback
            self._screen._ws.klippy.gcode_script(f"AI_FEEDBACK {json.dumps(feedback_data)}")
            
        self._screen._menu_go_back()


             