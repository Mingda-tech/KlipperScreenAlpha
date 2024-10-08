import mpv
import logging
import gi
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from contextlib import suppress
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.mpv = None
        self.play_timer = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for i, cam in enumerate(self._printer.cameras):
            if not cam["enabled"] or cam["name"] == "calicam":
                continue
            logging.info(cam)
            cam[cam["name"]] = self._gtk.Button(
                image_name="camera", label=cam["name"], style=f"color{i % 4 + 1}",
                scale=self.bts, position=Gtk.PositionType.LEFT, lines=1
            )
            cam[cam["name"]].set_hexpand(True)
            cam[cam["name"]].set_vexpand(True)
            cam[cam["name"]].connect("clicked", self.play, cam)
            box.add(cam[cam["name"]])

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(box)
        self.content.add(self.scroll)
        self.content.show_all()

    def activate(self):
        # if only 1 cam start playing fullscreen
        if len(self._printer.cameras) == 1:
            cam = next(iter(self._printer.cameras))
            if cam['enabled']:
                self.play(None, cam)
        if self.play_timer:
            self.play_timer.cancel()
            self.play_timer = None                

    def deactivate(self):
        if self.play_timer:
            self.play_timer.cancel()
            self.play_timer = None
        if self.mpv:
            self.mpv.terminate()
            self.mpv = None

    def play(self, widget, cam):
        url = cam['stream_url']
        if url.startswith('/'):
            logging.info("camera URL is relative")
            endpoint = self._screen.apiclient.endpoint.split(':')
            url = f"{endpoint[0]}:{endpoint[1]}{url}"
        if '/webrtc' in url:
            self._screen.show_popup_message(_('WebRTC is not supported by the backend trying Stream'))
            url = url.replace('/webrtc', '/stream')
        vf = ""
        if cam["flip_horizontal"]:
            vf += "hflip,"
        if cam["flip_vertical"]:
            vf += "vflip,"
        vf += f"rotate:{cam['rotation'] * 3.14159 / 180}"
        logging.info(f"video filters: {vf}")

        if self.mpv:
            self.mpv.terminate()
        self.mpv = mpv.MPV(fullscreen=True, log_handler=self.log, vo='gpu,wlshm,xv,x11')

        self.mpv.vf = vf

        with suppress(Exception):
            self.mpv.profile = 'sw-fast'

        # LOW LATENCY PLAYBACK
        with suppress(Exception):
            self.mpv.profile = 'low-latency'
        self.mpv.untimed = True
        self.mpv.audio = 'no'

        @self.mpv.on_key_press('MBTN_LEFT' or 'MBTN_LEFT_DBL')
        def clicked():
            self.mpv.quit(0)

        logging.debug(f"Camera URL: {url}")
        self.mpv.play(url)
  
        # Start the timer
        self.play_timer = threading.Timer(3600, self.stop_playback)
        self.play_timer.start()
        
        try:
            self.mpv.wait_for_playback()
        except mpv.ShutdownError:
            logging.info('Exiting Fullscreen due to ShutdownError')
        except Exception as e:
            logging.exception(f"Unexpected error during playback: {e}")
        finally:
            self.stop_playback()        

    def stop_playback(self):
        logging.info("Stopping video playback")
        
        if self.play_timer:
            self.play_timer.cancel()
            self.play_timer = None
            logging.info("Playback timer cancelled")
        
        if self.mpv:
            def safe_terminate():
                try:
                    if self.mpv:
                        self.mpv.terminate()
                        logging.info("MPV player terminated")
                except Exception as e:
                    logging.exception(f"Error during MPV termination: {e}")
                finally:
                    self.mpv = None
                    if len(self._printer.cameras) == 1:
                        GLib.idle_add(self._screen._menu_go_back)
                        logging.info("Returning to previous menu")

            terminate_thread = threading.Thread(target=safe_terminate)
            terminate_thread.start()

            # Wait for the termination thread to complete, but set a timeout to avoid infinite waiting
            terminate_thread.join(timeout=5)  # 5 seconds timeout
            logging.info("Terminate thread completed or timed out")

        logging.info("Video playback stop procedure completed")
    def log(self, loglevel, component, message):
        logging.debug(f'[{loglevel}] {component}: {message}')
        if loglevel == 'error' and 'No Xvideo support found' not in message and 'youtube-dl' not in message:
            self._screen.show_popup_message(f'{message}')
