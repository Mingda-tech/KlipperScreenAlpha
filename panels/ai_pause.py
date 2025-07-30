import gi
import logging
import os
import glob
from datetime import datetime

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GdkPixbuf

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        
        # 从kwargs中直接获取extra_data，或者从实例属性中获取
        extra_data = kwargs.get('extra_data', getattr(self, 'extra_data', {}))
        defect_type = extra_data.get('defect_type', 'unknown')
        confidence = extra_data.get('confidence', 0)
        auto_paused = extra_data.get('auto_paused', False)
        detection_result = extra_data.get('detection_result', {})
        
        # 预测图片输出路径
        self.output_path = "/home/mingda/workspace/npudemo/PrintSentinel/md-ai-detection/output"
        
        # 创建主布局 - 使用水平布局，左侧图片，右侧信息和按钮
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        main.set_vexpand(True)
        main.set_hexpand(True)
        main.set_margin_start(20)
        main.set_margin_end(20)
        main.set_margin_top(20)
        main.set_margin_bottom(20)
        
        # 左侧：预测图片显示区域
        image_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        image_box.set_valign(Gtk.Align.CENTER)
        
        # 图片标题
        image_title = Gtk.Label()
        image_title.set_markup(f"<b>{_('Detection Image')}</b>")
        image_title.set_halign(Gtk.Align.CENTER)
        
        # 预测图片
        self.detection_image = Gtk.Image()
        self.detection_image.set_size_request(400, 300)
        
        # 加载最新的预测图片
        self._load_latest_prediction_image()
        
        image_box.pack_start(image_title, False, False, 0)
        image_box.pack_start(self.detection_image, False, False, 0)
        
        # 右侧：错误信息和按钮区域
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        info_box.set_valign(Gtk.Align.CENTER)
        info_box.set_hexpand(True)
        
        # 错误提示信息
        alert_label = Gtk.Label()
        alert_label.set_markup(f'<span size="large" color="red"><b>{_("Print Issue Detected!")}</b></span>')
        alert_label.set_halign(Gtk.Align.CENTER)
        
        # 错误类型
        defect_label = Gtk.Label()
        defect_name = self._get_defect_display_name(defect_type)
        defect_label.set_markup(f'<span size="medium"><b>{_("Defect Type")}:</b> {defect_name}</span>')
        defect_label.set_halign(Gtk.Align.CENTER)
        
        # 置信度
        confidence_label = Gtk.Label()
        confidence_label.set_markup(f'<span size="medium"><b>{_("Confidence")}:</b> {confidence:.1%}</span>')
        confidence_label.set_halign(Gtk.Align.CENTER)
        
        # 按钮区域
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(20)
        
        # 继续打印按钮
        resume_button = self._gtk.Button("resume", _("Continue Print"), "color1")
        resume_button.connect("clicked", self.resume)
        resume_button.set_hexpand(True)
        
        # 取消打印按钮
        cancel_button = self._gtk.Button("cancel", _("Cancel Print"), "color3")
        cancel_button.connect("clicked", self.cancel)
        cancel_button.set_hexpand(True)
        
        button_box.pack_start(resume_button, False, False, 0)
        button_box.pack_start(cancel_button, False, False, 0)
        
        # 组装右侧信息区域
        info_box.pack_start(alert_label, False, False, 0)
        info_box.pack_start(defect_label, False, False, 0)
        info_box.pack_start(confidence_label, False, False, 0)
        info_box.pack_start(button_box, False, False, 0)
        
        # 组装主布局
        main.pack_start(image_box, False, False, 0)
        main.pack_start(info_box, True, True, 0)
        
        self.content.add(main)
    
    def _load_latest_prediction_image(self):
        """加载最新的预测图片"""
        try:
            # 查找最新的预测图片
            pattern = os.path.join(self.output_path, "spaghetti_monitor_*.jpg")
            image_files = glob.glob(pattern)
            
            if image_files:
                # 按修改时间排序，获取最新的文件
                latest_image = max(image_files, key=os.path.getmtime)
                
                # 加载并显示图片
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        latest_image, 400, 300, True
                    )
                    self.detection_image.set_from_pixbuf(pixbuf)
                    logging.info(f"已加载预测图片: {latest_image}")
                except Exception as e:
                    logging.error(f"加载图片失败: {e}")
                    self._set_placeholder_image()
            else:
                logging.warning(f"未找到预测图片，路径: {pattern}")
                self._set_placeholder_image()
                
        except Exception as e:
            logging.error(f"查找预测图片失败: {e}")
            self._set_placeholder_image()
    
    def _set_placeholder_image(self):
        """设置占位图片"""
        try:
            # 创建一个简单的占位图片
            placeholder_text = _("No prediction image available")
            
            # 使用文本标签作为占位符
            placeholder = Gtk.Label(placeholder_text)
            placeholder.set_size_request(400, 300)
            placeholder.set_halign(Gtk.Align.CENTER)
            placeholder.set_valign(Gtk.Align.CENTER)
            
            # 如果detection_image已经有父容器，需要先移除
            parent = self.detection_image.get_parent()
            if parent:
                parent.remove(self.detection_image)
                parent.pack_start(placeholder, False, False, 0)
                placeholder.show()
                
        except Exception as e:
            logging.error(f"设置占位图片失败: {e}")
    
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

    def resume(self, widget):
        """继续打印"""
        try:
            # 清理AI暂停状态
            self._screen.ai_pause_active = False
            
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
            # 清理AI暂停状态
            self._screen.ai_pause_active = False
            
            self._screen._ws.klippy.print_cancel()
            self._screen.show_popup_message(_("Print cancelled"), level=2)
        except Exception as e:
            logging.error(f"取消打印失败: {e}")
            self._screen.show_popup_message(_("Failed to cancel print"), level=3)
        finally:
            self._screen._menu_go_back()