"""
Nozzle Auto Calibration Panel
自动校准双喷嘴XY偏移面板
"""

import logging
import gi
import os
import time
import threading
import numpy as np
import cv2
from PIL import Image, ImageDraw
import requests
from io import BytesIO

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.nozzle_detector import NozzleDetector


class Panel(ScreenPanel):
    """双喷嘴自动校准面板"""
    
    def __init__(self, screen, title):
        super().__init__(screen, title)
        
        # 初始化变量
        self.detector = NozzleDetector(pixel_to_mm_ratio=0.05)
        self.calibrating = False
        self.current_step = 0
        self.calibration_thread = None
        self.camera_url = None
        self.preview_active = False
        
        # 存储校准结果
        self.calibration_results = {
            'nozzle1_pos': None,
            'nozzle2_pos': None,
            'offset_x': None,
            'offset_y': None,
            'pixel_ratio': 0.05
        }
        
        # 读取现有配置
        self.current_offset = {'x': 0, 'y': 0}
        if self._screen.klippy_config is not None:
            try:
                self.current_offset['x'] = self._screen.klippy_config.getfloat("Variables", "idex_xoffset")
                self.current_offset['y'] = self._screen.klippy_config.getfloat("Variables", "idex_yoffset")
            except Exception as e:
                logging.info(f"No existing offset config: {e}")
        
        # 设置摄像头URL
        self._setup_camera_url()
        
        # 创建UI
        self._create_ui()
        
    def _setup_camera_url(self):
        """设置摄像头URL"""
        # 优先使用校准专用摄像头
        for cam in self._printer.cameras:
            if cam.get("enabled") and "calib" in cam.get("name", "").lower():
                self.camera_url = cam.get("stream_url", "")
                break
        
        # 如果没有专用校准摄像头，使用第一个可用摄像头
        if not self.camera_url:
            for cam in self._printer.cameras:
                if cam.get("enabled"):
                    self.camera_url = cam.get("stream_url", "")
                    break
        
        # 处理相对URL
        if self.camera_url and self.camera_url.startswith('/'):
            endpoint = self._screen.apiclient.endpoint.split(':')
            self.camera_url = f"{endpoint[0]}:{endpoint[1]}{self.camera_url}"
            
        logging.info(f"Camera URL configured: {self.camera_url}")
    
    def _create_ui(self):
        """创建用户界面"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # 标题栏
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title_label = Gtk.Label()
        title_label.set_markup("<big><b>双喷嘴自动校准</b></big>")
        title_box.pack_start(title_label, True, True, 0)
        main_box.pack_start(title_box, False, False, 10)
        
        # 主要内容区域（水平布局）
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # 左侧：摄像头预览区域
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        # 摄像头预览
        self.preview_frame = Gtk.Frame()
        self.preview_frame.set_size_request(480, 360)
        self.preview_image = Gtk.Image()
        self.preview_frame.add(self.preview_image)
        left_box.pack_start(self.preview_frame, True, True, 0)
        
        # 预览控制按钮
        preview_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.btn_preview = self._gtk.Button(None, _("Start Preview"), "color2")
        self.btn_preview.connect("clicked", self.toggle_preview)
        self.btn_capture = self._gtk.Button(None, _("Capture Image"), "color3")
        self.btn_capture.connect("clicked", self.capture_image)
        preview_controls.pack_start(self.btn_preview, True, True, 0)
        preview_controls.pack_start(self.btn_capture, True, True, 0)
        left_box.pack_start(preview_controls, False, False, 0)
        
        content_box.pack_start(left_box, True, True, 0)
        
        # 右侧：控制和信息区域
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # 校准步骤说明
        steps_frame = Gtk.Frame(label="校准步骤")
        steps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        steps_box.set_margin_left(10)
        steps_box.set_margin_right(10)
        steps_box.set_margin_top(10)
        steps_box.set_margin_bottom(10)
        
        self.step_labels = []
        steps = [
            "1. 归零并移动到校准位置",
            "2. 提升喷嘴温度",
            "3. 清洁喷嘴",
            "4. 降低喷嘴到检测高度",
            "5. 拍摄并分析图像",
            "6. 计算偏移量",
            "7. 保存校准结果"
        ]
        
        for step in steps:
            label = Gtk.Label(label=step)
            label.set_halign(Gtk.Align.START)
            self.step_labels.append(label)
            steps_box.pack_start(label, False, False, 0)
        
        steps_frame.add(steps_box)
        right_box.pack_start(steps_frame, False, False, 0)
        
        # 当前状态
        status_frame = Gtk.Frame(label="状态信息")
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        status_box.set_margin_left(10)
        status_box.set_margin_right(10)
        status_box.set_margin_top(10)
        status_box.set_margin_bottom(10)
        
        self.status_label = Gtk.Label(label="准备就绪")
        self.status_label.set_line_wrap(True)
        status_box.pack_start(self.status_label, False, False, 0)
        
        # 当前偏移值
        self.offset_label = Gtk.Label()
        self._update_offset_display()
        status_box.pack_start(self.offset_label, False, False, 5)
        
        # 检测结果
        self.result_label = Gtk.Label(label="")
        self.result_label.set_line_wrap(True)
        status_box.pack_start(self.result_label, False, False, 5)
        
        status_frame.add(status_box)
        right_box.pack_start(status_frame, False, False, 0)
        
        # 参数设置
        params_frame = Gtk.Frame(label="参数设置")
        params_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        params_box.set_margin_left(10)
        params_box.set_margin_right(10)
        params_box.set_margin_top(10)
        params_box.set_margin_bottom(10)
        
        # 像素比例调整
        pixel_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        pixel_label = Gtk.Label(label="像素比例 (mm/px):")
        self.pixel_entry = Gtk.Entry()
        self.pixel_entry.set_text(str(self.detector.pixel_to_mm))
        self.pixel_entry.set_width_chars(10)
        pixel_box.pack_start(pixel_label, False, False, 0)
        pixel_box.pack_start(self.pixel_entry, False, False, 0)
        params_box.pack_start(pixel_box, False, False, 0)
        
        # 检测高度
        height_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        height_label = Gtk.Label(label="检测高度 (mm):")
        self.height_entry = Gtk.Entry()
        self.height_entry.set_text("5")
        self.height_entry.set_width_chars(10)
        height_box.pack_start(height_label, False, False, 0)
        height_box.pack_start(self.height_entry, False, False, 0)
        params_box.pack_start(height_box, False, False, 0)
        
        params_frame.add(params_box)
        right_box.pack_start(params_frame, False, False, 0)
        
        # 控制按钮
        control_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        # 主要操作按钮
        main_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.btn_start = self._gtk.Button(None, _("Start Calibration"), "color1")
        self.btn_start.connect("clicked", self.start_calibration)
        self.btn_stop = self._gtk.Button(None, _("Stop"), "color4")
        self.btn_stop.connect("clicked", self.stop_calibration)
        self.btn_stop.set_sensitive(False)
        
        main_buttons.pack_start(self.btn_start, True, True, 0)
        main_buttons.pack_start(self.btn_stop, True, True, 0)
        control_box.pack_start(main_buttons, False, False, 0)
        
        # 辅助操作按钮
        aux_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.btn_manual = self._gtk.Button(None, _("Manual Detect"), "color2")
        self.btn_manual.connect("clicked", self.manual_detect)
        self.btn_save = self._gtk.Button(None, _("Save Results"), "color3")
        self.btn_save.connect("clicked", self.save_results)
        self.btn_save.set_sensitive(False)
        
        aux_buttons.pack_start(self.btn_manual, True, True, 0)
        aux_buttons.pack_start(self.btn_save, True, True, 0)
        control_box.pack_start(aux_buttons, False, False, 0)
        
        right_box.pack_end(control_box, False, False, 0)
        
        content_box.pack_start(right_box, False, False, 0)
        main_box.pack_start(content_box, True, True, 0)
        
        self.content.add(main_box)
        
    def _update_offset_display(self):
        """更新偏移值显示"""
        self.offset_label.set_markup(
            f"<b>当前偏移:</b> X: {self.current_offset['x']:.2f}mm, Y: {self.current_offset['y']:.2f}mm"
        )
    
    def _update_step_display(self, step_index):
        """更新步骤显示"""
        for i, label in enumerate(self.step_labels):
            if i < step_index:
                label.set_markup(f"<span foreground='green'>✓ {label.get_text()}</span>")
            elif i == step_index:
                label.set_markup(f"<span foreground='blue'><b>▶ {label.get_text()}</b></span>")
            else:
                label.set_markup(f"<span foreground='gray'>{label.get_text()}</span>")
    
    def toggle_preview(self, widget):
        """切换摄像头预览"""
        if not self.preview_active:
            self.start_preview()
        else:
            self.stop_preview()
    
    def start_preview(self):
        """开始摄像头预览"""
        if not self.camera_url:
            self._screen.show_popup_message(_("No camera configured"), level=2)
            return
        
        self.preview_active = True
        self.btn_preview.set_label(_("Stop Preview"))
        
        # 启动预览更新线程
        def update_preview():
            while self.preview_active:
                try:
                    # 从摄像头获取图像
                    response = requests.get(self.camera_url, timeout=2)
                    img = Image.open(BytesIO(response.content))
                    
                    # 添加十字线
                    draw = ImageDraw.Draw(img)
                    width, height = img.size
                    center_x, center_y = width // 2, height // 2
                    
                    # 画十字线
                    draw.line([(center_x - 50, center_y), (center_x + 50, center_y)], 
                             fill=(255, 0, 0), width=1)
                    draw.line([(center_x, center_y - 50), (center_x, center_y + 50)], 
                             fill=(0, 255, 0), width=1)
                    
                    # 转换为GdkPixbuf并更新显示
                    img = img.resize((480, 360), Image.LANCZOS)
                    img_bytes = BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    
                    loader = GdkPixbuf.PixbufLoader()
                    loader.write(img_bytes.read())
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                    
                    GLib.idle_add(self.preview_image.set_from_pixbuf, pixbuf)
                    
                except Exception as e:
                    logging.error(f"Preview update error: {e}")
                
                time.sleep(0.5)  # 2 FPS
        
        preview_thread = threading.Thread(target=update_preview)
        preview_thread.daemon = True
        preview_thread.start()
    
    def stop_preview(self):
        """停止摄像头预览"""
        self.preview_active = False
        self.btn_preview.set_label(_("Start Preview"))
        self.preview_image.clear()
    
    def capture_image(self, widget):
        """捕获当前图像"""
        if not self.camera_url:
            self._screen.show_popup_message(_("No camera configured"), level=2)
            return
        
        try:
            # 捕获图像
            response = requests.get(self.camera_url, timeout=5)
            img = Image.open(BytesIO(response.content))
            
            # 保存图像
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = f"/tmp/nozzle_capture_{timestamp}.png"
            img.save(save_path)
            
            self._screen.show_popup_message(f"Image saved to {save_path}", level=1)
            
            # 立即进行检测
            self.detect_nozzles_in_image(save_path)
            
        except Exception as e:
            logging.error(f"Capture error: {e}")
            self._screen.show_popup_message(f"Capture failed: {e}", level=2)
    
    def start_calibration(self, widget):
        """开始自动校准流程"""
        if self.calibrating:
            return
        
        self.calibrating = True
        self.btn_start.set_sensitive(False)
        self.btn_stop.set_sensitive(True)
        self.current_step = 0
        
        # 更新像素比例
        try:
            self.detector.pixel_to_mm = float(self.pixel_entry.get_text())
        except:
            pass
        
        # 启动校准线程
        self.calibration_thread = threading.Thread(target=self._calibration_process)
        self.calibration_thread.daemon = True
        self.calibration_thread.start()
    
    def _calibration_process(self):
        """校准流程"""
        try:
            # Step 1: 归零
            self._update_status("归零中...")
            GLib.idle_add(self._update_step_display, 0)
            self._screen._ws.klippy.gcode_script("G28")
            time.sleep(3)
            
            if not self.calibrating:
                return
            
            # Step 2: 加热喷嘴
            self._update_status("加热喷嘴到工作温度...")
            GLib.idle_add(self._update_step_display, 1)
            self._screen._ws.klippy.gcode_script("M104 S200 T0")  # 加热喷嘴0
            self._screen._ws.klippy.gcode_script("M104 S200 T1")  # 加热喷嘴1
            time.sleep(10)  # 等待加热
            
            if not self.calibrating:
                return
            
            # Step 3: 清洁喷嘴
            self._update_status("清洁喷嘴...")
            GLib.idle_add(self._update_step_display, 2)
            # 这里可以添加清洁喷嘴的G代码
            time.sleep(2)
            
            if not self.calibrating:
                return
            
            # Step 4: 移动到检测位置
            self._update_status("移动到检测位置...")
            GLib.idle_add(self._update_step_display, 3)
            
            # 读取检测高度
            try:
                detect_height = float(self.height_entry.get_text())
            except:
                detect_height = 5.0
            
            # 移动到平台中心上方
            bed_x = 150  # 假设床尺寸300x300
            bed_y = 150
            self._screen._ws.klippy.gcode_script(f"G0 X{bed_x} Y{bed_y} Z{detect_height} F3000")
            time.sleep(3)
            
            if not self.calibrating:
                return
            
            # Step 5: 拍摄并分析
            self._update_status("拍摄并分析图像...")
            GLib.idle_add(self._update_step_display, 4)
            
            # 关闭喷嘴加热
            self._screen._ws.klippy.gcode_script("M104 S0 T0")
            self._screen._ws.klippy.gcode_script("M104 S0 T1")
            
            # 捕获图像
            if self.camera_url:
                try:
                    response = requests.get(self.camera_url, timeout=5)
                    img = Image.open(BytesIO(response.content))
                    
                    # 保存图像
                    img_path = "/tmp/nozzle_calibration.png"
                    img.save(img_path)
                    
                    # 转换为OpenCV格式
                    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    
                    # Step 6: 检测喷嘴
                    self._update_status("检测喷嘴位置...")
                    GLib.idle_add(self._update_step_display, 5)
                    
                    # 使用检测器
                    offset = self.detector.auto_calibrate(img_cv)
                    
                    if offset:
                        self.calibration_results['offset_x'] = offset[0]
                        self.calibration_results['offset_y'] = offset[1]
                        
                        self._update_status(f"检测成功! 偏移: X={offset[0]:.3f}mm, Y={offset[1]:.3f}mm")
                        GLib.idle_add(self.result_label.set_markup,
                                    f"<b>检测结果:</b>\nX偏移: {offset[0]:.3f}mm\nY偏移: {offset[1]:.3f}mm")
                        
                        # Step 7: 准备保存
                        GLib.idle_add(self._update_step_display, 6)
                        GLib.idle_add(self.btn_save.set_sensitive, True)
                        
                        self._update_status("校准完成! 请点击'保存结果'按钮保存配置")
                    else:
                        self._update_status("未能检测到两个喷嘴，请手动调整后重试")
                        
                except Exception as e:
                    logging.error(f"Image capture/detection error: {e}")
                    self._update_status(f"检测失败: {e}")
            else:
                self._update_status("未配置摄像头")
            
        except Exception as e:
            logging.error(f"Calibration error: {e}")
            self._update_status(f"校准失败: {e}")
        
        finally:
            self.calibrating = False
            GLib.idle_add(self.btn_start.set_sensitive, True)
            GLib.idle_add(self.btn_stop.set_sensitive, False)
    
    def stop_calibration(self, widget):
        """停止校准"""
        self.calibrating = False
        self._update_status("校准已停止")
        
        # 关闭加热
        self._screen._ws.klippy.gcode_script("M104 S0 T0")
        self._screen._ws.klippy.gcode_script("M104 S0 T1")
        
        self.btn_start.set_sensitive(True)
        self.btn_stop.set_sensitive(False)
    
    def manual_detect(self, widget):
        """手动检测（使用最近的捕获图像）"""
        # 查找最近的捕获图像
        import glob
        captures = glob.glob("/tmp/nozzle_capture_*.png")
        if captures:
            latest = max(captures, key=os.path.getctime)
            self.detect_nozzles_in_image(latest)
        else:
            self._screen.show_popup_message(_("No captured images found"), level=2)
    
    def detect_nozzles_in_image(self, image_path):
        """在指定图像中检测喷嘴"""
        try:
            # 更新像素比例
            try:
                self.detector.pixel_to_mm = float(self.pixel_entry.get_text())
            except:
                pass
            
            # 加载图像
            img = cv2.imread(image_path)
            if img is None:
                self._screen.show_popup_message(f"Cannot load image: {image_path}", level=2)
                return
            
            # 检测
            offset = self.detector.auto_calibrate(img)
            
            if offset:
                self.calibration_results['offset_x'] = offset[0]
                self.calibration_results['offset_y'] = offset[1]
                
                self.result_label.set_markup(
                    f"<b>检测结果:</b>\nX偏移: {offset[0]:.3f}mm\nY偏移: {offset[1]:.3f}mm"
                )
                self.btn_save.set_sensitive(True)
                
                # 显示调试图像
                debug_path = "/tmp/nozzle_detection_debug.png"
                if os.path.exists(debug_path):
                    # 加载并显示调试图像
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(debug_path, 480, 360, True)
                    self.preview_image.set_from_pixbuf(pixbuf)
                
                self._screen.show_popup_message(
                    f"检测成功!\nX偏移: {offset[0]:.3f}mm\nY偏移: {offset[1]:.3f}mm",
                    level=1
                )
            else:
                self._screen.show_popup_message(_("Failed to detect nozzles"), level=2)
                
        except Exception as e:
            logging.error(f"Manual detection error: {e}")
            self._screen.show_popup_message(f"Detection error: {e}", level=2)
    
    def save_results(self, widget):
        """保存校准结果"""
        if self.calibration_results['offset_x'] is None:
            return
        
        try:
            # 更新配置
            if self._screen.klippy_config is not None:
                self._screen.klippy_config.set("Variables", "idex_xoffset", 
                                              f"{self.calibration_results['offset_x']:.3f}")
                self._screen.klippy_config.set("Variables", "idex_yoffset", 
                                              f"{self.calibration_results['offset_y']:.3f}")
                
                # 保存像素比例
                self._screen.klippy_config.set("Variables", "pixel_to_mm_ratio",
                                              f"{self.detector.pixel_to_mm:.5f}")
                
                # 写入文件
                with open(self._screen.klippy_config_path, 'w') as file:
                    self._screen.klippy_config.write(file)
                
                # 更新显示
                self.current_offset['x'] = self.calibration_results['offset_x']
                self.current_offset['y'] = self.calibration_results['offset_y']
                self._update_offset_display()
                
                # 发送SAVE_CONFIG命令
                script = {"script": "SAVE_CONFIG"}
                self._screen._confirm_send_action(
                    None,
                    _("Calibration saved!") + "\n\n" + _("Restart required. Restart now?"),
                    "printer.gcode.script",
                    script
                )
                
                self.btn_save.set_sensitive(False)
                self._update_status("校准结果已保存")
                
        except Exception as e:
            logging.error(f"Save error: {e}")
            self._screen.show_popup_message(f"Save failed: {e}", level=2)
    
    def _update_status(self, message):
        """更新状态显示"""
        GLib.idle_add(self.status_label.set_text, message)
        logging.info(f"Calibration: {message}")
    
    def deactivate(self):
        """面板停用时的清理"""
        self.stop_preview()
        if self.calibrating:
            self.stop_calibration(None)