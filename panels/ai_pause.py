import gi
import logging
import os
import glob

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GdkPixbuf

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, **kwargs):
        super().__init__(screen, title)
        
        
        # 预测图片输出路径
        self.output_path = "/home/mingda/workspace/npudemo/PrintSentinel/md-ai-detection/output"
        
        # 创建主布局 - 垂直布局，按高度比例分配
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)
        main.set_hexpand(True)
        
        # 1. 顶部错误提示信息 - 占用1/7高度
        alert_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        alert_box.set_vexpand(False)
        alert_box.set_hexpand(True)
        alert_box.set_valign(Gtk.Align.CENTER)
        
        alert_label = Gtk.Label()
        alert_label.set_markup(f'<span size="medium" color="red"><b>{_("Print Issue Detected!")}</b></span>')
        alert_label.set_halign(Gtk.Align.CENTER)
        alert_label.set_valign(Gtk.Align.CENTER)
        alert_box.pack_start(alert_label, True, True, 0)
        
        # 2. 中间图片显示区域 - 占用5/7高度
        image_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        image_box.set_vexpand(True)
        image_box.set_hexpand(True)
        image_box.set_valign(Gtk.Align.CENTER)
        image_box.set_halign(Gtk.Align.CENTER)
        
        # 预测图片
        self.detection_image = Gtk.Image()
        
        # 加载最新的预测图片
        self._load_latest_prediction_image()
        
        image_box.pack_start(self.detection_image, True, True, 0)
        
        # 3. 底部按钮区域 - 占用1/7高度
        button_box = self._gtk.HomogeneousGrid()  # 使用Grid布局来精确控制
        
        # 继续打印按钮
        resume_button = self._gtk.Button("resume", None, "color1", scale=.66)
        resume_button.connect("clicked", self.resume)
        
        # 取消打印按钮
        cancel_button = self._gtk.Button("cancel", None, "color3", scale=.66)
        cancel_button.connect("clicked", self.cancel)
        
        # 使用Grid布局精确控制按钮位置
        button_box.attach(resume_button, 0, 0, 1, 1)  # 左侧按钮
        button_box.attach(cancel_button, 2, 0, 1, 1)  # 右侧按钮，跳过中间列
        
        # 组装主布局 - 按比例分配高度
        main.pack_start(alert_box, False, False, 0)    # 1/7
        main.pack_start(image_box, True, True, 0)      # 5/7 (expand=True)
        main.pack_start(button_box, False, False, 0)   # 1/7
        
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
                
                # 加载并显示图片 - 自适应容器大小
                try:
                    # 获取屏幕尺寸用于缩放
                    screen_width = self._screen.width
                    screen_height = self._screen.height
                    
                    # 计算图片显示区域的大小 (5/7 of height, with some padding)
                    max_width = int(screen_width * 0.95)  # 留出5%边距
                    max_height = int(screen_height * 5/7 * 0.95)  # 5/7高度，留出5%边距
                    
                    # 加载图片并按比例缩放
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        latest_image, max_width, max_height, True
                    )
                    self.detection_image.set_from_pixbuf(pixbuf)
                    logging.info(f"已加载预测图片: {latest_image}, 缩放至: {pixbuf.get_width()}x{pixbuf.get_height()}")
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
            # 创建一个简单的占位文本
            placeholder_text = _("No prediction image available")
            
            # 设置占位文本到图片控件
            self.detection_image.clear()
            
            # 或者创建一个标签作为占位符（如果需要的话）
            # 这里我们直接清空图片，让容器显示空白
            
        except Exception as e:
            logging.error(f"设置占位图片失败: {e}")
    

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