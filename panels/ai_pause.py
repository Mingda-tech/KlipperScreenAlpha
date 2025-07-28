import gi
import logging
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        
        # 创建主布局
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)
        main.set_hexpand(True)
        
        # 添加标题
        title_label = Gtk.Label()
        title_label.set_markup("<big><b>" + _("AI Detection Alert") + "</b></big>")
        title_label.set_line_wrap(True)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_valign(Gtk.Align.CENTER)
        
        # 添加描述
        description = Gtk.Label()
        description.set_line_wrap(True)
        description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        description.set_markup(_(
            "The AI system has detected potential issues during printing.\n"
            "Please check the print status."
        ))
        description.set_halign(Gtk.Align.CENTER)
        description.set_valign(Gtk.Align.CENTER)
        
        # 添加按钮
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_valign(Gtk.Align.CENTER)
        button_box.set_hexpand(True)
        button_box.set_margin_start(20)
        button_box.set_margin_end(20)
        
        resume_button = self._gtk.Button("resume", _("Resume"), "color1")
        resume_button.connect("clicked", self.resume)
        button_box.pack_start(resume_button, True, True, 5)
        
        cancel_button = self._gtk.Button("cancel", _("Cancel"), "color3")
        cancel_button.connect("clicked", self.cancel)
        button_box.pack_start(cancel_button, True, True, 5)
        
        # 将所有元素添加到主布局
        main.pack_start(Gtk.Label(), True, True, 0)  # 顶部间距
        main.pack_start(title_label, False, False, 0)
        main.pack_start(description, False, False, 20)
        main.pack_start(button_box, False, False, 0)
        main.pack_start(Gtk.Label(), True, True, 0)  # 底部间距
        
        self.content.add(main)
    
    def resume(self, widget):
        self._screen._ws.klippy.print_resume()
        self._screen._menu_go_back()
    
    def cancel(self, widget):
        self._screen._ws.klippy.print_cancel()
        self._screen._menu_go_back() 