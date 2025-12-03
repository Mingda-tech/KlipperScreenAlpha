import logging
import gi
import os
import subprocess
import mpv
from contextlib import suppress
from PIL import Image, ImageDraw, ImageFont
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


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
        self.labels['confirm'] = self._gtk.Button(None, _("Confirm Pos"), "color1")
        self.labels['save'] = self._gtk.Button(None, "Save", "color1")

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

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            # Use toolhead position (raw coordinates without offsets) instead of gcode_position
            if "toolhead" in data and "position" in data["toolhead"]:
                self.pos['x'] = data['toolhead']['position'][0]
                self.pos['y'] = data['toolhead']['position'][1]
                self.pos['z'] = data['toolhead']['position'][2]  
        else:
            if "x" in homed_axes:
                if "toolhead" in data and "position" in data["toolhead"]:
                    self.pos['x'] = data['toolhead']['position'][0]
            else:
                self.pos['x'] = None
            if "y" in homed_axes:
                if "toolhead" in data and "position" in data["toolhead"]:
                    self.pos['y'] = data['toolhead']['position'][1]
            else:
                self.pos['y'] = None
            if "z" in homed_axes:
                if "toolhead" in data and "position" in data["toolhead"]:
                    self.pos['z'] = data['toolhead']['position'][2]
            else:
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
            # Execute macro to turn off calibration camera light when exiting
            self._screen._ws.klippy.gcode_script("XY_CALIBRATION_LIGHT_OFF")
            logging.info("Executing XY_CALIBRATION_LIGHT_OFF macro")
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False   

    def confirm_extrude_position(self, widget):
        if self._printer.extrudercount < 2:
            self._screen.show_popup_message(_("Only one extruder does not require calibration."), level = 2)
            return
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")

        if self._printer.get_tool_number(self.current_extruder) == 0:
            self.pos['lx'] = self.pos['x']
            self.pos['ly'] = self.pos['y']
            self.pos['lz'] = self.pos['z'] 
            self._screen.show_popup_message(f"left extruder pos: ({self.pos['lx']:.2f}, {self.pos['ly']:.2f}, {self.pos['lz']:.2f})", level = 1)
            self.change_extruder(widget, "extruder1")
            self._calculate_position()
        elif self._printer.get_tool_number(self.current_extruder) == 1:
            if self.pos['lx'] is None or self.pos['ly'] is None or self.pos['lz'] is None:
                self._screen.show_popup_message(f"Please confirm left extruder position.", level = 2)
            else:
                self.pos['ox'] = self.pos['x'] - self.pos['lx']
                self.pos['oy'] = self.pos['y'] - self.pos['ly']
                self.pos['oz'] = self.pos['z']  - self.pos['lz']
                self._screen.show_popup_message(f"Right extruder offset is ({self.pos['ox']:.2f}, {self.pos['oy']:.2f}, {self.pos['oz']:.2f})", level = 1)
                self.labels['save'].set_sensitive(True)                      

    def change_extruder(self, widget, extruder):
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"T{self._printer.get_tool_number(extruder)}"})
        
    def save_offset(self, widget):      
        if self.pos['ox'] is None or self.pos['oy'] is None:
            self._screen.show_popup_message(_("Need to recalculate the offset value."), level = 2)
            return
        
        try:
            self._screen.klippy_config.set("Variables", "idex_xoffset", f"{self.pos['ox']:.2f}")
            self._screen.klippy_config.set("Variables", "idex_yoffset", f"{self.pos['oy']:.2f}")
            self._screen.klippy_config.set("Variables", "cam_xpos", f"{self.pos['lx']:.2f}")
            self._screen.klippy_config.set("Variables", "cam_ypos", f"{self.pos['ly']:.2f}")
            logging.info(f"xy offset set to x: {self.pos['ox']:.2f} y: {self.pos['oy']:.2f}")
            with open(self._screen.klippy_config_path, 'w') as file:
                self._screen.klippy_config.write(file)
                if self.mpv:
                    self.mpv.terminate()
                    self.mpv = None
                    # Execute macro to turn off calibration camera light when saving
                    self._screen._ws.klippy.gcode_script("XY_CALIBRATION_LIGHT_OFF")
                    logging.info("Executing XY_CALIBRATION_LIGHT_OFF macro")
                self.save_config()                    
                self._screen._menu_go_back()
        except Exception as e:
            logging.error(f"Error writing configuration file in {self._screen.klippy_config_path}:\n{e}")
            self._screen.show_popup_message(_("Error writing configuration"))
            
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
        
        # Execute macro to turn on calibration camera light
        self._screen._ws.klippy.gcode_script("XY_CALIBRATION_LIGHT_ON")
        logging.info("Executing XY_CALIBRATION_LIGHT_ON macro")
        
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

        self.overlay = self.mpv.create_image_overlay()
        
        # Get the video dimensions (assuming standard camera resolution)
        # You may need to adjust these values based on actual camera resolution
        video_width = 640  # Adjust based on your camera resolution
        video_height = 480  # Adjust based on your camera resolution
        
        # Create overlay image with full video dimensions
        img = Image.new('RGBA', (video_width, video_height),  (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        
        # Draw XY coordinate system
        center_x = video_width // 2 + 20
        center_y = video_height // 2 + 130
        axis_length = 200  # 200 pixels length for each axis
        x_axis_color = (255, 0, 0, 255)  # Red color for X axis (horizontal)
        y_axis_color = (0, 255, 0, 255)  # Green color for Y axis (vertical)
        line_width = 1  # Thinner line width
        arrow_size = 10  # Size of arrow head
        
        # Draw X axis (horizontal line - red)
        d.line([(center_x - axis_length, center_y), 
                (center_x + axis_length, center_y)], 
               fill=x_axis_color, width=line_width)
        
        # Draw X axis arrow (right side)
        d.polygon([(center_x + axis_length, center_y),
                   (center_x + axis_length - arrow_size, center_y - arrow_size//2),
                   (center_x + axis_length - arrow_size, center_y + arrow_size//2)],
                  fill=x_axis_color)
        
        # Draw Y axis (vertical line - green)
        d.line([(center_x, center_y - axis_length), 
                (center_x, center_y + axis_length)], 
               fill=y_axis_color, width=line_width)
        
        # Draw Y axis arrow (top side - pointing up for positive Y)
        d.polygon([(center_x, center_y - axis_length),
                   (center_x - arrow_size//2, center_y - axis_length + arrow_size),
                   (center_x + arrow_size//2, center_y - axis_length + arrow_size)],
                  fill=y_axis_color)
        
        self.overlay.update(img, pos=(0, 0))

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
        self._screen._ws.klippy.gcode_script(f'G0 Z{z_position} F3000')
        self._screen._ws.klippy.gcode_script(f'G0 X{x_position} Y{y_position} F3000')
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
        # Execute macro to turn off calibration camera light when deactivating
        self._screen._ws.klippy.gcode_script("XY_CALIBRATION_LIGHT_OFF")
        logging.info("Executing XY_CALIBRATION_LIGHT_OFF macro")
        
        symbolic_link = "/home/mingda/printer_data/config/crowsnest.conf"
        source_file = "/home/mingda/printer_data/config/crowsnest1.conf"
        create_symbolic_link(source_file, symbolic_link)
        # os.system('sudo systemctl restart crowsnest.service')
        subprocess.Popen(["sudo", "systemctl", "restart", "crowsnest.service"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


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
        # Run the curl command to fetch the headers, following redirects
        result = subprocess.run(["curl", "-I", "-L", url], check=True, capture_output=True, text=True, timeout=10)

        # Extract the final HTTP status code (last response when redirects occur)
        lines = [line for line in result.stdout.splitlines() if line.startswith('HTTP/')]
        if lines:
            status_code = lines[-1].split()[1]
        else:
            logging.warning(f"Could not parse HTTP status from curl output")
            return False

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
