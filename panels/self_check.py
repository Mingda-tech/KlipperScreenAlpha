import logging
import os
import gi
import pathlib
# import bed_mesh
import netifaces
import time
import shutil

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    initialized = False

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.themedir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", screen.theme, "images")
        self.image_pass = os.path.join(self.themedir, "check_pass.svg")
        self.image_fail = os.path.join(self.themedir, "check_fail.svg")
        self.image_loading = os.path.join(self.themedir, "loading.gif")
        self.images = []
        self.is_poweroff_resume = 0
        self.fileposition = 0
        self.filename = ""
        self.gcodes_path = None
        if self._screen.klippy_config is not None:
            self.is_poweroff_resume = self._screen.klippy_config.getint("Variables", "resumeflag", fallback=0)
            self.filename = self._screen.klippy_config.get("Variables", "filepath", fallback="")
            self.fileposition = self._screen.klippy_config.getint("Variables", "fileposition", fallback=0)

        self.network_interfaces = netifaces.interfaces()
        self.wireless_interfaces = [iface for iface in self.network_interfaces if iface.startswith('w')]
        self.wifi = None
        self.use_network_manager = os.system('systemctl is-active --quiet NetworkManager.service') == 0
        if len(self.wireless_interfaces) > 0:
            logging.info(f"Found wireless interfaces: {self.wireless_interfaces}")
            if self.use_network_manager:
                logging.info("Using NetworkManager")
                from ks_includes.wifi_nm import WifiManager
            else:
                logging.info("Using wpa_cli")
                from ks_includes.wifi import WifiManager
            self.wifi = WifiManager(self.wireless_interfaces[0])

        self.test_items = ["Nozzle Heating", "Hot Bed Heating", "Nozzle Cooling Fan", "Hotend Cooling Fan", "Filament Detection", "Auto Leveling", "Camera", "WiFi"]
        self.steps = [x for x in range(len(self.test_items))]

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        self.labels['warning'] = Gtk.Label()
        message = _("Do not touch the printer during self-check.")
        self.labels['warning'].set_markup(f'<span foreground="red">{message}</span>')
        grid.attach(self.labels['warning'], 0, 0, 4, 1)
        for i, text in enumerate(self.test_items):
            self.labels[text] = 0
            i = i + 1
            grid.attach(Gtk.Label(), 0, i, 1, 1)
            label = Gtk.Label(label=_(text))
            label.set_vexpand(True)
            grid.attach(label, 1, i, 1, 1)
            image = Gtk.Image()
            image.set_from_file(self.image_loading)
            self.images.append(image)
            grid.attach(image, 2, i, 1, 1)
            grid.attach(Gtk.Label(), 3, i, 1, 1)
        
        self.labels['confirm'] = self._gtk.Button(None, _("Confirm"), "color1")
        self.labels['confirm'].connect("clicked", self.confirm_action)
        grid.attach(self.labels['confirm'], 0, len(self.test_items)+1, 4, 1)

        for i in range(len(self.test_items)):
            self.change_state(i, 1)

        self.is_check = True
        self.tool_target = 50
        self.bed_target = 40
        self.fan_speed = 35
        self.fans = self._printer.get_fans()
        self.start_time = time.time()
        self.time_out = 60     #seconds
        #Nozzle Heating
        for extruder in self._printer.get_tools():
            temp = self._printer.get_dev_stat(extruder, "temperature")
            if temp < self.tool_target:
                self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(extruder), self.tool_target)

        #Bed Headting
        for dev in self._printer.get_heaters():
            if dev == "heater_bed":
                temp = self._printer.get_dev_stat("heater_bed", "temperature")
                if temp < self.bed_target:
                    self.bed_target = temp + 5        
                    self._screen._ws.klippy.set_bed_temp(self.bed_target)  

        #Nozzle Cooling Fan
        for fan in self.fans:
            if fan == "fan":
                speed = self._printer.get_fan_speed(fan) * 100
                if speed < self.fan_speed:
                    self._screen._ws.klippy.gcode_script(f"M106 S{self.fan_speed * 2.55:.0f}")                           

        if self.is_poweroff_resume == 1 and self.filename != "" and self.fileposition != 0:
            if "virtual_sdcard" in self._screen.printer.get_config_section_list():
                vsd = self._screen.printer.get_config_section("virtual_sdcard")
                if "path" in vsd:
                    self.gcodes_path = os.path.expanduser(vsd['path'])
            if self.gcodes_path is not None:
                self.filename = self.filename.replace("'", "")
                src = os.path.join(self.gcodes_path, self.filename)
                dst = os.path.join(self.gcodes_path, "plr.gcode")                
                GLib.idle_add(self.copy_gcode, src, dst)

        self.content.add(grid)        

    def remove_all_dialog(self):
        self.close_screensaver()
        for dialog in self.screen.dialogs:
            self.remove_dialog(dialog)
    
    def change_state(self, step, state):
        if step < 0 and step > len(self.steps):
            return
        imagePath = self.image_loading
        if state == -1:
            imagePath = self.image_fail
        elif state == 0:
            imagePath = self.image_pass
        self.images[step].set_from_file(imagePath)

    def self_test(self):        
        for step in self.steps:
            is_ok = False
            if step == 0:
                for extruder in self._printer.get_tools():
                    is_ok = True
                    temp = self._printer.get_dev_stat(extruder, "temperature")
                    if temp < self.tool_target:
                        is_ok = False
                        break
            elif step == 1:
                for dev in self._printer.get_heaters():
                    is_ok = True
                    if dev == "heater_bed":
                        temp = self._printer.get_dev_stat("heater_bed", "temperature")
                        if temp < self.bed_target:
                            is_ok = False
                            break
            elif step == 2:
                for fan in self.fans:
                    is_ok = True
                    if fan == "fan":
                        speed = self._printer.get_fan_speed("fan") * 100
                        if speed < self.fan_speed-5:
                            is_ok = False
                            break
            elif step == 3:
                for fan in self.fans:
                    is_ok = True
                    if 'hotend' in fan.lower():
                        speed = self._printer.get_fan_speed(fan) * 100                        
                        if speed < self.fan_speed-5:
                            is_ok = False
                            break
            elif step == 4:
                filament_sensors = self._printer.get_filament_sensors()
                for fs in filament_sensors:
                    is_ok = True
                    if self._printer.get_stat(fs, "enabled") :
                        if not self._printer.get_stat(fs, "filament_detected"):
                            is_ok = False
                            break
                    else:
                        is_ok = False
                        break
            elif step == 5:
                is_ok = False
                bm = self._printer.get_stat("bed_mesh")
                if bm is not None and self._printer.get_stat("bed_mesh", "profile_name") != '':
                    is_ok = True
                                            
            elif step == 6:
                for i, cam in enumerate(self._printer.cameras):
                    is_ok = os.path.exists(f"/dev/video{2*i}")
                    if not cam["enabled"]:
                        is_ok = False
                        break
            elif step == 7:
                is_ok = False
                connected_ssid = self.wifi.get_connected_ssid()
                if connected_ssid is not None:
                    is_ok = True

            if is_ok:
                GLib.idle_add(self.change_state, step, 0)
                self.steps.remove(step)

        end_time = time.time()
        elapsed_time = end_time - self.start_time
        if(self.time_out < elapsed_time):
            for step in self.steps:
                GLib.idle_add(self.change_state, step, -1)
                self.steps.remove(step)

    def confirm_action(self, widget):
        self._screen._ws.klippy.gcode_script("TURN_OFF_HEATERS")                           
        self._screen._ws.klippy.gcode_script("M106 S0")                           
        self._screen.show_panel("main_menu", None, remove_all=True, items=self._config.get_menu_items("__main"))
        if self.is_poweroff_resume == 1 and self.filename != "" and self.fileposition != 0:
            if self._screen._ws.connected:
                script = {"script": "POWEROFF_RESUME"}
                self._screen._confirm_send_action(None,
                                              _("Power loss recovery, is resume print?"),
                                              "printer.gcode.script", script)                          
        self.is_poweroff_resume = 0

    def process_update(self, action, data):
        if action == "notify_status_update":
            self.self_test()
            
    def copy_gcode(self, src, dst):
        shutil.copy2(src, dst)