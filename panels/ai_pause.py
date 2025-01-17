import logging
import gi
import json

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title, message=None, result=None):
        super().__init__(screen, title)
        self.message = message
        self.result = result
        
        # Create main layout
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)
        main.set_hexpand(True)
        
        # Add title
        title_label = Gtk.Label()
        title_label.set_markup("<big><b>" + _("AI Detection Warning") + "</b></big>")
        title_label.set_line_wrap(True)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_valign(Gtk.Align.CENTER)
        main.add(title_label)
        
        # Add detection result info
        if message:
            info_label = Gtk.Label(label=message)
            info_label.set_line_wrap(True)
            info_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            info_label.set_halign(Gtk.Align.CENTER)
            info_label.set_valign(Gtk.Align.CENTER)
            main.add(info_label)
        
        # Add thumbnail if exists
        if result and "image_url" in result:
            image = self._gtk.Image("file", self._gtk.content_width * .9, self._gtk.content_height * .5)
            image.set_from_url(result["image_url"])
            main.add(image)
        
        # Add buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_valign(Gtk.Align.CENTER)
        button_box.set_hexpand(False)
        button_box.set_vexpand(False)
        
        # Resume print button
        self.resume_button = self._gtk.Button("resume", _("Resume Print"), "color1")
        self.resume_button.connect("clicked", self.resume_print)
        self.resume_button.set_hexpand(False)
        button_box.add(self.resume_button)
        
        # Cancel print button
        self.cancel_button = self._gtk.Button("cancel", _("Cancel Print"), "color3")
        self.cancel_button.connect("clicked", self.cancel_print)
        self.cancel_button.set_hexpand(False)
        button_box.add(self.cancel_button)
        
        main.add(button_box)
        
        # Add user feedback options
        feedback_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        feedback_box.set_halign(Gtk.Align.CENTER)
        feedback_box.set_valign(Gtk.Align.CENTER)
        
        feedback_label = Gtk.Label()
        feedback_label.set_markup("<b>" + _("Is the detection result accurate?") + "</b>")
        feedback_box.add(feedback_label)
        
        feedback_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.yes_button = self._gtk.Button("complete", _("Accurate"), "color4")
        self.yes_button.connect("clicked", self.send_feedback, True)
        feedback_buttons.add(self.yes_button)
        
        self.no_button = self._gtk.Button("error", _("False Alarm"), "color2")
        self.no_button.connect("clicked", self.send_feedback, False)
        feedback_buttons.add(self.no_button)
        
        feedback_box.add(feedback_buttons)
        main.add(feedback_box)
        
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

             