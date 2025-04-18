#!/usr/bin/python

import argparse
import json
import logging
import os
import subprocess
import pathlib
import traceback  # noqa
import locale
import sys
import gi
import configparser
import threading

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from importlib import import_module
from jinja2 import Environment
from signal import SIGTERM
from datetime import datetime

from ks_includes import functions
from ks_includes.KlippyWebsocket import KlippyWebsocket
from ks_includes.KlippyRest import KlippyRest
from ks_includes.files import KlippyFiles
from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.printer import Printer
from ks_includes.widgets.keyboard import Keyboard
from ks_includes.config import KlipperScreenConfig
from panels.base_panel import BasePanel

logging.getLogger("urllib3").setLevel(logging.WARNING)

PRINTER_BASE_STATUS_OBJECTS = [
    'bed_mesh',
    'configfile',
    'display_status',
    'extruder',
    'fan',
    'gcode_move',
    'heater_bed',
    'idle_timeout',
    'pause_resume',
    'print_stats',
    'toolhead',
    'virtual_sdcard',
    'webhooks',
    'motion_report',
    'firmware_retraction',
    'exclude_object',
    'manual_probe',
]

klipperscreendir = pathlib.Path(__file__).parent.resolve()


def set_text_direction(lang=None):
    rtl_languages = ['he']
    if lang is None:
        for lng in rtl_languages:
            if locale.getlocale()[0].startswith(lng):
                lang = lng
                break
    if lang in rtl_languages:
        Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        logging.debug("Enabling RTL mode")
        return False
    Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)
    return True


def state_execute(callback):
    callback()
    return False


