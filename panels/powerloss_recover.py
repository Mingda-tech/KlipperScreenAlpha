# -*- coding: utf-8 -*-
import logging
import gi
import os
import configparser

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.menu = ['powerloss_recover']
        self.filename = None
        self.print_state_file = "/home/mingda/printer_data/config/print_state.cfg"
        self.resume_button = None
        self.tip_label = None
        
        # Calculate sizes based on screen resolution
        self.width = self._gtk.content_width
        self.height = self._gtk.content_height
        
        # Calculate optimal sizes
        self.button_height = self.height // 12  # 按钮高度为屏幕高度的1/12
        self.margin = min(20, self.width // 50)  # 边距最大20，或可用宽度的1/50

        # 计算实际可用宽度（考虑所有边距）
        total_margin_width = self.margin * 4  # 左右两侧的外边距 + 中间分隔的边距
        available_width = self.width - total_margin_width
        
        # 重新计算预览区域和信息区域的宽度
        self.preview_size = min(available_width // 3, self.height // 2)  # 调整预览图尺寸
        info_area_width = available_width - self.preview_size - self.margin  # 信息区域的可用宽度
        
        # Create main grid layout
        main_grid = Gtk.Grid()
        main_grid.set_row_spacing(self.margin // 2)
        main_grid.set_column_spacing(self.margin)
        main_grid.set_margin_start(self.margin)
        main_grid.set_margin_end(self.margin)
        main_grid.set_margin_top(self.margin)
        main_grid.set_margin_bottom(self.margin)

        # Left preview area and button container
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.margin)
        left_box.set_halign(Gtk.Align.CENTER)
        
        # Preview frame
        preview_frame = Gtk.Frame()
        preview_frame.set_size_request(self.preview_size, self.preview_size)
        
        # Create preview container
        preview_box = Gtk.Box()
        preview_box.set_size_request(self.preview_size, self.preview_size)
        preview_box.set_halign(Gtk.Align.CENTER)
        preview_box.set_valign(Gtk.Align.CENTER)
        
        # Create preview image
        self.preview_image = Gtk.Image()
        self.preview_image.set_size_request(self.preview_size - self.margin, 
                                          self.preview_size - self.margin)
        
        preview_box.pack_start(self.preview_image, True, True, self.margin // 2)
        preview_frame.add(preview_box)
        left_box.pack_start(preview_frame, False, False, 0)

        # Resume print button
        self.resume_button = self._gtk.Button("resume", _("Power Loss Recovery"), "color2")
        self.resume_button.connect("clicked", self.resume_print)
        self.resume_button.set_size_request(min(self.preview_size, 200), self.button_height)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.pack_start(self.resume_button, False, False, 0)
        left_box.pack_start(button_box, False, False, 0)

        main_grid.attach(left_box, 0, 0, 1, 6)

        # Right info area
        info_grid = Gtk.Grid()
        info_grid.set_row_spacing(self.margin)
        info_grid.set_column_spacing(self.margin)
        info_grid.set_margin_start(self.margin)
        info_grid.set_vexpand(True)  # 允许垂直扩展
        info_grid.set_valign(Gtk.Align.FILL)  # 填充整个可用空间
        info_grid.set_size_request(-1, self.preview_size)  # 设置与预览图相同的高度
        
        # Calculate label sizes
        label_width = (info_area_width - self.margin * 2) // 2  # 考虑标签之间的间距
        info_height = self.preview_size  # 与预览图等高
        row_height = (info_height - self.margin * 5) // 6  # 6行信息，5个间隔
        
        # Filename (占用两列宽度)
        filename_label = Gtk.Label(label=_("Filename:"), halign=Gtk.Align.START)
        filename_label.set_size_request(label_width, -1)
        filename_label.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(filename_label, 0, 0, 2, 1)
        
        self.filename_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.filename_value.set_size_request(label_width * 2, -1)  # 两倍宽度
        self.filename_value.set_line_wrap(True)
        self.filename_value.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.filename_value.set_justify(Gtk.Justification.LEFT)
        self.filename_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(self.filename_value, 0, 1, 2, 1)  # 占用下一行的两列

        # Print height
        height_label = Gtk.Label(label=_("Print Height:"), halign=Gtk.Align.START)
        height_label.set_size_request(label_width, -1)
        height_label.set_vexpand(True)  # 允许垂直扩展
        self.height_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.height_value.set_size_request(label_width, -1)
        self.height_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(height_label, 0, 2, 1, 1)
        info_grid.attach(self.height_value, 1, 2, 1, 1)

        # Nozzle temperature
        nozzle_label = Gtk.Label(label=_("Nozzle Temp:"), halign=Gtk.Align.START)
        nozzle_label.set_size_request(label_width, -1)
        nozzle_label.set_vexpand(True)  # 允许垂直扩展
        self.nozzle_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.nozzle_value.set_size_request(label_width, -1)
        self.nozzle_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(nozzle_label, 0, 3, 1, 1)
        info_grid.attach(self.nozzle_value, 1, 3, 1, 1)

        # Bed temperature
        bed_label = Gtk.Label(label=_("Bed Temp:"), halign=Gtk.Align.START)
        bed_label.set_size_request(label_width, -1)
        bed_label.set_vexpand(True)  # 允许垂直扩展
        self.bed_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.bed_value.set_size_request(label_width, -1)
        self.bed_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(bed_label, 0, 4, 1, 1)
        info_grid.attach(self.bed_value, 1, 4, 1, 1)

        # Active extruder
        extruder_label = Gtk.Label(label=_("Active Extruder:"), halign=Gtk.Align.START)
        extruder_label.set_size_request(label_width, -1)
        extruder_label.set_vexpand(True)  # 允许垂直扩展
        self.extruder_value = Gtk.Label(label="", halign=Gtk.Align.START)
        self.extruder_value.set_size_request(label_width, -1)
        self.extruder_value.set_vexpand(True)  # 允许垂直扩展
        info_grid.attach(extruder_label, 0, 5, 1, 1)
        info_grid.attach(self.extruder_value, 1, 5, 1, 1)

        # Set properties for all labels
        for child in info_grid.get_children():
            if isinstance(child, Gtk.Label):
                child.set_line_wrap(True)
                child.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                child.set_valign(Gtk.Align.CENTER)  # 垂直居中对齐

        main_grid.attach(info_grid, 1, 0, 1, 6)

        # Tip message (占满整行)
        tip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tip_box.set_hexpand(True)  # 水平方向扩展
        tip_box.set_halign(Gtk.Align.FILL)
        
        self.tip_label = Gtk.Label()
        self.tip_label.set_markup(
            f"<span foreground='orange'>{_('Tip: Please ensure the nozzle is about 0.1mm above the model')}</span>"
        )
        self.tip_label.set_halign(Gtk.Align.CENTER)
        self.tip_label.set_hexpand(True)  # 标签也设置为扩展
        self.tip_label.set_line_wrap(True)
        self.tip_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.tip_label.set_justify(Gtk.Justification.CENTER)
        
        tip_box.pack_start(self.tip_label, True, True, 0)
        main_grid.attach(tip_box, 0, 6, 2, 1)

        # Make the main grid expand to fill available space
        main_grid.set_vexpand(True)
        main_grid.set_hexpand(True)
        
        self.content.add(main_grid)
        
        # Load power loss recovery info on initialization
        self.load_powerloss_info()

    def get_file_image(self, filename, width, height):
        """获取文件预览图"""
        if filename is None:
            logging.info("Filename is None, cannot get thumbnail")
            return None
            
        logging.info(f"Trying to get thumbnail for file: {filename}")
        
        # 确保文件名编码正确
        filename = filename.strip()
        logging.info(f"Sanitized filename: {filename}")
        
        # 检查是否有缩略图
        has_thumb = self._files.has_thumbnail(filename)
        logging.info(f"Has thumbnail: {has_thumb}")
        
        def scale_pixbuf(pixbuf, target_width, target_height):
            """缩放图片以适应目标尺寸，保持宽高比"""
            img_width = pixbuf.get_width()
            img_height = pixbuf.get_height()
            scale_ratio = min(target_width / img_width, target_height / img_height)
            new_width = int(img_width * scale_ratio)
            new_height = int(img_height * scale_ratio)
            return pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)
        
        if has_thumb:
            loc = self._files.get_thumbnail_location(filename)
            logging.info(f"Thumbnail location: {loc}")
            
            if loc and loc[0] == "file":
                # 本地文件缩略图
                thumb_path = loc[1]
                logging.info(f"Loading local thumbnail from: {thumb_path}")
                # 检查文件是否存在
                if os.path.exists(thumb_path):
                    logging.info(f"Thumbnail file exists at: {thumb_path}")
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file(thumb_path)
                        return scale_pixbuf(pixbuf, width, height)
                    except Exception as e:
                        logging.error(f"Error loading thumbnail: {str(e)}")
                else:
                    logging.error(f"Thumbnail file not found at: {thumb_path}")
            if loc and loc[0] == "http":
                # HTTP缩略图
                logging.info(f"Loading HTTP thumbnail from: {loc[1]}")
                try:
                    pixbuf = self._gtk.PixbufFromHttp(loc[1])
                    return scale_pixbuf(pixbuf, width, height)
                except Exception as e:
                    logging.error(f"Error loading HTTP thumbnail: {str(e)}")
        
        # 如果没有找到缩略图，尝试直接查找 .thumbs 目录
        gcode_dir = os.path.dirname(self.print_state_file).replace('config', 'gcodes')
        thumbs_dir = os.path.join(gcode_dir, '.thumbs')
        base_name = os.path.basename(filename)
        
        # 按优先级尝试不同尺寸的缩略图
        thumb_sizes = ['300x300', '48x48', '32x32']
        for size in thumb_sizes:
            thumb_pattern = f"{base_name.rsplit('.', 1)[0]}-{size}.png"
            direct_thumb_path = os.path.join(thumbs_dir, thumb_pattern)
            
            logging.info(f"Trying direct thumbnail path: {direct_thumb_path}")
            if os.path.exists(direct_thumb_path):
                logging.info(f"Found thumbnail directly at: {direct_thumb_path}")
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(direct_thumb_path)
                    return scale_pixbuf(pixbuf, width, height)
                except Exception as e:
                    logging.error(f"Error loading direct thumbnail: {str(e)}")
                    continue
        
        logging.info("No thumbnail found through any method")
        return None

    def update_preview_image(self):
        """更新预览图"""
        try:
            if self.filename is None:
                logging.info("No filename available for preview image")
                self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
                return
                
            logging.info(f"Updating preview image for file: {self.filename}")
            # 计算实际显示尺寸
            display_size = self.preview_size - (self.margin * 2)  # 考虑边距
            logging.info(f"Display size for preview: {display_size}x{display_size}")
            
            # 获取预览图
            pixbuf = self.get_file_image(self.filename, display_size, display_size)
            if pixbuf is not None:
                logging.info(f"Successfully loaded preview image: {pixbuf.get_width()}x{pixbuf.get_height()}")
                self.preview_image.set_from_pixbuf(pixbuf)
            else:
                logging.info("No preview image available, using default icon")
                self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
        except Exception as e:
            logging.exception(f"Failed to load preview image: {str(e)}")
            self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

    def check_recovery_info(self, config):
        """检查恢复信息是否完整"""
        missing_items = []
        warnings = []
        
        # 检查文件路径
        try:
            if not config.get("print_state", "file_path"):
                missing_items.append(_("Filename"))
        except:
            missing_items.append(_("Filename"))
            
        # 检查打印高度
        try:
            z_position = float(config.get("position", "z"))
            if not z_position:
                missing_items.append(_("Print Height"))
            elif z_position < 5:  # 检查打印高度是否小于5mm
                warnings.append(_("Print height is less than 5mm"))
        except:
            missing_items.append(_("Print Height"))
            
        # 检查温度信息
        has_extruder_temp = False
        try:
            if config.has_option("temperatures", "extruder1"):
                has_extruder_temp = True
            elif config.has_option("temperatures", "extruder"):
                has_extruder_temp = True
        except:
            pass
        
        if not has_extruder_temp:
            missing_items.append(_("Nozzle Temperature"))
            
        try:
            if not config.has_option("temperatures", "bed"):
                missing_items.append(_("Bed Temperature"))
        except:
            missing_items.append(_("Bed Temperature"))
            
        # 检查活跃喷头
        try:
            if not config.get("extruder", "active_extruder"):
                missing_items.append(_("Active Extruder"))
        except:
            missing_items.append(_("Active Extruder"))
            
        return missing_items, warnings

    def update_ui_state(self, missing_items, warnings=None):
        """更新UI状态"""
        if missing_items or warnings:
            # 禁用恢复按钮
            self.resume_button.set_sensitive(False)
            
            # 更新提示信息
            if missing_items:
                missing_info = ", ".join(missing_items)
                self.tip_label.set_markup(
                    f"<span foreground='red'>{_('Missing required information')}: {missing_info}</span>"
                )
            elif warnings:
                warning_info = ", ".join(warnings)
                self.tip_label.set_markup(
                    f"<span foreground='red'>{warning_info}</span>"
                )
        else:
            # 启用恢复按钮
            self.resume_button.set_sensitive(True)
            
            # 恢复默认提示
            self.tip_label.set_markup(
                f"<span foreground='orange'>{_('Tip: Please ensure the nozzle is about 0.1mm above the model')}</span>"
            )

    def load_powerloss_info(self):
        """Load power loss recovery information"""
        if not os.path.exists(self.print_state_file):
            logging.error(f"Print state file not found: {self.print_state_file}")
            self.update_ui_state([_("Recovery File")], [])
            return
            
        try:
            config = configparser.ConfigParser()
            config.read(self.print_state_file)
            
            # 检查恢复信息是否完整
            missing_items, warnings = self.check_recovery_info(config)
            self.update_ui_state(missing_items, warnings)
            
            if missing_items:
                logging.warning(f"Missing recovery information: {', '.join(missing_items)}")
                return
                
            if warnings:
                logging.warning(f"Recovery warnings: {', '.join(warnings)}")
                return
            
            # Get file information
            self.filename = config.get("print_state", "file_path")
            logging.info(f"Original filename from print_state: {self.filename}")
            
            # 处理文件路径，提取相对路径部分
            if "/gcodes/" in self.filename:
                self.filename = self.filename.split("/gcodes/")[-1]
                logging.info(f"Filename after extracting relative path: {self.filename}")
            
            # 确保文件名没有前后空格
            self.filename = self.filename.strip()
            self.filename_value.set_label(os.path.basename(self.filename))
            
            # Get position information
            z_position = float(config.get("position", "z"))
            self.height_value.set_label(f"{z_position:.2f} mm")
            
            # Get temperature information
            # 检查配置文件中的温度节点名称
            if config.has_option("temperatures", "extruder1"):
                extruder_temp = int(float(config.get("temperatures", "extruder1")))
            elif config.has_option("temperatures", "extruder"):
                extruder_temp = int(float(config.get("temperatures", "extruder")))
            else:
                extruder_temp = 0
            self.nozzle_value.set_label(f"{extruder_temp}℃")
            
            bed_temp = int(float(config.get("temperatures", "bed", fallback="0")))
            self.bed_value.set_label(f"{bed_temp}℃")
            
            # Get active extruder
            active_extruder = config.get("extruder", "active_extruder", fallback="extruder")
            self.extruder_value.set_label(active_extruder)
            
            # Update preview image
            self.update_preview_image()
            
        except Exception as e:
            logging.exception(f"Failed to load power loss recovery info: {str(e)}")

    def resume_print(self, widget):
        """Resume printing"""
        if self.filename is None:
            return
            
        logging.info("Starting to resume print...")
        
        # Send resume print command
        script = [
            "M84\n",
            "RESTORE_PRINT\n"
        ]
        self._screen._send_action(widget, "printer.gcode.script", {"script": "\n".join(script)})
        self._screen.state_printing()
    def activate(self):
        """每次进入面板时调用"""
        # 清空所有显示的值
        self.filename = None
        self.filename_value.set_label("")
        self.height_value.set_label("")
        self.nozzle_value.set_label("")
        self.bed_value.set_label("")
        self.extruder_value.set_label("")
        self.preview_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
        
        # 重新加载断电续打信息
        self.load_powerloss_info()