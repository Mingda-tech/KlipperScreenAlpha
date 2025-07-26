import logging
import os
import gi
import netifaces

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    initialized = False

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.show_add = False
        self.networks = {}
        self.interface = None
        self.prev_network = None
        self.connecting_dialog = None
        self.update_timeout = None
        self.network_interfaces = netifaces.interfaces()
        self.wireless_interfaces = [iface for iface in self.network_interfaces if iface.startswith('wl')]
        self.wifi = None
        self.use_network_manager = os.system('systemctl is-active --quiet NetworkManager.service') == 0
        if self.wireless_interfaces:
            logging.info(f"Found wireless interfaces: {self.wireless_interfaces}")
            if self.use_network_manager:
                logging.info("Network Manager is active, using ks_includes/wifi_nm.py")
                from ks_includes.wifi_nm import WifiManager
            else:
                logging.info("Network Manager is not active, using ks_includes/wifi.py (wpa_cli)")
                from ks_includes.wifi import WifiManager
            self.wifi = WifiManager(self.wireless_interfaces[0])
        else:
            logging.info(_("No wireless interface has been found"))

        # Get IP Address
        gws = netifaces.gateways()
        if "default" in gws and netifaces.AF_INET in gws["default"]:
            self.interface = gws["default"][netifaces.AF_INET][1]
        else:
            ints = netifaces.interfaces()
            if 'lo' in ints:
                ints.pop(ints.index('lo'))
            self.interface = ints[0] if len(ints) > 0 else 'lo'

        self.labels['networks'] = {}

        self.labels['interface'] = Gtk.Label(hexpand=True)
        self.labels['interface'].set_text(_("Interface") + f': {self.interface}  ')

        self.labels['ip'] = Gtk.Label(hexpand=True)
        ifadd = netifaces.ifaddresses(self.interface)
        if ifadd.get(netifaces.AF_INET):
            self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")

        reload_networks = self._gtk.Button("refresh", None, "color1", self.bts)
        reload_networks.connect("clicked", self.reload_networks)
        # reload_networks.set_hexpand(False)

        self.labels['back'] = self._gtk.Button("arrow-left", None, "color1", .66)
        self.labels['back'].connect("clicked", self.on_back_click)
        # self.labels['back'].set_hexpand(False)

        self.labels['next'] = self._gtk.Button("complete", None, "color1", .66)
        self.labels['next'].connect("clicked", self.on_next_click)
        # self.labels['next'].set_hexpand(False)

        sbox = Gtk.Box(hexpand=True, vexpand=False)
        sbox.add(self.labels['back'])
        sbox.add(reload_networks)
        sbox.add(self.labels['next'])

        scroll = self._gtk.ScrolledWindow()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)

        self.labels['networklist'] = Gtk.Grid()

        if self.wifi is not None:
            box.pack_start(sbox, False, False, 5)
            box.pack_start(scroll, True, True, 0)

            scroll.add(self.labels['networklist'])

            self.wifi.add_callback("connected", self.connected_callback)
            self.wifi.add_callback("scan_results", self.scan_callback)
            self.wifi.add_callback("popup", self.popup_callback)
            
            # Delay network loading to wait for WiFi Manager initialization
            GLib.timeout_add_seconds(1, self.delayed_network_loading)
            
            if self.update_timeout is None:
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks_async)
        else:
            self.labels['networkinfo'] = Gtk.Label()
            self.labels['networkinfo'].get_style_context().add_class('temperature_entry')
            box.pack_start(self.labels['networkinfo'], False, False, 0)
            self.update_single_network_info()
            if self.update_timeout is None:
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

        self.content.add(box)
        self.labels['main_box'] = box
        self.initialized = True

    def load_networks_async(self, widget=None):
        """Load network list asynchronously"""
        
        def on_networks_loaded(networks, error):
            if error:
                logging.error(f"Failed to load network list: {error}")
                if widget:
                    GLib.timeout_add_seconds(10, self._gtk.Button_busy, widget, False)
                return
                
            if not networks:
                if widget:
                    GLib.timeout_add_seconds(10, self._gtk.Button_busy, widget, False)
                return
                
            for net in networks:
                self.add_network(net, False)
            self.update_all_networks_async()
            if widget:
                GLib.timeout_add_seconds(10, self._gtk.Button_busy, widget, False)
            self.content.show_all()
            
        self.wifi.get_networks(on_networks_loaded)

    def add_network(self, ssid, show=True):
        if ssid is None:
            return
        ssid = ssid.strip()
        if ssid in list(self.networks):
            return

        # Get supplicant network information asynchronously
        def on_supplicant_networks(configured_networks, error):
            if error:
                logging.error(f"Failed to get supplicant networks: {error}")
                configured_networks = {}
                
            network_id = -1
            for net in list(configured_networks):
                if configured_networks[net]['ssid'] == ssid:
                    network_id = net

            display_name = _("Hidden") if ssid.startswith("\x00") else f"{ssid}"
            
            # Get network information asynchronously
            def on_network_info(netinfo, error):
                if error or netinfo is None:
                    netinfo = {'connected': False}

                # Get currently connected SSID asynchronously
                def on_connected_ssid(connected_ssid, error):
                    if error:
                        connected_ssid = None
                    
                    # Check if network already exists (avoid race condition)
                    if ssid in list(self.networks):
                        return
                        
                    name = Gtk.Label(hexpand=True, halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
                    if connected_ssid == ssid:
                        display_name_final = display_name + " (" + _("Connected") + ")"
                        name.set_markup(f"<big><b>{display_name_final}</b></big>")
                    else:
                        name.set_label(display_name)

                    info = Gtk.Label(halign=Gtk.Align.START)
                    labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True,
                                     halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
                    labels.add(name)
                    labels.add(info)

                    connect = self._gtk.Button("load", None, "color3", self.bts)
                    connect.connect("clicked", self.connect_network, ssid)
                    connect.set_hexpand(False)
                    connect.set_halign(Gtk.Align.END)

                    delete = self._gtk.Button("delete", None, "color3", self.bts)
                    delete.connect("clicked", self.remove_wifi_network, ssid)
                    delete.set_hexpand(False)
                    delete.set_halign(Gtk.Align.END)

                    network = Gtk.Box(spacing=5, hexpand=True, vexpand=False)
                    network.get_style_context().add_class("frame-item")
                    network.add(labels)

                    buttons = Gtk.Box(spacing=5)
                    if network_id != -1 or netinfo.get('connected', False):
                        buttons.pack_end(connect, False, False, 0)
                        buttons.pack_end(delete, False, False, 0)
                    else:
                        buttons.pack_end(connect, False, False, 0)
                    network.add(buttons)
                    self.networks[ssid] = network

                    nets = sorted(list(self.networks), reverse=False)
                    if connected_ssid in nets:
                        nets.remove(connected_ssid)
                        nets.insert(0, connected_ssid)
                    
                    try:
                        pos = nets.index(ssid)
                    except ValueError:
                        logging.error(f"Error: SSID {ssid} not in nets")
                        return

                    self.labels['networks'][ssid] = {
                        "connect": connect,
                        "delete": delete,
                        "info": info,
                        "name": name,
                        "row": network
                    }

                    self.labels['networklist'].insert_row(pos)
                    self.labels['networklist'].attach(self.networks[ssid], 0, pos, 1, 1)
                    if show:
                        self.labels['networklist'].show()
                        
                self.wifi.get_connected_ssid(on_connected_ssid)
                
            self.wifi.get_network_info(ssid, on_network_info)
            
        self.wifi.get_supplicant_networks(on_supplicant_networks)

    def add_new_network(self, widget, ssid):
        self._screen.remove_keyboard()
        
        def on_network_added(result, error):
            self.close_add_network()
            if error:
                self._screen.show_popup_message(f"Error adding network {ssid}: {error}")
            elif result:
                self.connect_network(widget, ssid, False)
            else:
                self._screen.show_popup_message(f"Error adding network {ssid}")
                
        self.wifi.add_network(ssid, self.labels['network_psk'].get_text(), on_network_added)

    def back(self):
        if self.show_add:
            self.close_add_network()
            return True
        return False

    def check_missing_networks(self):
        """Check and add missing networks"""
        def on_networks_loaded(networks, error):
            if error or not networks:
                return
                
            # Find missing networks
            missing_networks = []
            for net in networks:
                if net not in list(self.networks):
                    missing_networks.append(net)

            # Add missing networks
            for net in missing_networks:
                self.add_network(net, False)
                
            if missing_networks:
                self.labels['networklist'].show_all()
            
        self.wifi.get_networks(on_networks_loaded)

    def close_add_network(self):
        if not self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels['main_box'])
        self.content.show()
        for i in ['add_network', 'network_psk']:
            if i in self.labels:
                del self.labels[i]
        self.show_add = False

    def popup_callback(self, msg):
        self._screen.show_popup_message(msg)

    def connected_callback(self, ssid, prev_ssid):
        logging.info(f"Now connected to a new network: {ssid}")
        # Refresh all network status without deleting/recreating UI components
        self.update_all_networks_async()

    def connect_network(self, widget, ssid, showadd=True):
        def on_supplicant_networks(configured_networks, error):
            if error:
                logging.error(f"Failed to get supplicant networks: {error}")
                return
                
            isdef = any(net['ssid'] == ssid for netid, net in configured_networks.items())
            if not isdef:
                if showadd:
                    self.show_add_network(widget, ssid)
                return
                
            def on_connected_ssid(prev_network, error):
                if error:
                    prev_network = None
                self.prev_network = prev_network

                buttons = [
                    {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
                ]

                scroll = self._gtk.ScrolledWindow()
                self.labels['connecting_info'] = Gtk.Label(
                    label=_("Starting WiFi Association"), halign=Gtk.Align.START, valign=Gtk.Align.START, wrap=True)
                scroll.add(self.labels['connecting_info'])
                
                # Save dialog instance
                self.connecting_dialog = self._gtk.Dialog(
                    _("Starting WiFi Association"), buttons, scroll, self._gtk.remove_dialog
                )
                self.connecting_dialog.connect("response", self.on_connecting_dialog_close)

                self._screen.show_all()

                self.wifi.add_callback("connecting_status", self.connecting_status_callback)
                
                def on_connect_result(result, error):
                    if error:
                        logging.error(f"Connection failed: {error}")
                        
                self.wifi.connect(ssid, on_connect_result)
                
            self.wifi.get_connected_ssid(on_connected_ssid)
            
        self.wifi.get_supplicant_networks(on_supplicant_networks)

    def on_connecting_dialog_close(self, dialog, response):
        """Clean up callbacks when user manually closes dialog"""
        self.connecting_dialog = None
        if self.wifi:
            self.wifi.remove_callback("connecting_status", self.connecting_status_callback)
            
    def connecting_status_callback(self, msg):
        if 'connecting_info' in self.labels:
            self.labels['connecting_info'].set_text(f"{self.labels['connecting_info'].get_text()}\n{msg}")
            self.labels['connecting_info'].show_all()

        # Check if connection is complete or failed
        final_states = ["Connected", "Connection failed", "已连接", "连接失败"]
        if any(state in msg for state in final_states):
            # Delay closing dialog so user can see final status
            GLib.timeout_add_seconds(2, self.close_connecting_dialog)

    def close_connecting_dialog(self):
        """Close connecting dialog and remove callbacks"""
        if self.connecting_dialog:
            self._gtk.remove_dialog(self.connecting_dialog)
            self.connecting_dialog = None
        if self.wifi:
            self.wifi.remove_callback("connecting_status", self.connecting_status_callback)
        return False  # Execute only once

    def remove_network(self, ssid, show=True):
        if ssid not in list(self.networks):
            return
        
        # Safely find and remove network row
        try:
            # Find the network by iterating through all rows
            network_widget = self.networks[ssid]
            found_row = -1
            
            # Get row count in Grid
            for row in range(100):  # Use reasonable upper limit
                child = self.labels['networklist'].get_child_at(0, row)
                if child is None:
                    break
                if child == network_widget:
                    found_row = row
                    break
            
            if found_row >= 0:
                self.labels['networklist'].remove_row(found_row)
                self.labels['networklist'].show()
            
            # Clean up data structures
            del self.networks[ssid]
            if ssid in self.labels['networks']:
                del self.labels['networks'][ssid]
                
        except Exception as e:
            logging.error(f"Error removing network {ssid}: {e}")

    def remove_wifi_network(self, widget, ssid):
        def on_network_deleted(result, error):
            if error:
                logging.error(f"Failed to delete network: {error}")
            else:
                self.remove_network(ssid)
                self.check_missing_networks()
                
        self.wifi.delete_network(ssid, on_network_deleted)

    def scan_callback(self, new_networks, old_networks):
        for net in old_networks:
            self.remove_network(net, False)
        for net in new_networks:
            self.add_network(net, False)
        self.content.show_all()

    def show_add_network(self, widget, ssid):
        if self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        if "add_network" in self.labels:
            del self.labels['add_network']

        label = Gtk.Label(label=_("PSK for") + f' {ssid}', hexpand=False)
        self.labels['network_psk'] = Gtk.Entry(hexpand=True)
        self.labels['network_psk'].connect("activate", self.add_new_network, ssid)
        self.labels['network_psk'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("sd", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.add_new_network, ssid)

        box = Gtk.Box()
        box.pack_start(self.labels['network_psk'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['add_network'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, valign=Gtk.Align.CENTER,
                                             hexpand=True, vexpand=True)
        self.labels['add_network'].pack_start(label, True, True, 5)
        self.labels['add_network'].pack_start(box, True, True, 5)

        self.content.add(self.labels['add_network'])
        self.labels['network_psk'].grab_focus_without_selecting()
        self.content.show_all()
        self.show_add = True

    def update_all_networks_async(self):
        """Update all network information asynchronously"""
        if self.wifi is None or not self.wifi.initialized:
            return True  # Continue periodic calls, wait for initialization
            
        networks_to_update = list(self.networks.keys())
        
        def update_next_network():
            if not networks_to_update:
                return True  # Return True to continue periodic calls
                
            ssid = networks_to_update.pop(0)
            
            def on_network_info_updated(netinfo, error):
                if not error and netinfo:
                    self.update_network_info_with_data(ssid, netinfo)
                # Continue updating next network
                GLib.idle_add(update_next_network)
                
            if ssid in self.networks:  # Ensure network still exists
                self.wifi.get_network_info(ssid, on_network_info_updated)
            else:
                GLib.idle_add(update_next_network)
                
        update_next_network()
        return True

    def update_network_info_with_data(self, ssid, netinfo):
        """Update UI with provided network information"""
        if ssid not in list(self.networks) or ssid not in self.labels['networks']:
            logging.info(f"Unknown SSID {ssid}")
            return

        def on_connected_ssid(connected_ssid, error):
            # Initialize all variables
            info = freq = encr = chan = lvl = ipv4 = ipv6 = ""
            
            if error:
                connected_ssid = None
                
            if netinfo.get('connected') or connected_ssid == ssid:
                ifadd = netifaces.ifaddresses(self.interface)
                if ifadd.get(netifaces.AF_INET):
                    ipv4 = f"<b>IPv4:</b> {ifadd[netifaces.AF_INET][0]['addr']}"
                    self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")
                if ifadd.get(netifaces.AF_INET6):
                    ipv6 = f"<b>IPv6:</b> {ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0]}"

                info = '<b>' + _("Hostname") + f':</b> {os.uname().nodename}\n{ipv4}\n{ipv6}'
            else:
                self.labels['networks'][ssid]['name'].set_label(_("Hidden") if ssid.startswith("\x00") else f"{ssid}")
                if "psk" in netinfo:
                    info = _("Password saved")
                    
            if "encryption" in netinfo and netinfo['encryption'] != "off":
                encr = netinfo['encryption'].upper()
            if "frequency" in netinfo:
                freq = "2.4 GHz" if netinfo['frequency'][:1] == "2" else "5 Ghz"
            if "channel" in netinfo:
                chan = _("Channel") + f' {netinfo["channel"]}'
            if "signal_level_dBm" in netinfo:
                unit = "%" if self.use_network_manager else _("dBm")
                lvl = f"{netinfo['signal_level_dBm']} {unit}"
                icon = self.signal_strength(int(netinfo["signal_level_dBm"]))
                if 'icon' not in self.labels['networks'][ssid]:
                    self.labels['networks'][ssid]['row'].add(icon)
                    self.labels['networks'][ssid]['row'].reorder_child(icon, 0)
                    self.labels['networks'][ssid]['icon'] = icon
                self.labels['networks'][ssid]['icon'] = icon

            self.labels['networks'][ssid]['info'].set_markup(f"{info}\n<small>{encr}  {freq}  {chan}  {lvl}</small>")
            self.labels['networks'][ssid]['row'].show_all()
            
        self.wifi.get_connected_ssid(on_connected_ssid)

    def signal_strength(self, signal_level):
        # networkmanager uses percentage not dbm
        # the bars of nmcli are aligned near this breakpoints
        exc = 77 if self.use_network_manager else -50
        good = 60 if self.use_network_manager else -60
        fair = 35 if self.use_network_manager else -70
        if signal_level > exc:
            return self._gtk.Image('wifi_excellent')
        elif signal_level > good:
            return self._gtk.Image('wifi_good')
        elif signal_level > fair:
            return self._gtk.Image('wifi_fair')
        else:
            return self._gtk.Image('wifi_weak')

    def update_single_network_info(self):
        ifadd = netifaces.ifaddresses(self.interface)
        ipv6 = f"{ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0]}" if ifadd.get(netifaces.AF_INET6) else ""
        if netifaces.AF_INET in ifadd and ifadd[netifaces.AF_INET]:
            ipv4 = f"{ifadd[netifaces.AF_INET][0]['addr']} "
            self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")
        else:
            ipv4 = ""
        self.labels['networkinfo'].set_markup(
            f'<b>{self.interface}</b>\n\n'
            + '<b>' + _("Hostname") + f':</b> {os.uname().nodename}\n'
            f'<b>IPv4:</b> {ipv4}\n'
            f'<b>IPv6:</b> {ipv6}'
        )
        self.labels['networkinfo'].show_all()
        return True

    def reload_networks(self, widget=None):
        self.networks = {}
        self.labels['networklist'].remove_column(0)
        if self.wifi is not None:
            if not self.wifi.initialized:
                logging.warning("WiFi Manager not initialized, cannot rescan")
                if widget:
                    GLib.timeout_add_seconds(1, self._gtk.Button_busy, widget, False)
                return
                
            if widget:
                self._gtk.Button_busy(widget, True)
                
            def on_rescan_complete(result, error):
                if error:
                    logging.error(f"Rescan failed: {error}")
                    if widget:
                        GLib.timeout_add_seconds(10, self._gtk.Button_busy, widget, False)
                else:
                    # Load network list after scan completes
                    GLib.timeout_add_seconds(2, self.load_networks_async, widget)
                    
            self.wifi.rescan(on_rescan_complete)

    def delayed_network_loading(self):
        """Delay network loading to wait for WiFi Manager initialization"""
        if self.wifi is not None and self.wifi.initialized:
            logging.info("WiFi Manager initialized, starting network list loading")
            self.load_networks_async()
            return False  # Stop repeating calls
        else:
            return True  # Continue waiting

    def activate(self):
        if self.initialized:
            self.reload_networks()
            if self.update_timeout is None:
                if self.wifi is not None:
                    self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks_async)
                else:
                    self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

    def deactivate(self):
        if self.update_timeout is not None:
            GLib.source_remove(self.update_timeout)
            self.update_timeout = None

    def on_back_click(self, widget=None):
        # Check if coming from setup_force_move panel via setup_init
        if self._screen.setup_init != 2:
            self._screen.show_panel("setup_force_move", _("Remove Foam"), remove_all=True)
        else:
            # Otherwise return to language selection panel
            self._screen.show_panel("setup_wizard", _("Choose Language"), remove_all=True)

    def on_next_click(self, widget=None):
        self._screen.setup_init = 0
        self._screen.save_init_step()
        self._screen._ws.klippy.restart_firmware()
        os.system('systemctl restart KlipperScreen.service')