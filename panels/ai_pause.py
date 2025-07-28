import gi
import logging
import time
from datetime import datetime

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        
        # 从传递的额外数据中获取检测信息
        extra_data = getattr(self, 'extra_data', {})
        defect_type = extra_data.get('defect_type', 'unknown')
        confidence = extra_data.get('confidence', 0)
        auto_paused = extra_data.get('auto_paused', False)
        detection_result = extra_data.get('detection_result', {})
        detection_time = extra_data.get('detection_time', time.time())
        
        # 创建主布局
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main.set_vexpand(True)
        main.set_hexpand(True)
        
        # 添加AI检测图标
        icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        icon_box.set_halign(Gtk.Align.CENTER)
        
        # AI检测相关的图标
        warning_icon = Gtk.Label("🤖⚠️")
        warning_icon.set_markup('<span size="xx-large">🤖⚠️</span>')
        icon_box.pack_start(warning_icon, False, False, 0)
        
        # 标题
        title_label = Gtk.Label()
        title_label.set_markup(f"<big><b>{_('AI Detection Alert')}</b></big>")
        title_label.set_line_wrap(True)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_valign(Gtk.Align.CENTER)
        
        # 检测详情
        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        defect_label = Gtk.Label()
        defect_name = self._get_defect_display_name(defect_type)
        defect_label.set_markup(f"<b>{_('Detected Defect')}:</b> {defect_name}")
        defect_label.set_halign(Gtk.Align.CENTER)
        
        confidence_label = Gtk.Label()
        confidence_label.set_markup(f"<b>{_('Confidence')}:</b> {confidence:.1%}")
        confidence_label.set_halign(Gtk.Align.CENTER)
        
        time_label = Gtk.Label()
        detection_time_str = datetime.fromtimestamp(detection_time).strftime("%H:%M:%S")
        time_label.set_markup(f"<b>{_('Detection Time')}:</b> {detection_time_str}")
        time_label.set_halign(Gtk.Align.CENTER)
        
        action_label = Gtk.Label()
        if auto_paused:
            action_text = _("Print has been automatically paused")
        else:
            action_text = _("Please check your print and decide the next action")
        action_label.set_markup(f"<i>{action_text}</i>")
        action_label.set_halign(Gtk.Align.CENTER)
        
        detail_box.pack_start(defect_label, False, False, 0)
        detail_box.pack_start(confidence_label, False, False, 0)
        detail_box.pack_start(time_label, False, False, 0)
        detail_box.pack_start(action_label, False, False, 5)
        
        # 描述文本
        description = Gtk.Label()
        description.set_line_wrap(True)
        description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        description_text = self._get_defect_description(defect_type)
        description.set_markup(description_text)
        description.set_halign(Gtk.Align.CENTER)
        description.set_valign(Gtk.Align.CENTER)
        
        # 按钮区域
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_valign(Gtk.Align.CENTER)
        button_box.set_hexpand(True)
        button_box.set_margin_start(20)
        button_box.set_margin_end(20)
        
        # 继续打印按钮
        resume_button = self._gtk.Button("resume", _("Continue Print"), "color1")
        resume_button.connect("clicked", self.resume)
        button_box.pack_start(resume_button, True, True, 5)
        
        # 取消打印按钮
        cancel_button = self._gtk.Button("cancel", _("Cancel Print"), "color3")
        cancel_button.connect("clicked", self.cancel)
        button_box.pack_start(cancel_button, True, True, 5)
        
        # 查看详情按钮
        details_button = self._gtk.Button("info", _("View Details"), "color2")
        details_button.connect("clicked", self.view_details)
        button_box.pack_start(details_button, True, True, 5)
        
        # 组装布局
        main.pack_start(Gtk.Label(), True, True, 0)  # 顶部间距
        main.pack_start(icon_box, False, False, 0)
        main.pack_start(title_label, False, False, 10)
        main.pack_start(detail_box, False, False, 10)
        main.pack_start(description, False, False, 10)
        main.pack_start(button_box, False, False, 10)
        main.pack_start(Gtk.Label(), True, True, 0)  # 底部间距
        
        self.content.add(main)
    
    def _get_defect_display_name(self, defect_type):
        """获取缺陷类型的显示名称"""
        defect_names = {
            'spaghetti': _('Spaghetti (炒面)'),
            'head_burst': _('Head Burst (爆头)'),
            'misalignment': _('Misalignment (错位)'),
            'layer_crack': _('Layer Crack (层间开裂)'),
            'warping': _('Warping (翘曲变形)'),
            'porosity': _('Porosity (孔隙)'),
        }
        return defect_names.get(defect_type, defect_type.title())
    
    def _get_defect_description(self, defect_type):
        """获取缺陷类型的描述"""
        descriptions = {
            'spaghetti': _("Spaghetti failure detected. The filament appears to be tangled or the print has failed catastrophically. Immediate attention required."),
            'head_burst': _("Head burst detected. There may be a nozzle clog or extrusion problem. Check the hotend and clear any blockages."),
            'misalignment': _("Layer misalignment detected. Check belt tension, motor steps, and mechanical components for proper alignment."),
            'layer_crack': _("Layer adhesion problems detected. Check print temperature, layer height, and cooling settings."),
            'warping': _("Warping detected. Consider adjusting bed temperature, print speed, or adding support structures."),
            'porosity': _("Surface porosity detected. Check extrusion multiplier, print speed, and temperature settings."),
        }
        return descriptions.get(defect_type, _("An issue has been detected with your print. Please inspect the print carefully."))

    def view_details(self, widget):
        """查看检测详情"""
        # 跳转到AI监控面板查看详细信息
        self._screen.show_panel("ai_monitor", _("AI Monitor"))

    def resume(self, widget):
        """继续打印"""
        try:
            self._screen._ws.klippy.print_resume()
            self._screen.show_popup_message(_("Print resumed"), level=1)
        except Exception as e:
            logging.error(f"恢复打印失败: {e}")
            self._screen.show_popup_message(_("Failed to resume print"), level=3)
        finally:
            self._screen._menu_go_back()

    def cancel(self, widget):
        """取消打印"""
        try:
            self._screen._ws.klippy.print_cancel()
            self._screen.show_popup_message(_("Print cancelled"), level=2)
        except Exception as e:
            logging.error(f"取消打印失败: {e}")
            self._screen.show_popup_message(_("Failed to cancel print"), level=3)
        finally:
            self._screen._menu_go_back() 