class KlipperScreen(Gtk.Window):
    """ Class for creating a screen for Klipper via HDMI """
    _cur_panels = []
    connecting = False
    connecting_to_printer = None
    connected_printer = None
    files = None
    keyboard = None
    panels = {}
    popup_message = None
    screensaver = None
    printers = printer = None
    updating = False
    _ws = None
    screensaver_timeout = None
    reinit_count = 0
    max_retries = 4
    initialized = initializing = False
    popup_timeout = None
    wayland = False
    windowed = False
    notification_log = []
    auto_check = True
    def __init__(self, args):
        try:
            super().__init__(title="KlipperScreen")
        except Exception as e:
            logging.exception(f"{e}\n\n{traceback.format_exc()}")
            raise RuntimeError from e
        self.blanking_time = 600
        self.use_dpms = True
        self.apiclient = None
        self.dialogs = []
        self.confirm = None
        self.panels_reinit = []
        self.manual_settings = {}

        configfile = os.path.normpath(os.path.expanduser(args.configfile))

        self._config = KlipperScreenConfig(configfile, self)
        self.lang_ltr = set_text_direction(self._config.get_main_config().get("language", None))
        self.env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
        self.env.install_gettext_translations(self._config.get_lang())

        self.connect("key-press-event", self._key_press_event)
        # self.connect("configure_event", self.update_size)
        monitor = Gdk.Display.get_default().get_primary_monitor()
        if monitor is None:
            self.wayland = True
            monitor = Gdk.Display.get_default().get_monitor(0)
        if monitor is None:
            raise RuntimeError("Couldn't get default monitor")
        self.width = self._config.get_main_config().getint("width", None)
        self.height = self._config.get_main_config().getint("height", None)
        if 'XDG_CURRENT_DESKTOP' in os.environ:
            logging.warning("Running inside a desktop environment is not recommended")
            if not self.width:
                self.width = max(int(monitor.get_geometry().width * .5), 480)
            if not self.height:
                self.height = max(int(monitor.get_geometry().height * .5), 320)
        if self.width or self.height:
            logging.info("Setting windowed mode")
            self.set_resizable(True)
            self.windowed = True
        else:
            self.width = monitor.get_geometry().width
            self.height = monitor.get_geometry().height
            self.fullscreen()
        self.set_default_size(self.width, self.height)
        self.aspect_ratio = self.width / self.height
        self.vertical_mode = self.aspect_ratio < 1.0
        logging.info(f"Screen resolution: {self.width}x{self.height}")
        self.theme = self._config.get_main_config().get('theme', "colorized")
           
        self.show_cursor = self._config.get_main_config().getboolean("show_cursor", fallback=False)
        self.gtk = KlippyGtk(self)
        self.init_style()
        self.set_icon_from_file(os.path.join(klipperscreendir, "styles", "icon.svg"))

        self.base_panel = BasePanel(self, title="Base Panel")
        self.add(self.base_panel.main_grid)
        self.show_all()
        if self.show_cursor:
            self.get_window().set_cursor(
                Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.ARROW))
            os.system("xsetroot  -cursor_name  arrow")
        else:
            self.get_window().set_cursor(
                Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.BLANK_CURSOR))
            os.system("xsetroot  -cursor ks_includes/emptyCursor.xbm ks_includes/emptyCursor.xbm")
        self.base_panel.activate()
        if self._config.errors:
            self.show_error_modal("Invalid config file", self._config.get_errors())
            # Prevent this dialog from being destroyed
            self.dialogs = []
        self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking'))
        self.log_notification("KlipperScreen Started", 1)
        self.initial_connection()

        self.setup_init = 0
        self.klippy_config_path = None
        self.klippy_config = None
        self.is_show_manual = True
        
    def load_klipper_config(self):
        try:
            variables = self.printer.get_config_section("save_variables")
            
            if "filename" in variables:
                self.klippy_config_path = os.path.expanduser(variables['filename'])
            if self.klippy_config_path is not None:
                self.klippy_config = configparser.ConfigParser()
                self.klippy_config.read(self.klippy_config_path)
                if not self.klippy_config.has_section("Variables"):
                    self.klippy_config = None
        except KeyError as Kerror:
            msg = f"Error reading config: {self.config_path}\n{Kerror}"
            logging.exception(msg)
        except ValueError as Verror:
            msg = f"Invalid Value in the config:\n{Verror}"
            logging.exception(msg)
        except Exception as e:
            msg = f"Unknown error with the config:\n{e}"
            logging.exception(msg)

    def initial_connection(self):
        self.printers = self._config.get_printers()
        state_callbacks = {
            "disconnected": self.state_disconnected,
            "error": self.state_error,
            "paused": self.state_paused,
            "printing": self.state_printing,
            "ready": self.state_ready,
            "startup": self.state_startup,
            "shutdown": self.state_shutdown
        }
        for printer in self.printers:
            printer["data"] = Printer(state_execute, state_callbacks, self.process_busy_state)
        default_printer = self._config.get_main_config().get('default_printer')
        logging.debug(f"Default printer: {default_printer}")
        if [True for p in self.printers if default_printer in p]:
            self.connect_printer(default_printer)
        elif len(self.printers) == 1:
            pname = list(self.printers[0])[0]
            self.connect_printer(pname)
        else:
            self.base_panel.show_printer_select(True)
            self.show_printer_select()

    def connect_printer(self, name):
        self.connecting_to_printer = name
        if self._ws is not None and self._ws.connected:
            self._ws.close()
            self.connected_printer = None
            self.printer.state = "disconnected"
            if self.files:
                self.files.reset()
                self.files = None

        self.connecting = True
        self.initialized = False

        ind = 0
        logging.info(f"Connecting to printer: {name}")
        for printer in self.printers:
            if name == list(printer)[0]:
                ind = self.printers.index(printer)
                break

        self.printer = self.printers[ind]["data"]
        self.apiclient = KlippyRest(
            self.printers[ind][name]["moonraker_host"],
            self.printers[ind][name]["moonraker_port"],
            self.printers[ind][name]["moonraker_api_key"],
        )

        self.printer_initializing(_("Connecting to %s") % name, remove=True)

        self._ws = KlippyWebsocket(self,
                                   {
                                       "on_connect": self.init_printer,
                                       "on_message": self._websocket_callback,
                                       "on_close": self.websocket_disconnected
                                   },
                                   self.printers[ind][name]["moonraker_host"],
                                   self.printers[ind][name]["moonraker_port"],
                                   )

        self.files = KlippyFiles(self)
        self._ws.initial_connect()

    def ws_subscribe(self):
        requested_updates = {
            "objects": {
                "bed_mesh": ["profile_name", "mesh_max", "mesh_min", "probed_matrix", "profiles"],
                "configfile": ["config"],
                "display_status": ["progress", "message"],
                "fan": ["speed"],
                "gcode_move": ["extrude_factor", "gcode_position", "homing_origin", "speed_factor", "speed"],
                "idle_timeout": ["state"],
                "pause_resume": ["is_paused"],
                "print_stats": ["print_duration", "total_duration", "filament_used", "filename", "state", "message",
                                "info"],
                "toolhead": ["homed_axes", "estimated_print_time", "print_time", "position", "extruder",
                             "max_accel", "max_accel_to_decel", "max_velocity", "square_corner_velocity"],
                "virtual_sdcard": ["file_position", "is_active", "progress"],
                "webhooks": ["state", "state_message"],
                "firmware_retraction": ["retract_length", "retract_speed", "unretract_extra_length", "unretract_speed"],
                "motion_report": ["live_position", "live_velocity", "live_extruder_velocity"],
                "exclude_object": ["current_object", "objects", "excluded_objects"],
                "manual_probe": ['is_active'],
            }
        }
        for extruder in self.printer.get_tools():
            requested_updates['objects'][extruder] = [
                "target", "temperature", "pressure_advance", "smooth_time", "power"]
        for h in self.printer.get_heaters():
            requested_updates['objects'][h] = ["target", "temperature", "power"]
        for f in self.printer.get_fans():
            requested_updates['objects'][f] = ["speed"]
        for f in self.printer.get_filament_sensors():
            requested_updates['objects'][f] = ["enabled", "filament_detected"]
        for p in self.printer.get_output_pins():
            requested_updates['objects'][p] = ["value"]
        for led in self.printer.get_leds():
            requested_updates['objects'][led] = ["color_data"]

        self._ws.klippy.object_subscription(requested_updates)

    @staticmethod
    def _load_panel(panel):
        logging.debug(f"Loading panel: {panel}")
        panel_path = os.path.join(os.path.dirname(__file__), 'panels', f"{panel}.py")
        if not os.path.exists(panel_path):
            logging.error(f"Panel {panel} does not exist")
            raise FileNotFoundError(os.strerror(2), "\n" + panel_path)
        return import_module(f"panels.{panel}")

    def show_panel(self, panel, title, remove_all=False, panel_name=None, **kwargs):
        if panel_name is None:
            panel_name = panel
        try:
            if remove_all:
                self._remove_all_panels()
                self.panels_reinit = list(self.panels)
            else:
                self._remove_current_panel()
            if panel_name not in self.panels:
                try:
                    self.panels[panel_name] = self._load_panel(panel).Panel(self, title, **kwargs)
                except Exception as e:
                    self.show_error_modal(f"Unable to load panel {panel}", f"{e}\n\n{traceback.format_exc()}")
                    return
            elif panel_name in self.panels_reinit:
                logging.info("Reinitializing panel")
                self.panels[panel_name].__init__(self, title, **kwargs)
                self.panels_reinit.remove(panel_name)
            self._cur_panels.append(panel_name)
            self.attach_panel(panel_name)
        except Exception as e:
            logging.exception(f"Error attaching panel:\n{e}\n\n{traceback.format_exc()}")

    def attach_panel(self, panel):
        self.base_panel.add_content(self.panels[panel])
        logging.debug(f"Current panel hierarchy: {' > '.join(self._cur_panels)}")
        if hasattr(self.panels[panel], "process_update"):
            self.process_update("notify_status_update", self.printer.data)
            self.process_update("notify_busy", self.printer.busy)
        if hasattr(self.panels[panel], "activate"):
            self.panels[panel].activate()
        self.show_all()

    def log_notification(self, message, level=0):
        time = datetime.now().strftime("%H:%M:%S")
        log_entry = {"message": message, "level": level, "time": time}
        if len(self.notification_log) > 999:
            del self.notification_log[0]
        self.notification_log.append(log_entry)
        self.process_update("notify_log", log_entry)

    def show_popup_message(self, message, level=3):
        self.close_screensaver()
        if self.popup_message is not None:
            self.close_popup_message()

        self.log_notification(message, level)

        msg = Gtk.Button(label=f"{message}")
        msg.set_hexpand(True)
        msg.set_vexpand(True)
        msg.get_child().set_line_wrap(True)
        msg.get_child().set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        msg.get_child().set_max_width_chars(40)
        msg.connect("clicked", self.close_popup_message)
        msg.get_style_context().add_class("message_popup")
        if level == 1:
            msg.get_style_context().add_class("message_popup_echo")
            logging.info(f'echo: {message}')
        elif level == 2:
            msg.get_style_context().add_class("message_popup_warning")
            logging.info(f'warning: {message}')
        else:
            msg.get_style_context().add_class("message_popup_error")
            logging.info(f'error: {message}')

        popup = Gtk.Popover.new(self.base_panel.titlebar)
        popup.get_style_context().add_class("message_popup_popover")
        popup.set_size_request(self.width * .9, -1)
        popup.set_halign(Gtk.Align.CENTER)
        popup.add(msg)
        popup.popup()

        self.popup_message = popup
        self.popup_message.show_all()

        if self._config.get_main_config().getboolean('autoclose_popups', True):
            if self.popup_timeout is not None:
                GLib.source_remove(self.popup_timeout)
                self.popup_timeout = None
            self.popup_timeout = GLib.timeout_add_seconds(10, self.close_popup_message)

        return False

    def close_popup_message(self, widget=None):
        if self.popup_message is None:
            return
        self.popup_message.popdown()
        if self.popup_timeout is not None:
            GLib.source_remove(self.popup_timeout)
        self.popup_message = self.popup_timeout = None
        return False

    def show_error_modal(self, err, e=""):
        logging.error(f"Showing error modal: {err} {e}")

        title = Gtk.Label()
        title.set_markup(f"<b>{err}</b>\n")
        title.set_line_wrap(True)
        title.set_line_wrap_mode(Pango.WrapMode.CHAR)
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        version = Gtk.Label(label=f"{functions.get_software_version()}")
        version.set_halign(Gtk.Align.END)

        help_msg = _("Provide KlipperScreen.log when asking for help.\n")
        message = Gtk.Label(label=f"{help_msg}\n\n{e}")
        message.set_line_wrap(True)
        scroll = self.gtk.ScrolledWindow(steppers=False)
        scroll.set_vexpand(True)
        if self.vertical_mode:
            scroll.set_size_request(self.gtk.width - 30, self.gtk.height * .6)
        else:
            scroll.set_size_request(self.gtk.width - 30, self.gtk.height * .45)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(message)

        grid = Gtk.Grid()
        grid.attach(title, 0, 0, 1, 1)
        grid.attach(version, 1, 0, 1, 1)
        grid.attach(Gtk.Separator(), 0, 1, 2, 1)
        grid.attach(scroll, 0, 2, 2, 1)

        buttons = [
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL}
        ]
        self.gtk.Dialog(_("Error"), buttons, grid, self.error_modal_response)

    def error_modal_response(self, dialog, response_id):
        self.gtk.remove_dialog(dialog)
        self.restart_ks()

    def restart_ks(self, *args):
        logging.debug(f"Restarting {sys.executable} {' '.join(sys.argv)}")
        os.execv(sys.executable, ['python'] + sys.argv)
        self._ws.send_method("machine.services.restart", {"service": "KlipperScreen"})  # Fallback

    def init_style(self):
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-theme-name", "Adwaita")
        settings.set_property("gtk-application-prefer-dark-theme", False)
        css_data = pathlib.Path(os.path.join(klipperscreendir, "styles", "base.css")).read_text()

        with open(os.path.join(klipperscreendir, "styles", "base.conf")) as f:
            style_options = json.load(f)
        # Load custom theme
        theme = os.path.join(klipperscreendir, "styles", self.theme)
        theme_style = os.path.join(theme, "style.css")
        theme_style_conf = os.path.join(theme, "style.conf")

        if os.path.exists(theme_style):
            with open(theme_style) as css:
                css_data += css.read()
        if os.path.exists(theme_style_conf):
            try:
                with open(theme_style_conf) as f:
                    style_options.update(json.load(f))
            except Exception as e:
                logging.error(f"Unable to parse custom template conf file:\n{e}\n\n{traceback.format_exc()}")

        self.gtk.color_list = style_options['graph_colors']

        for i in range(len(style_options['graph_colors']['extruder']['colors'])):
            num = "" if i == 0 else i
            css_data += "\n.graph_label_extruder%s {border-left-color: #%s}" % (
                num,
                style_options['graph_colors']['extruder']['colors'][i]
            )
        for i in range(len(style_options['graph_colors']['bed']['colors'])):
            css_data += "\n.graph_label_heater_bed%s {border-left-color: #%s}" % (
                "" if i == 0 else i + 1,
                style_options['graph_colors']['bed']['colors'][i]
            )
        for i in range(len(style_options['graph_colors']['fan']['colors'])):
            css_data += "\n.graph_label_fan_%s {border-left-color: #%s}" % (
                i + 1,
                style_options['graph_colors']['fan']['colors'][i]
            )
        for i in range(len(style_options['graph_colors']['sensor']['colors'])):
            css_data += "\n.graph_label_sensor_%s {border-left-color: #%s}" % (
                i + 1,
                style_options['graph_colors']['sensor']['colors'][i]
            )

        css_data = css_data.replace("KS_FONT_SIZE", f"{self.gtk.font_size}")

        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css_data.encode())

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _go_to_submenu(self, widget, name):
        logging.info(f"#### Go to submenu {name}")
        # Find current menu item
        if "main_menu" in self._cur_panels:
            menu = "__main"
        elif "splash_screen" in self._cur_panels:
            menu = "__splashscreen"
        else:
            menu = "__print"

        logging.info(f"#### Menu {menu}")
        disname = self._config.get_menu_name(menu, name)
        menuitems = self._config.get_menu_items(menu, name)
        if len(menuitems) != 0:
            self.show_panel("menu", disname, panel_name=name, items=menuitems)
        else:
            logging.info("No items in menu")

    def _remove_all_panels(self):
        for _ in self.base_panel.content.get_children():
            self.base_panel.content.remove(_)
        for dialog in self.dialogs:
            self.gtk.remove_dialog(dialog)
        for panel in list(self.panels):
            if hasattr(self.panels[panel], "deactivate"):
                self.panels[panel].deactivate()
        self._cur_panels.clear()
        self.close_screensaver()

    def _remove_current_panel(self):
        self.base_panel.remove(self.panels[self._cur_panels[-1]].content)
        if hasattr(self.panels[self._cur_panels[-1]], "deactivate"):
            self.panels[self._cur_panels[-1]].deactivate()

    def _menu_go_back(self, widget=None, home=False):
        logging.info(f"#### Menu go {'home' if home else 'back'}")
        self.remove_keyboard()
        while len(self._cur_panels) > 1:
            self._remove_current_panel()
            del self._cur_panels[-1]
            if not home:
                break
        if len(self._cur_panels) < 1:
            self.reload_panels()
            return
        self.attach_panel(self._cur_panels[-1])

    def reset_screensaver_timeout(self, *args):
        if self.screensaver_timeout is not None:
            GLib.source_remove(self.screensaver_timeout)
            self.screensaver_timeout = None
        if not self.use_dpms and self._config.get_main_config().get('screen_blanking') != "off":
            self.screensaver_timeout = GLib.timeout_add_seconds(self.blanking_time, self.show_screensaver)

    def show_screensaver(self):
        logging.debug("Showing Screensaver")
        if self.screensaver is not None:
            self.close_screensaver()
        self.remove_keyboard()
        self.close_popup_message()
        for dialog in self.dialogs:
            logging.debug("Hiding dialog")
            dialog.hide()

        close = Gtk.Button()
        close.connect("clicked", self.close_screensaver)

        box = Gtk.Box()
        box.set_size_request(self.width, self.height)
        box.pack_start(close, True, True, 0)
        box.set_halign(Gtk.Align.CENTER)
        box.get_style_context().add_class("screensaver")
        self.remove(self.base_panel.main_grid)
        self.add(box)

        # Avoid leaving a cursor-handle
        close.grab_focus()
        self.screensaver = box
        self.screensaver.show_all()
        self.power_devices(None, self._config.get_main_config().get("screen_off_devices", ""), on=False)
        if self.screensaver_timeout is not None:
            GLib.source_remove(self.screensaver_timeout)
            self.screensaver_timeout = None
        return False

    def close_screensaver(self, widget=None):
        if self.screensaver is None:
            return False
        logging.debug("Closing Screensaver")
        self.remove(self.screensaver)
        self.screensaver = None
        self.add(self.base_panel.main_grid)
        if self.use_dpms:
            self.wake_screen()
        else:
            self.reset_screensaver_timeout()
        for dialog in self.dialogs:
            logging.info(f"Restoring Dialog {dialog}")
            dialog.show()
        self.show_all()
        self.power_devices(None, self._config.get_main_config().get("screen_on_devices", ""), on=True)

    def check_dpms_state(self):
        if not self.use_dpms:
            return False
        state = functions.get_DPMS_state()
        if state == functions.DPMS_State.Fail:
            logging.info("DPMS State FAIL: Stopping DPMS Check")
            self.set_dpms(False)
            return False
        elif state != functions.DPMS_State.On:
            if self.screensaver is None:
                self.show_screensaver()
        return True

    def wake_screen(self):
        # Wake the screen (it will go to standby as configured)
        if self._config.get_main_config().get('screen_blanking') != "off":
            logging.debug("Screen wake up")
            if not self.wayland:
                os.system("xset -display :0 dpms force on")

    def set_dpms(self, use_dpms):
        self.use_dpms = use_dpms
        logging.info(f"DPMS set to: {self.use_dpms}")
        self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking'))

    def set_screenblanking_timeout(self, time):
        if not self.wayland:
            os.system("xset -display :0 s off")
        self.use_dpms = self._config.get_main_config().getboolean("use_dpms", fallback=True)

        if time == "off":
            logging.debug(f"Screen blanking: {time}")
            if self.screensaver_timeout is not None:
                GLib.source_remove(self.screensaver_timeout)
                self.screensaver_timeout = None
            if not self.wayland:
                os.system("xset -display :0 dpms 0 0 0")
            return

        self.blanking_time = abs(int(time))
        logging.debug(f"Changing screen blanking to: {self.blanking_time}")
        if self.use_dpms and functions.dpms_loaded is True:
            if not self.wayland:
                os.system("xset -display :0 +dpms")
            if functions.get_DPMS_state() == functions.DPMS_State.Fail:
                logging.info("DPMS State FAIL")
                self.show_popup_message(_("DPMS has failed to load and has been disabled"))
                self._config.set("main", "use_dpms", "False")
                self._config.save_user_config_options()
            else:
                logging.debug("Using DPMS")
                if not self.wayland:
                    os.system(f"xset -display :0 dpms 0 {self.blanking_time} 0")
                GLib.timeout_add_seconds(1, self.check_dpms_state)
                return
        # Without dpms just blank the screen
        logging.debug("Not using DPMS")
        if not self.wayland:
            os.system("xset -display :0 dpms 0 0 0")
        self.reset_screensaver_timeout()
        return

    def show_printer_select(self, widget=None):
        self.base_panel.show_heaters(False)
        self.show_panel("printer_select", _("Printer Select"), remove_all=True)

    def process_busy_state(self, busy):
        self.process_update("notify_busy", busy)
        return False

    def websocket_disconnected(self, msg):
        self.printer_initializing(msg, remove=True)
        self.printer.state = "disconnected"
        self.connecting = True
        self.connected_printer = None
        self.files.reset()
        self.files = None
        self.initialized = False
        self.connect_printer(self.connecting_to_printer)

    def state_disconnected(self):
        logging.debug("### Going to disconnected")
        self.close_screensaver()
        self.initialized = False
        self.reinit_count = 0
        self._init_printer(_("Firmware has disconnected"), remove=True)

    def state_error(self):
        self.close_screensaver()
        msg = _("Firmware has encountered an error.") + "\n"
        state = self.printer.get_stat("webhooks", "state_message")
        if "FIRMWARE_RESTART" in state:
            msg += _("A FIRMWARE_RESTART may fix the issue.") + "\n"
        elif "micro-controller" in state:
            msg += _("Please recompile and flash the micro-controller.") + "\n"
        self.printer_initializing(msg + "\n" + state, remove=True)

    def state_paused(self):
        self.state_printing()
        if self._config.get_main_config().getboolean("auto_open_extrude", fallback=True):
            self.show_panel("extrude", _("Extrude"))

    def state_printing(self):            
        self.close_screensaver()
        for dialog in self.dialogs:
            self.gtk.remove_dialog(dialog)
        self.show_panel("job_status", _("Printing"), remove_all=True)

    def state_ready(self, wait=True):
        # Do not return to main menu if completing a job, timeouts/user input will return
        if "job_status" in self._cur_panels and wait:
            return
        if not self.initialized:
            logging.debug("Printer not initialized yet")
            self.printer.state = "not ready"
            return
        self.show_panel("main_menu", None, remove_all=True, items=self._config.get_menu_items("__main"))

        #bed mesh
        bm = self.printer.get_stat("bed_mesh")
        if bm is not None: 
            pn = self.printer.get_stat("bed_mesh", "profile_name")
            ps = self.printer.get_stat("bed_mesh", "profiles")
            if pn == "" and 'default' in ps:
                script = 'BED_MESH_PROFILE LOAD="default"'
                self._ws.klippy.gcode_script(script)

        self.load_klipper_config()
        if self.klippy_config is not None and self.setup_init == 0:
            self.setup_init = self.klippy_config.getint("Variables", "setup_step", fallback=0)

        if self.setup_init == 1:
            if self.check_image_files():
                self.is_show_manual = True
                self.show_panel("manual", _("Manual"), remove_all=True)
            else :
                self.show_panel("setup_wizard", _("Choose Language"), remove_all=True)
        elif self.auto_check:
            self.show_panel("self_check", _("Self-check"), remove_all=True)
        self.auto_check = False

        self.on_filament_box_power = self._config.get_main_config().getboolean("filament_box_power", fallback=False)
        if self.on_filament_box_power and (self.printer is not None) and ('SET_FILAMENT_BOX_POWER' in self.printer.get_gcode_macros()):
            script  = 'SET_FILAMENT_BOX_POWER S=1'
            self._ws.klippy.gcode_script(script)        

        self.on_auto_extruder_switch = self._config.get_main_config().getboolean("auto_extruder_switch", fallback=False)
        if self.on_auto_extruder_switch:
            script = 'ENABLE_AUTO_EXTRUDER_SWITCH'
            self._ws.klippy.gcode_script(script)

    def state_startup(self):
        self.printer_initializing(_("Firmware is attempting to start"))

    def state_shutdown(self):
        self.close_screensaver()
        msg = self.printer.get_stat("webhooks", "state_message")
        msg = msg if "ready" not in msg else ""
        self.printer_initializing(_("Firmware has shutdown") + "\n\n" + msg, remove=True)

    def toggle_shortcut(self, show):
        if show and not self.printer.get_printer_status_data()["printer"]["gcode_macros"]["count"] > 0:
            self.show_popup_message(
                _("No elegible macros:") + "\n"
                + _("macros with a name starting with '_' are hidden") + "\n"
                + _("macros that use 'rename_existing' are hidden") + "\n"
                + _("LOAD_FILAMENT/UNLOAD_FILAMENT are hidden and should be used from extrude") + "\n"
            )
        self.base_panel.show_shortcut(show)

    def change_language(self, widget, lang, force_reload=True):
        self._config.install_language(lang)
        self.lang_ltr = set_text_direction(lang)
        self.env.install_gettext_translations(self._config.get_lang())
        self._config._create_configurable_options(self)
        self._config.set('main', 'language', lang)
        
        # 根据语言设置对应的时区
        timezone_map = {
            'ar': 'Asia/Riyadh',      # 阿拉伯语
            'bg': 'Europe/Sofia',      # 保加利亚语
            'cs': 'Europe/Prague',     # 捷克语
            'da': 'Europe/Copenhagen', # 丹麦语
            'de': 'Europe/Berlin',     # 德语
            'de_formal': 'Europe/Berlin', # 德语(正式)
            'en': 'America/New_York',  # 英语
            'es': 'Europe/Madrid',     # 西班牙语
            'et': 'Europe/Tallinn',    # 爱沙尼亚语
            'fr': 'Europe/Paris',      # 法语
            'he': 'Asia/Jerusalem',    # 希伯来语
            'hu': 'Europe/Budapest',   # 匈牙利语
            'it': 'Europe/Rome',       # 意大利语
            'jp': 'Asia/Tokyo',        # 日语
            'ko': 'Asia/Seoul',        # 韩语
            'lt': 'Europe/Vilnius',    # 立陶宛语
            'nl': 'Europe/Amsterdam',  # 荷兰语
            'pl': 'Europe/Warsaw',     # 波兰语
            'pt': 'Europe/Lisbon',     # 葡萄牙语
            'pt_BR': 'America/Sao_Paulo', # 巴西葡萄牙语
            'ru': 'Europe/Moscow',     # 俄语
            'sl': 'Europe/Ljubljana',  # 斯洛文尼亚语
            'sv': 'Europe/Stockholm',  # 瑞典语
            'tr': 'Europe/Istanbul',   # 土耳其语
            'uk': 'Europe/Kiev',       # 乌克兰语
            'vi': 'Asia/Ho_Chi_Minh',  # 越南语
            'zh_CN': 'Asia/Shanghai',  # 简体中文
            'zh_TW': 'Asia/Taipei'     # 繁体中文
        }
        
        # 如果存在对应的时区映射则设置
        if lang in timezone_map:
            try:
                logging.info(f"Setting timezone to {timezone_map[lang]} for language {lang}")
                set_timezone_async(timezone_map[lang])
            except Exception as e:
                logging.error(f"Error setting timezone: {e}")
        
        self._config.save_user_config_options()
        
        # 调用 set_language 更新手册语言
        self.set_language(lang)
        
        if force_reload:
            self.reload_panels()
    def reload_panels(self, *args):
        if "printer_select" in self._cur_panels:
            self.show_printer_select()
            return
        self._remove_all_panels()
        if self.printer is not None:
            self.printer.change_state(self.printer.state)

    def set_filament_box_power(self, is_on):
        if 'SET_FILAMENT_BOX_POWER' in self.printer.get_gcode_macros():
            script  = 'SET_FILAMENT_BOX_POWER S=0'
            if is_on:
                script  = 'SET_FILAMENT_BOX_POWER S=1'
            self._ws.klippy.gcode_script(script)

    def _websocket_callback(self, action, data):
        if self.connecting:
            return
        if action == "notify_klippy_disconnected":
            self.printer.process_update({'webhooks': {'state': "disconnected"}})
            return
        elif action == "notify_klippy_shutdown":
            self.printer.process_update({'webhooks': {'state': "shutdown"}})
        elif action == "notify_klippy_ready":
            if not self.initialized:
                logging.debug("Still not initialized")
                return
            self.printer.process_update({'webhooks': {'state': "ready"}})
        elif action == "notify_status_update" and self.printer.state != "shutdown":
            self.printer.process_update(data)
            if 'manual_probe' in data and data['manual_probe']['is_active'] and 'zcalibrate' not in self._cur_panels:
                if self.setup_init == 0:
                    self.show_panel("zcalibrate", _('Z Calibrate'))
        elif action == "notify_filelist_changed":
            if self.files is not None:
                self.files.process_update(data)
        elif action == "notify_metadata_update":
            self.files.request_metadata(data['filename'])
        elif action == "notify_update_response":
            if 'message' in data and 'Error' in data['message']:
                logging.error(f"{action}:{data['message']}")
                self.show_popup_message(data['message'], 3)
                if "KlipperScreen" in data['message']:
                    self.restart_ks()
        elif action == "notify_power_changed":
            logging.debug("Power status changed: %s", data)
            self.printer.process_power_update(data)
            self.panels['splash_screen'].check_power_status()
        elif action == "notify_gcode_response" and self.printer.state not in ["error", "shutdown"]:
            if not (data.startswith("B:") or data.startswith("T:")):
                if "RESPOND TYPE=" in data:
                    msg_start = data.find("MSG=")
                    if msg_start != -1:
                        msg = data[msg_start+5:-1] if data.endswith('"') else data[msg_start+5:]
                        translated_msg = _(msg)
                        level = 3 if "TYPE=error" in data else 2 if "TYPE=warning" in data else 1
                        self.show_popup_message(translated_msg, level)
                elif data.startswith("echo: "):
                    self.show_popup_message(_(data[6:]), 1)
                elif data.startswith("!! "):
                    self.show_popup_message(_(data[3:]), 3)
                elif "unknown" in data.lower() and \
                        not ("TESTZ" in data or "MEASURE_AXES_NOISE" in data or "ACCELEROMETER_QUERY" in data):
                    self.show_popup_message(_(data))
                elif "SAVE_CONFIG" in data and self.printer.state == "ready":
                    script = {"script": "SAVE_CONFIG"}
                    self._confirm_send_action(
                        None,
                        _("Save configuration?") + "\n\n" + _("Firmware will reboot"),
                        "printer.gcode.script",
                        script
                    )
        self.process_update(action, data)

    def process_update(self, *args):
        self.base_panel.process_update(*args)
        if self._cur_panels and hasattr(self.panels[self._cur_panels[-1]], "process_update"):
            self.panels[self._cur_panels[-1]].process_update(*args)

    def _confirm_send_action(self, widget, text, method, params=None, save_button=True):
        buttons = [
            {"name": _("Accept"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        if save_button and params is not None and 'script' in params and params['script'].strip():
                    buttons = [
            {"name": _("Save"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
                    
        try:
            j2_temp = self.env.from_string(text)
            text = j2_temp.render()
        except Exception as e:
            logging.debug(f"Error parsing jinja for confirm_send_action\n{e}\n\n{traceback.format_exc()}")

        label = Gtk.Label()
        label.set_markup(text)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        if self.confirm is not None:
            self.gtk.remove_dialog(self.confirm)
        self.confirm = self.gtk.Dialog(
            "KlipperScreen", buttons, label, self._confirm_send_action_response, method, params
        )

    def _confirm_send_action_response(self, dialog, response_id, method, params):
        self.gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            self._send_action(None, method, params)
        if method == "server.files.delete_directory":
            GLib.timeout_add_seconds(2, self.files.refresh_files)
            
        if params == {"script": "POWEROFF_RESUME"} and response_id == Gtk.ResponseType.CANCEL:
            self._send_action(None, method, {"script": "REMOVE_POWEROFF_RESUME"})

    def _send_action(self, widget, method, params):
        logging.info(f"{method}: {params}")
        if isinstance(widget, Gtk.Button):
            self.gtk.Button_busy(widget, True)
            self._ws.send_method(method, params, self.enable_widget, widget)
        else:
            self._ws.send_method(method, params)

    def enable_widget(self, *args):
        for x in args:
            if isinstance(x, Gtk.Button):
                GLib.timeout_add(150, self.gtk.Button_busy, x, False)

    def printer_initializing(self, msg, remove=False):
        if 'splash_screen' not in self.panels or remove:
            self.show_panel("splash_screen", None, remove_all=True)
        self.panels['splash_screen'].update_text(msg)
        self.log_notification(msg, 0)

    def search_power_devices(self, devices):
        found_devices = []
        if self.connected_printer is None or not devices:
            return found_devices
        devices = [str(i.strip()) for i in devices.split(',')]
        power_devices = self.printer.get_power_devices()
        if power_devices:
            found_devices = [dev for dev in devices if dev in power_devices]
            logging.info(f"Found {found_devices}", )
        return found_devices

    def power_devices(self, widget=None, devices=None, on=False):
        devs = self.search_power_devices(devices)
        for dev in devs:
            if on:
                self._ws.klippy.power_device_on(dev)
            else:
                self._ws.klippy.power_device_off(dev)

    def _init_printer(self, msg, remove=False):
        self.printer_initializing(msg, remove)
        self.initializing = False
        GLib.timeout_add_seconds(3, self.init_printer)
        return False

    def init_printer(self):
        if self.initializing:
            return False
        self.initializing = True
        if self.reinit_count > self.max_retries or 'printer_select' in self._cur_panels:
            self.initializing = False
            return False
        state = self.apiclient.get_server_info()
        if state is False:
            logging.info("Moonraker not connected")
            self.initializing = False
            return False
        self.connecting = not self._ws.connected
        self.connected_printer = self.connecting_to_printer
        self.base_panel.set_ks_printer_cfg(self.connected_printer)

        # Moonraker is ready, set a loop to init the printer
        self.reinit_count += 1

        server_info = self.apiclient.get_server_info()["result"]
        logging.info(f"Moonraker info {server_info}")
        popup = ''
        level = 2
        if server_info["warnings"]:
            popup += '\nMoonraker warnings:\n'
            for warning in server_info["warnings"]:
                warning = warning.replace('<br>', '').replace('<br/>', '\n').replace('</br>', '\n').replace(':', ':\n')
                popup += f"{warning}\n"
        if server_info["failed_components"]:
            popup += '\nMoonraker failed components:\n'
            for failed in server_info["failed_components"]:
                popup += f'[{failed}]\n'
        if server_info["missing_klippy_requirements"]:
            popup += '\nMissing Klipper configuration:\n'
            for missing in server_info["missing_klippy_requirements"]:
                popup += f'[{missing}]\n'
                level = 3
        if popup:
            self.show_popup_message(popup, level)
        if "power" in server_info["components"]:
            powerdevs = self.apiclient.send_request("machine/device_power/devices")
            if powerdevs is not False:
                self.printer.configure_power_devices(powerdevs['result'])
        if "webcam" in server_info["components"]:
            cameras = self.apiclient.send_request("server/webcams/list")
            if cameras is not False:
                self.printer.configure_cameras(cameras['result']['webcams'])
        if "spoolman" in server_info["components"]:
            self.printer.enable_spoolman()

        if state['result']['klippy_connected'] is False:
            logging.info("Klipper not connected")
            msg = _("Moonraker: connected") + "\n\n"
            msg += f"Klipper: {state['result']['klippy_state']}" + "\n\n"
            if self.reinit_count <= self.max_retries:
                msg += _("Retrying") + f' #{self.reinit_count}'
            return self._init_printer(msg)
        printer_info = self.apiclient.get_printer_info()
        if printer_info is False:
            return self._init_printer("Unable to get printer info from moonraker")
        config = self.apiclient.send_request("printer/objects/query?configfile")
        if config is False:
            return self._init_printer("Error getting printer configuration")
        logging.debug(config['result']['status'])
        # Reinitialize printer, in case the printer was shut down and anything has changed.
        self.printer.reinit(printer_info['result'], config['result']['status'])
        self.printer.available_commands = self.apiclient.get_gcode_help()['result']
        info = self.apiclient.send_request("machine/system_info")
        if info and 'system_info' in info:
            self.printer.system_info = info['system_info']

        self.ws_subscribe()
        extra_items = (self.printer.get_tools()
                       + self.printer.get_heaters()
                       + self.printer.get_fans()
                       + self.printer.get_filament_sensors()
                       + self.printer.get_output_pins()
                       + self.printer.get_leds()
                       )

        data = self.apiclient.send_request("printer/objects/query?" + "&".join(PRINTER_BASE_STATUS_OBJECTS +
                                                                               extra_items))
        if data is False:
            return self._init_printer("Error getting printer object data with extra items")
        if len(self.printer.get_temp_devices()) > 0:
            self.init_tempstore()

        self.files.initialize()
        self.files.refresh_files()

        logging.info("Printer initialized")
        self.initialized = True
        self.reinit_count = 0
        self.initializing = False
        self.printer.process_update(data['result']['status'])
        self.log_notification("Printer Initialized", 1)
        return False

    def init_tempstore(self):
        tempstore = self.apiclient.send_request("server/temperature_store")
        if tempstore and 'result' in tempstore and tempstore['result']:
            self.printer.init_temp_store(tempstore['result'])
            if hasattr(self.panels[self._cur_panels[-1]], "update_graph_visibility"):
                self.panels[self._cur_panels[-1]].update_graph_visibility()
        else:
            logging.error(f'Tempstore not ready: {tempstore} Retrying in 5 seconds')
            GLib.timeout_add_seconds(5, self.init_tempstore)
            return
        server_config = self.apiclient.send_request("server/config")
        if server_config:
            try:
                self.printer.tempstore_size = server_config["result"]["config"]["data_store"]["temperature_store_size"]
                logging.info(f"Temperature store size: {self.printer.tempstore_size}")
            except KeyError:
                logging.error("Couldn't get the temperature store size")
        return False

    def show_keyboard(self, entry=None, event=None):
        if self.keyboard is not None:
            return

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_size_request(self.gtk.content_width, self.gtk.keyboard_height)
        box.set_vexpand(False)

        if self._config.get_main_config().getboolean("use-matchbox-keyboard", False):
            return self._show_matchbox_keyboard(box)
        if entry is None:
            logging.debug("Error: no entry provided for keyboard")
            return
        box.get_style_context().add_class("keyboard_box")
        box.add(Keyboard(self, self.remove_keyboard, entry=entry))
        self.keyboard = {"box": box}
        self.base_panel.content.pack_end(box, False, False, 0)
        self.base_panel.content.show_all()

    def _show_matchbox_keyboard(self, box):
        env = os.environ.copy()
        usrkbd = os.path.expanduser("~/.matchbox/keyboard.xml")
        if os.path.isfile(usrkbd):
            env["MB_KBD_CONFIG"] = usrkbd
        else:
            env["MB_KBD_CONFIG"] = "ks_includes/locales/keyboard.xml"
        p = subprocess.Popen(["matchbox-keyboard", "--xid"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env)
        xid = int(p.stdout.readline())
        logging.debug(f"XID {xid}")
        logging.debug(f"PID {p.pid}")

        keyboard = Gtk.Socket()
        box.get_style_context().add_class("keyboard_matchbox")
        box.pack_start(keyboard, True, True, 0)
        self.base_panel.content.pack_end(box, False, False, 0)

        self.show_all()
        keyboard.add_id(xid)

        self.keyboard = {
            "box": box,
            "process": p,
            "socket": keyboard
        }
        return

    def remove_keyboard(self, widget=None, event=None):
        if self.keyboard is None:
            return
        if 'process' in self.keyboard:
            os.kill(self.keyboard['process'].pid, SIGTERM)
        self.base_panel.content.remove(self.keyboard['box'])
        self.keyboard = None

    def _key_press_event(self, widget, event):
        keyval_name = Gdk.keyval_name(event.keyval)
        if keyval_name == "Escape":
            self._menu_go_back(home=True)
        elif keyval_name == "BackSpace" and len(self._cur_panels) > 1 and self.keyboard is None:
            self.base_panel.back()

    def update_size(self, *args):
        width, height = self.get_size()
        if width != self.width or height != self.height:
            logging.info(f"Size changed: {self.width}x{self.height}")
        #self.width, self.height = width, height
        new_ratio = self.width / self.height
        new_mode = new_ratio < 1.0
        ratio_delta = abs(self.aspect_ratio - new_ratio)
        if ratio_delta > 0.1 and self.vertical_mode != new_mode:
            self.reload_panels()
            self.vertical_mode = new_mode
            self.aspect_ratio = new_ratio
            logging.info(f"Vertical mode: {self.vertical_mode}")

    def save_init_step(self):
        try:
            self.klippy_config["Variables"]["setup_step"] = str(self.setup_init)
            with open(self.klippy_config_path, 'w') as file:
                self.klippy_config.write(file)
        except Exception as e:
            logging.error(f"Error writing configuration file in {self.klippy_config_path}:\n{e}")        

    def check_image_files(self, directory="/home/mingda/printer_data/resources/manual"):
        if not os.path.exists(directory):
            return False
    
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".jpg") or file.endswith(".png") or file.endswith(".gif"):
                    print(f"Found image file: {os.path.join(root, file)}")
                    return True
    
        return False
    
    def set_language(self, lang):
        # 已有的语言设置代码...
        
        # 更新手册语言
        if hasattr(self, "panels") and "manual" in self.panels:
            self.panels["manual"].update_language(lang)

    def check_auto_extruder_switch(self):
        # 检查配置文件中是否存在 auto_extruder_switch 段
        if self.printer is None:
            return False
            
        return self.printer.config_section_exists("auto_extruder_switch")

    def set_auto_extruder_switch(self, is_on):
        script = 'DISABLE_AUTO_EXTRUDER_SWITCH'
        if is_on:
            script = 'ENABLE_AUTO_EXTRUDER_SWITCH'
        self._ws.klippy.gcode_script(script)

def set_timezone_async(timezone):
    """异步设置时区的函数"""
    def _set_timezone():
        try:
            # 添加超时控制，5秒后如果还没完成就终止
            process = subprocess.Popen(
                ['sudo', 'timedatectl', 'set-timezone', timezone],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            try:
                process.wait(timeout=5)
                if process.returncode == 0:
                    logging.info(f"Successfully set timezone to {timezone}")
                else:
                    logging.error(f"Failed to set timezone: {process.stderr.read().decode()}")
            except subprocess.TimeoutExpired:
                process.kill()
                logging.error(f"Timeout while setting timezone to {timezone}")
        except Exception as e:
            logging.error(f"Error setting timezone: {e}")

    # 在新线程中执行时区设置
    thread = threading.Thread(target=_set_timezone)
    thread.daemon = True
    thread.start()

def main():
    minimum = (3, 7)
    if not sys.version_info >= minimum:
        logging.error(f"python {sys.version_info.major}.{sys.version_info.minor} "
                      f"does not meet the minimum requirement {minimum[0]}.{minimum[1]}")
        sys.exit(1)
    parser = argparse.ArgumentParser(description="KlipperScreen - A GUI for Klipper")
    homedir = os.path.expanduser("~")

    parser.add_argument(
        "-c", "--configfile", default=os.path.join(homedir, "KlipperScreen.conf"), metavar='<configfile>',
        help="Location of KlipperScreen configuration file"
    )
    logdir = os.path.join(homedir, "printer_data", "logs")
    if not os.path.exists(logdir):
        logdir = "/tmp"
    parser.add_argument(
        "-l", "--logfile", default=os.path.join(logdir, "KlipperScreen.log"), metavar='<logfile>',
        help="Location of KlipperScreen logfile output"
    )
    args = parser.parse_args()

    functions.setup_logging(os.path.normpath(os.path.expanduser(args.logfile)))
    functions.patch_threading_excepthook()
    if not Gtk.init_check():
        logging.critical("Failed to initialize Gtk")
        raise RuntimeError
    try:
        win = KlipperScreen(args)
    except Exception as e:
        logging.exception(f"Failed to initialize window\n{e}\n\n{traceback.format_exc()}")
        raise RuntimeError from e
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        logging.exception(f"Fatal error in main loop:\n{ex}\n\n{traceback.format_exc()}")
        sys.exit(1)

