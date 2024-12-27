import logging
import gi
import os
import subprocess
import mpv
from contextlib import suppress
from PIL import Image, ImageDraw, ImageFont
from gi.repository import GLib

# 尝试导入可选依赖
try:
    import io
    import cv2
    import numpy as np
    import requests
    CALIBRATION_SUPPORTED = True
except ImportError:
    CALIBRATION_SUPPORTED = False
    logging.warning("Auto calibration dependencies not found. Please install: python3-opencv python3-numpy python3-requests")

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class MdAutoCalibrator():
    def __init__(self, ip):
        # 假设最佳中心点
        self.perfect_center = (131, 141)
        self.perfect_lt = (131-60, 141-60)
        self.perfect_rb = (131+60, 141+60)
        # 摄像头url的单帧图片
        self.camera_url = f"http://{ip}/webcam2/?action=snapshot"
        # 对比模板图片路径
        self.template_left_path = "/home/mingda/printer_data/resources/template_left.png"
        self.template_right_path = "/home/mingda/printer_data/resources/template_right.png"
        self.extruder_left_path = "/home/mingda/printer_data/resources/extruder_left.png"
        self.extruder_right_path = "/home/mingda/printer_data/resources/extruder_right.png"
        self.allow_match = False

    # 获取图片
    def getImage(self, url):
        if url.startswith('http'):
            response = requests.get(url)
            image = Image.open(io.BytesIO(response.content))
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.COLOR_BGR2GRAY)
            # 将图像翻转，使图片方向与实际看到的方向一致
            image = cv2.flip(image, 0)
            # 将图片旋转90度
            image = cv2.rotate(image, -cv2.ROTATE_90_CLOCKWISE)
        else:
            image = cv2.imread(url, cv2.COLOR_BGR2GRAY)
        return image

    # 保存图片
    def saveImage(self, image, path):
        cv2.imwrite(path, image)

    # 缩放图片
    def resizeImage(self, image, scale):
        height, width = image.shape[:2]
        new_height = int(height * scale)
        new_width = int(width * scale)
        scaled_template = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return scaled_template

    # 旋转图片
    def rotateImage(self, image, angle):
        height, width = image.shape[:2]
        center = (width / 2, height / 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated_image = cv2.warpAffine(image, rotation_matrix, (width, height))
        return rotated_image

    # 匹配图片
    def matchImage(self, image, template):
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED, mask=None)
        min_val,max_val,min_loc,max_loc = cv2.minMaxLoc(result)
        top_left = max_loc
        h,w = template.shape[:2]
        bottem_right = (top_left[0] + w, top_left[1] + h)
        return image, max_val, top_left, bottem_right

    # 裁剪图片
    def clipImage(self, image, top_left, bottem_right):
        cropped_image = image[top_left[1]:bottem_right[1], top_left[0]:bottem_right[0]]
        return cropped_image

    # 归一化直方图对比
    def compare_images(self, img1, img2):
        hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        cv2.normalize(hist1, hist1, alpha = 0, beta = 1, norm_type = cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, alpha = 0, beta = 1, norm_type = cv2.NORM_MINMAX)
        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
        return 1-similarity

    # 基于特征匹配的相似度
    def compare_images_sift(self, img1, img2):
        sift = cv2.SIFT_create()
        keypoints1, descriptors1 = sift.detectAndCompute(img1, None)
        keypoints2, descriptors2 = sift.detectAndCompute(img2, None)
        bf = cv2.BFMatcher()
        matches = bf.knnMatch(descriptors1, descriptors2, k = 2)
        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
        similarity = len(good_matches) / max(len(keypoints1), len(keypoints2))
        return similarity

    # 计算中心点
    def getCenter(self, top_left, bottem_right):
        center_x = (top_left[0] + bottem_right[0]) / 2
        center_y = (top_left[1] + bottem_right[1]) / 2
        return (center_x, center_y)
    
    # 获取左 extruder 的模板
    def saveTemplateLeft(self) :
        image = self.getImage(self.camera_url)
        temp = self.clipImage(image, self.perfect_lt, self.perfect_rb)
        self.saveImage(temp, self.template_left_path)
        self.saveImage(image, self.extruder_left_path)

    # 获取右 extruder 的模板
    def saveTemplateRight(self) :
        image = self.getImage(self.camera_url)
        temp = self.clipImage(image, self.perfect_lt, self.perfect_rb)
        self.saveImage(temp, self.template_right_path)
        self.saveImage(image, self.extruder_right_path)

    # 开始匹配
    def startMatch(self):
        image = self.getImage(self.camera_url)

        # 匹配左侧喷头
        template_left = self.getImage(self.template_left_path)
        image, max_val, top_left, bottem_right = self.matchImage(image, template_left)
        left_clip_image = self.clipImage(image, top_left, bottem_right)
        left_clip_center = self.getCenter(top_left, bottem_right)

        # 对比相似度，判断是否为左侧喷头
        similarity_left_1 = self.compare_images(left_clip_image, template_left)
        similarity_left_2 = self.compare_images_sift(left_clip_image, template_left)

        logging.info(f"Left extruder match: {similarity_left_1}, {similarity_left_2}")
        if similarity_left_1 > 0.7 or similarity_left_2 > 0.4:
            # 对比中心点与目标中心点
            offset_x = left_clip_center[0] - self.perfect_center[0]
            offset_y = left_clip_center[1] - self.perfect_center[1]
            offset = (offset_x, offset_y) 
            if offset == (0, 0):
                # 更新匹配模板
                logging.info(f"Perfect! Saving image... max_val: {max_val}, offset: {offset}")
                self.saveImage(left_clip_image, self.template_left_path)
                self.saveImage(image, self.extruder_left_path)
            return True, image, offset, top_left, bottem_right 
        
        # 匹配右侧喷头
        template_right = self.getImage(self.template_right_path)
        image, max_val, top_left, bottem_right = self.matchImage(image, template_right)
        clip_image_right = self.clipImage(image, top_left, bottem_right)
        clip_center_right = self.getCenter(top_left, bottem_right)

        # 对比相似度，判断是否为右侧喷头
        similarity_right_1 = self.compare_images(clip_image_right, template_right)
        similarity_right_2 = self.compare_images_sift(clip_image_right, template_right)

        logging.info(f"Right extruder match: {similarity_right_1}, {similarity_right_2}")
        if similarity_right_1 > 0.7 or similarity_right_2 > 0.4:
            # 对比中心点与目标中心点
            offset_x = clip_center_right[0] - self.perfect_center[0]
            offset_y = clip_center_right[1] - self.perfect_center[1]
            offset = (offset_x, offset_y)
            if offset == (0, 0):
                # 更新匹配模板
                logging.info(f"Perfect! Saving image... max_val: {max_val}")
                self.saveImage(clip_image_right, self.template_right_path)
                self.saveImage(image, self.extruder_right_path)
            return True, image, offset, top_left, bottem_right
        
        # 未匹配到模板区域，请清理喷头异物
        return False, image, self.perfect_center, (0,0), (0,0)

    # 开始校准
    def startCalibration(self):
        if os.path.exists(self.template_left_path) == False:
            logging.warning("Left extruder template does not exist, please calibrate manually and save template")
            return False, (0,0)
        elif os.path.exists(self.template_right_path) == False:
            logging.warning("Right extruder template does not exist, please calibrate manually and save template")
            return False, (0,0)
        else:
            logging.info("Starting auto calibration...")
            result, image, offset, top_left, bottem_right = self.startMatch()
            if result == True:
                logging.info(f"Offset distance: {offset}")
                return True, offset
            else:
                logging.error("Auto calibration failed, no template area matched. Please clean the nozzle")
                return False, offset

