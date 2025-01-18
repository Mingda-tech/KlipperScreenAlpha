import gi
import logging
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel
class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.buttons = {
            'feedback_yes': self._gtk.Button("complete", _("Yes, False Alert"), "color1"),
            'feedback_no': self._gtk.Button("error", _("No, Issue Detected"), "color3")
        }
        
        # Set button size
        for button in self.buttons.values():
            button.set_hexpand(True)
            button.set_vexpand(False)
            button.set_property("height-request", round(self._gtk.font_size * 4))
        self.buttons['feedback_yes'].connect("clicked", self.send_feedback, True)
        self.buttons['feedback_no'].connect("clicked", self.send_feedback, False)
        # Create main layout
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)
        main.set_hexpand(True)
        # Add title and description
        title_label = Gtk.Label()
        title_label.set_markup("<big><b>" + _("AI Detection Alert") + "</b></big>")
        title_label.set_line_wrap(True)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_valign(Gtk.Align.CENTER)
        
        description = Gtk.Label()
        description.set_line_wrap(True)
        description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        description.set_markup(_(
            "The AI system has detected potential issues during printing\n"
            "Please check the print and let us know if this detection was accurate."
        ))
        description.set_halign(Gtk.Align.CENTER)
        description.set_valign(Gtk.Align.CENTER)
        # Add feedback buttons
        feedback_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        feedback_box.set_halign(Gtk.Align.FILL)
        feedback_box.set_valign(Gtk.Align.CENTER)
        feedback_box.set_hexpand(True)
        feedback_box.set_margin_start(20)
        feedback_box.set_margin_end(20)
        feedback_box.pack_start(self.buttons['feedback_yes'], True, True, 5)
        feedback_box.pack_start(self.buttons['feedback_no'], True, True, 5)
        # Add all elements to main layout with spacing
        main.pack_start(Gtk.Label(), True, True, 0)  # Spacer
        main.pack_start(title_label, False, False, 0)
        main.pack_start(description, False, False, 20)
        main.pack_start(feedback_box, False, False, 0)
        main.pack_start(Gtk.Label(), True, True, 0)  # Spacer
        self.content.add(main)
    def send_feedback(self, widget, is_false_positive):
        # Add code here to send feedback to AI service
        logging.info(f"AI detection feedback: {'false positive' if is_false_positive else 'true positive'}")
        # Disable feedback buttons after submission
        # self.buttons['feedback_yes'].set_sensitive(False)
        # self.buttons['feedback_no'].set_sensitive(False)
        
        # # Show thank you dialog
        # thank_dialog = self._gtk.Dialog(
        #     self._screen,
        #     {
        #         "confirm_text": _("OK"),
        #         "cancel_text": None,
        #         "confirm_style": "color1"
        #     },
        #     _("Thank You"),
        #     _("Thank you for your feedback. This will help us improve the AI detection system.")
        # )
        # thank_dialog.set_title(_("Thank You"))
        
        # Return to previous menu after dialog is closed
        self._screen._menu_go_back() 