class Panel(ScreenPanel):
    distances = ['0.02', '.1', '1', '10']
    distance = distances[-2]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.settings = {}
        self.pos = {}
        self.is_home = False
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        self.menu = ['main_menu']
        self.pos['e1_xoffset'] = None
        self.pos['e1_yoffset'] = None
        # 添加校准模式标志
        self.calibration_mode = 'manual'  # 'manual' 或 'auto'
        self.current_calibrating = "left"
        self.left_offset = None

        if self._screen.klippy_config is not None:
            try:
                self.pos['e1_xoffset'] = self._screen.klippy_config.getfloat("Variables", "e1_xoffset")
                self.pos['e1_yoffset'] = self._screen.klippy_config.getfloat("Variables", "e1_yoffset")
            except Exception as e:
                logging.error(f"Read {self._screen.klippy_config_path} error:\n{e}")

        self.buttons = {
            'x+': self._gtk.Button(None, "X+", "color1"),
            'x-': self._gtk.Button(None, "X-", "color1"),
            'y+': self._gtk.Button(None, "Y+", "color2"),
            'y-': self._gtk.Button(None, "Y-", "color2"),
            'z+': self._gtk.Button(None, "Z+", "color3"),
            'z-': self._gtk.Button(None, "Z-", "color3"),
            'home': self._gtk.Button(None, _("Home"), "color4"),
            'motors_off': self._gtk.Button(None, _("Disable Motors"), "color4"),
        }

        self.buttons['x+'].connect("clicked", self.move, "X", "+")
        self.buttons['x-'].connect("clicked", self.move, "X", "-")
        self.buttons['y+'].connect("clicked", self.move, "Y", "+")
        self.buttons['y-'].connect("clicked", self.move, "Y", "-")
        self.buttons['z+'].connect("clicked", self.move, "Z", "+")
        self.buttons['z-'].connect("clicked", self.move, "Z", "-")

        grid = self._gtk.HomogeneousGrid()
        # limit = 2
        i = 0
        self.extruders = [extruder for extruder in self._printer.get_tools()]
        # for extruder in self._printer.get_tools():
        #     if self._printer.extrudercount > 1:
        #         self.labels[extruder] = self._gtk.Button(None, f"T{self._printer.get_tool_number(extruder)}")
        #         self.labels[extruder].connect("clicked", self.change_extruder, extruder)
        #     else:
        #         self.labels[extruder] = self._gtk.Button(None, "extruder")
        #     if extruder == self.current_extruder:
        #         self.labels[extruder].get_style_context().add_class("button_active")
        #     if i < limit:
        #         grid.attach(self.labels[extruder], i, 0, 1, 1)
        #         i += 1
        grid.attach(self.buttons['x+'], 0, 1, 1, 1)
        grid.attach(self.buttons['x-'], 1, 1, 1, 1)
        grid.attach(self.buttons['y+'], 0, 2, 1, 1)
        grid.attach(self.buttons['y-'], 1, 2, 1, 1)

        distgrid = self._gtk.HomogeneousGrid()
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distgrid.attach(self.labels['move_dist'], 0, 0, len(self.distances), 1)            
        for j, i in enumerate(self.distances):
            self.labels[i] = self._gtk.Button(label=i)
            self.labels[i].set_direction(Gtk.TextDirection.LTR)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 1, 1, 1)

        for p in ('pos_x', 'pos_y', 'pos_z'):
            self.labels[p] = Gtk.Label()

        offsetgrid = self._gtk.HomogeneousGrid()
        offsetgrid = Gtk.Grid()
        if CALIBRATION_SUPPORTED:
            # 创建手动和自动校准按钮
            self.labels['manual'] = self._gtk.Button(None, _("Manual Calibrate"), "color1")
            self.labels['auto'] = self._gtk.Button(None, _("Auto Calibrate"), "color2")

        # 添加其他按钮
        self.labels['confirm'] = self._gtk.Button(None, _("Confirm Pos"), "color1")
        self.labels['save'] = self._gtk.Button(None, _("Save"), "color1")
        self.labels['confirm'].connect("clicked", self.confirm_extrude_position)
        self.labels['save'].connect("clicked", self.save_offset)
        offsetgrid.attach(self.labels['confirm'], 0, 0, 1, 1)           
        offsetgrid.attach(self.labels['save'], 1, 0, 1, 1)   

        self.mpv = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for i, cam in enumerate(self._printer.cameras):
            if not cam["enabled"] or cam["name"] != 'calicam':
                continue
            logging.info(cam)
            cam[cam["name"]] = self._gtk.Button(
                image_name="camera", label=_("Start"), style=f"color{i % 4 + 1}",
                scale=self.bts, position=Gtk.PositionType.LEFT, lines=1
            )
            cam[cam["name"]].set_hexpand(True)
            cam[cam["name"]].set_vexpand(True)
            cam[cam["name"]].connect("clicked", self.play, cam)
        if CALIBRATION_SUPPORTED:
            self.labels['manual'].connect("clicked", self.start_manual_calibration, cam)
            self.labels['auto'].connect("clicked",self.start_auto_calibration, cam)
            box.add(self.labels['manual'])
            box.add(self.labels['auto'])
        else:
                box.add(cam[cam["name"]])
        

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(box)
        
        self.labels['main_menu'] = self._gtk.HomogeneousGrid()
        self.labels['main_menu'].attach(self.scroll, 0, 0, 3, 6)
        self.labels['main_menu'].attach(grid, 3, 0, 2, 3)
        self.labels['main_menu'].attach(distgrid, 3, 3, 2, 2)
        self.labels['main_menu'].attach(offsetgrid, 3, 5, 2, 1)

        self.content.add(self.labels['main_menu'])
        self.reset_pos()

        # 只在支持自动校准时初始化校准器
        if CALIBRATION_SUPPORTED:
            ip = "127.0.0.1"
            self.calibrator = MdAutoCalibrator(ip)

    def process_update(self, action, data):
        if action == "notify_gcode_response" and self.calibration_mode == 'auto':
            # 监听 gcode 响应消息
             if "auto_calibration_move_complete" in data:
                logging.info("Received move complete message, waiting 3 seconds before calibration")
                # 使用 GLib.timeout_add 来实现3秒延时
                GLib.timeout_add(3000, self._delayed_calibration)
                if self.current_calibrating == "left":
                    self._screen.show_popup_message(_("Left extruder calibration started"), level=1)
                elif self.current_calibrating == "right":                
                    self._screen.show_popup_message(_("Right extruder calibration started"), level=1)
        
        if action != "notify_status_update":
            return
        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                # self.labels['pos_x'].set_text(f"X: {data['gcode_move']['gcode_position'][0]:.2f}")
                # self.labels['pos_y'].set_text(f"Y: {data['gcode_move']['gcode_position'][1]:.2f}")
                # self.labels['pos_z'].set_text(f"Z: {data['gcode_move']['gcode_position'][2]:.2f}")

                self.pos['x'] = data['gcode_move']['gcode_position'][0]
                self.pos['y'] = data['gcode_move']['gcode_position'][1]
                self.pos['z'] = data['gcode_move']['gcode_position'][2]  
                # text = f"x: {data['gcode_move']['gcode_position'][0]:.2f}, y: {data['gcode_move']['gcode_position'][1]:.2f}, z: {data['gcode_move']['gcode_position'][2]:.2f}"          
        else:
            if "x" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    # self.labels['pos_x'].set_text(f"X: {data['gcode_move']['gcode_position'][0]:.2f}")
                    self.pos['x'] = data['gcode_move']['gcode_position'][0]
            else:
                # self.labels['pos_x'].set_text("X: ?")
                self.pos['x'] = None
            if "y" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    # self.labels['pos_y'].set_text(f"Y: {data['gcode_move']['gcode_position'][1]:.2f}")
                    self.pos['y'] = data['gcode_move']['gcode_position'][1]
            else:
                # self.labels['pos_y'].set_text("Y: ?")
                self.pos['y'] = None
            if "z" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_z'].set_text(f"Z: {data['gcode_move']['gcode_position'][2]:.2f}")
                    self.pos['z'] = data['gcode_move']['gcode_position'][2]
            else:
                # self.labels['pos_z'].set_text("Z: ?")
                self.pos['z'] = None


    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move(self, widget, axis, direction):
        if self._config.get_config()['main'].getboolean(f"invert_{axis.lower()}", False):
            direction = "-" if direction == "+" else "+"

        dist = f"{direction}{self.distance}"
        config_key = "move_speed_z" if axis == "Z" else "move_speed_xy"
        speed = None if self.ks_printer_cfg is None else self.ks_printer_cfg.getint(config_key, None)
        if speed is None:
            speed = self._config.get_config()['main'].getint(config_key, 20)
        speed = 60 * max(1, speed)
        script = f"{KlippyGcodes.MOVE_RELATIVE}\nG0 {axis}{dist} F{speed}"
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup(f"<big><b>{option['name']}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.get_style_context().add_class("frame-item")
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)
        dev.add(name)

        if option['type'] == "binary":
            box = Gtk.Box()
            box.set_vexpand(False)
            switch = Gtk.Switch()
            switch.set_hexpand(False)
            switch.set_vexpand(False)
            switch.set_active(self._config.get_config().getboolean(option['section'], opt_name))
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name)
            switch.set_property("width-request", round(self._gtk.font_size * 7))
            switch.set_property("height-request", round(self._gtk.font_size * 3.5))
            box.add(switch)
            dev.add(box)
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            dev.add(scale)

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()

    def back(self):
        if self.mpv:
            self.mpv.terminate()
            self.mpv = None                    
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False   

    def confirm_extrude_position(self, widget):
        if self._printer.extrudercount < 2:
            self._screen.show_popup_message(_("Only one extruder does not require calibration."), level = 2)
            return        
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        
        # 只在手动校准模式下保存模板
        if self.calibration_mode == 'manual':
            try:
                # 获取摄像头图像并保存为模板
                image = None
                if CALIBRATION_SUPPORTED:
                    image = self.calibrator.getImage(self.calibrator.camera_url)
                if current_extruder == "extruder":
                    # 左喷头模板
                    if image is not None:   
                        self.calibrator.saveTemplateLeft()
                        logging.info("Left extruder template saved")
                        #self._screen.show_popup_message(_("Left extruder template saved"), level=1)
                        
                    # 记录左喷头位置并切换到右喷头
                    self.pos['lx'] = self.pos['x']
                    self.pos['ly'] = self.pos['y']
                    self.pos['lz'] = self.pos['z'] 
                    self._screen.show_popup_message(_("left extruder pos: (%.3f, %.3f, %.3f)") % (self.pos['lx'], self.pos['ly'], self.pos['lz']), level = 1)
                    self.change_extruder(widget, "extruder1")
                    self._calculate_position()
                    
                else:
                    # 右喷头模板
                    if image is not None:
                        self.calibrator.saveTemplateRight()
                        logging.info("Right extruder template saved")
                        #self._screen.show_popup_message(_("Right extruder template saved"), level=1)
                    if self.pos['lx'] is None or self.pos['ly'] is None or self.pos['lz'] is None:
                        self._screen.show_popup_message(_("Please confirm left extruder position."), level = 2)
                    else:
                        self.pos['ox'] = self.pos['x'] - self.pos['lx']
                        self.pos['oy'] = self.pos['y'] - self.pos['ly']
                        self.pos['oz'] = self.pos['z']  - self.pos['lz']
                        self._screen.show_popup_message(_("Right extruder offset is (%.3f, %.3f, %.3f)") % (self.pos['ox'], self.pos['oy'], self.pos['oz']), level = 1)
                    self.labels['save'].set_sensitive(True)                      
            except Exception as e:
                logging.error(f"Error saving template: {e}")
                return
    def change_extruder(self, widget, extruder):
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"T{self._printer.get_tool_number(extruder)}"})
        
    def save_offset(self, widget):      
        if self.pos['e1_xoffset'] is None or self.pos['e1_yoffset'] is None:
            return
        if self.pos['ox'] is None or self.pos['oy'] is None:
            self._screen.show_popup_message(_("Need to recalculate the offset value."), level = 2)
        else:
            # 记录原始值用于调试
            logging.info(f"Raw offset values - ox: {self.pos['ox']}, oy: {self.pos['oy']}")
            self.pos['e1_xoffset'] += self.pos['ox']
            self.pos['e1_yoffset'] += self.pos['oy']
            try:
                self._screen.klippy_config.set("Variables", "e1_xoffset", f"{self.pos['e1_xoffset']:.2f}")
                self._screen.klippy_config.set("Variables", "e1_yoffset", f"{self.pos['e1_yoffset']:.2f}")
                if self.calibration_mode == 'manual':
                    self._screen.klippy_config.set("Variables", "cam_xpos", f"{self.pos['lx']:.2f}")
                    self._screen.klippy_config.set("Variables", "cam_ypos", f"{self.pos['ly']:.2f}")
                logging.info(f"xy offset change to x: {self.pos['e1_xoffset']:.2f} y: {self.pos['e1_yoffset']:.2f}")
                with open(self._screen.klippy_config_path, 'w') as file:
                    self._screen.klippy_config.write(file)
                    if self.mpv:
                        self.mpv.terminate()
                        self.mpv = None
                    self.save_config()                    
                    self._screen._menu_go_back()
            except Exception as e:
                logging.error(f"Error writing configuration file in {self._screen.klippy_config_path}:\n{e}")
                self._screen.show_popup_message(_("Error writing configuration"))
                self.pos['e1_xoffset'] -= self.pos['ox']
                self.pos['e1_yoffset'] -= self.pos['oy']
            
    def play(self, widget, cam):
        url = cam['stream_url']
        if url.startswith('/'):
            logging.info("camera URL is relative")
            endpoint = self._screen.apiclient.endpoint.split(':')
            url = f"{endpoint[0]}:{endpoint[1]}{url}"
        vf = ""
        if cam["flip_horizontal"]:
            vf += "hflip,"
        if cam["flip_vertical"]:
            vf += "vflip,"
        vf += f"rotate:{cam['rotation']*3.14159/180}"
        logging.info(f"video filters: {vf}")

        if check_web_page_access(url) == False:
            self._screen.show_popup_message(_("Please wait for the camera initialization to complete."), level=1)
            return
        self.reset_pos()
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script("G28")
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        if current_extruder != "extruder":
            self.change_extruder(widget=None, extruder="extruder")
        self._calculate_position()


        if self.mpv:
            self.mpv.terminate()
        # self.mpv = mpv.MPV(fullscreen=False, log_handler=self.log, vo='gpu,wlshm,xv,x11', geometry = '400x240')
        # self.mpv = mpv.MPV(fullscreen=True, log_handler=self.log, vo='gpu,xv', wid=str(widget.get_property("window").get_xid()))
        self.mpv = mpv.MPV(fullscreen=True, log_handler=self.log, vo='gpu,wlshm,xv,x11', wid=str(widget.get_property("window").get_xid()))
        self.mpv.vf = vf

        with suppress(Exception):
            self.mpv.profile = 'sw-fast'

        # LOW LATENCY PLAYBACK
        with suppress(Exception):
            self.mpv.profile = 'low-latency'
        self.mpv.untimed = True
        self.mpv.audio = 'no'

        logging.debug(f"Camera URL: {url}")
        self.mpv.loop = True
        self.mpv.play(url)

        try:
            self.mpv.wait_until_playing()
            # self.mpv.wait_for_playback()
        except mpv.ShutdownError:
            logging.info('Exiting Fullscreen')
            return
        except Exception as e:
            logging.exception(e)
            return

        font = ImageFont.truetype('DejaVuSans.ttf', 10)
        font1 = ImageFont.truetype('DejaVuSans.ttf', 12)
        self.overlay = self.mpv.create_image_overlay()
        img = Image.new('RGBA', (400, 150),  (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        base_pos = [80, 0]
        d.text((base_pos[0], base_pos[1]+30), '___________________',font=font, fill=(255, 0, 0, 255))
        d.text((base_pos[0]+90, base_pos[1]+33), '>',font=font1, fill=(255, 0, 0, 255))
        d.text((base_pos[0]+36, base_pos[1]), '^',font=font1, fill=(0, 255, 0, 255))
        for pos in range (base_pos[1], base_pos[1] + 80, 10):
            d.text((base_pos[0]+40, pos), '|', font=font, fill=(0, 255, 0, 255))
        self.overlay.update(img, pos=(40, 65))

    def log(self, loglevel, component, message):
        logging.debug(f'[{loglevel}] {component}: {message}')
        if loglevel == 'error' and 'No Xvideo support found' not in message:
            self._screen.show_popup_message(f'{message}')

    def reset_pos(self):
        self.pos['lx'] = None
        self.pos['ly'] = None
        self.pos['lz'] = None 
        self.pos['rx'] = None
        self.pos['ry'] = None
        self.pos['rz'] = None 
        self.pos['ox'] = None
        self.pos['oy'] = None
        self.pos['oz'] = None 
        self.labels['save'].set_sensitive(False)

    def _calculate_position(self):
        try:
            x_position = self._screen.klippy_config.getfloat("Variables", "cam_xpos")
            y_position = self._screen.klippy_config.getfloat("Variables", "cam_ypos")
            z_position = self._screen.klippy_config.getfloat("Variables", "cam_zpos")            
        except:
            logging.error("Couldn't get the calibration camera position.")
            return
        
        logging.info(f"Moving to X:{x_position} Y:{y_position}")
        script = [
            f"G0 Z{z_position} F600",
            f"G0 X{x_position} Y{y_position} F3000",
            "M400",  # 等待所有移动完成
            "RESPOND TYPE=command MSG=auto_calibration_move_complete"  # 发送移动完成消息
        ]
        self._screen._send_action(None, "printer.gcode.script", 
                                {"script": "\n".join(script)})
        self.pos['z'] = z_position 
        
    def save_config(self):
        script = {"script": "SAVE_CONFIG"}
        self._screen._confirm_send_action(
            None,
            _("Saved successfully!") + "\n\n" + _("Need reboot, relaunch immediately?"),
            "printer.gcode.script",
            script
        )        

    def activate(self):
        symbolic_link = "/home/mingda/printer_data/config/crowsnest.conf"
        source_file = "/home/mingda/printer_data/config/crowsnest2.conf"
        create_symbolic_link(source_file, symbolic_link)
        os.system('sudo systemctl restart crowsnest.service')
        self._screen.show_popup_message(_("Please wait for the camera's fill light to light up for 5 seconds before clicking 'Start'"), level=2)

    def deactivate(self):
        symbolic_link = "/home/mingda/printer_data/config/crowsnest.conf"
        source_file = "/home/mingda/printer_data/config/crowsnest1.conf"
        create_symbolic_link(source_file, symbolic_link)
        # os.system('sudo systemctl restart crowsnest.service')
        subprocess.Popen(["sudo", "systemctl", "restart", "crowsnest.service"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def start_manual_calibration(self, widget, cam):
        """开始手动校准"""
        logging.info("Starting manual calibration")
        self.calibration_mode = 'manual'
        self.labels['confirm'].set_sensitive(True)
        self.buttons['x+'].set_sensitive(True)
        self.buttons['x-'].set_sensitive(True)
        self.buttons['y+'].set_sensitive(True)
        self.buttons['y-'].set_sensitive(True)        
        self.play(widget, cam)
    def start_auto_calibration(self, widget, cam):
        """开始自动校准"""
        logging.info("Starting auto calibration")
        
        # 检查是否存在模板图像
        if not os.path.exists(self.calibrator.template_left_path) or not os.path.exists(self.calibrator.template_right_path):
            logging.error("No template images found")
            self._screen.show_popup_message(
                _("No template images found. Please perform manual calibration first."), 
                level=2
            )
            return
        
        # 开始自动校准
        self.calibration_mode = 'auto'
        self.current_calibrating = "left"
        self.left_offset = None
        self.labels['confirm'].set_sensitive(False)
        self.buttons['x+'].set_sensitive(False)
        self.buttons['x-'].set_sensitive(False)
        self.buttons['y+'].set_sensitive(False)
        self.buttons['y-'].set_sensitive(False)
        self.play(widget, cam)
    def _start_left_calibration(self):
        """开始左喷头校准"""
        logging.info("Starting left calibration")
        result, offset = self.calibrator.startCalibration()
        if result:
            self.left_offset = offset
            # 切换到右喷头继续校准
            self.current_calibrating = "right"
            self.change_extruder(None, "extruder1")
            self._calculate_position()
        else:
            self._screen.show_popup_message(
                _("Left extruder calibration failed. Please clean the nozzle and try again."),
                level=2
            )

    def _start_right_calibration(self):
        """开始右喷头校准"""
        logging.info("Starting right calibration")
        result, offset = self.calibrator.startCalibration()
        if result:
            if self.left_offset is not None:
                self.pos['ox'] = offset[0] - self.left_offset[0]
                self.pos['oy'] = offset[1] - self.left_offset[1]
                self.save_offset(None)
        else:
            self._screen.show_popup_message(
                _("Right extruder calibration failed. Please clean the nozzle and try again."),
                level=2
            )

    def _delayed_calibration(self):
        """延时3秒后执行校准"""
        logging.info("Starting delayed calibration")
        if self.current_calibrating == "left":
            self._start_left_calibration()
        elif self.current_calibrating == "right":
            self._start_right_calibration()
        # 返回 False 以防止重复执行
        return False

def create_symbolic_link(source_path, link_path):
    if os.path.exists(link_path):
        os.remove(link_path)
    try:
        os.symlink(source_path, link_path)
        logging.info(f"Symbolic link created: {link_path} -> {source_path}")
    except OSError as e:
        logging.info(f"Error creating symbolic link: {e}")

def check_web_page_access(url):
    try:
        # Run the curl command to fetch the headers
        result = subprocess.run(["curl", "-I", url], check=True, capture_output=True, text=True, timeout=10)
        
        # Extract the HTTP status code from the result
        status_code = result.stdout.splitlines()[0].split()[1]

        if status_code == "200":
            logging.info(f"The web page at {url} is accessible. Status code: {status_code}")
            return True
        else:
            logging.warning(f"Warning: The web page at {url} returned status code {status_code}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error: The web page at {url} is not accessible. {e}")
    except subprocess.TimeoutExpired:
        logging.error(f"Error: Timeout occurred while checking the web page at {url}.")        
    return False
