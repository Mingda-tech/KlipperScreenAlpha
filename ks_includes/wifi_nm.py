# Network in KlipperScreen is a connection in NetworkManager
# Interface in KlipperScreen is a device in NetworkManager

import logging
import uuid
import dbus
import gi
import threading
import queue
from typing import Callable, Any, Dict, Optional

gi.require_version('Gdk', '3.0')
from gi.repository import GLib
from contextlib import suppress
from ks_includes.wifi import WifiChannels
from ks_includes import NetworkManager
from dbus.mainloop.glib import DBusGMainLoop


class WorkerTask:
    """Represents a background task."""
    def __init__(self, task_type: str, args: tuple = (), kwargs: dict = None, callback: Callable = None):
        self.task_type = task_type
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.callback = callback


class WifiManager:
    """Fully asynchronous WiFi manager, all operations are executed in a background thread."""
    
    def __init__(self, interface_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DBusGMainLoop(set_as_default=True)
        
        # Callback system
        self._callbacks = {
            "connected": [],
            "connecting_status": [],
            "scan_results": [],
            "popup": [],
        }
        
        # State variables
        self.connected = False
        self.connected_ssid = None
        self.interface_name = interface_name
        self.known_networks = {}  # List of known connections
        self.visible_networks = {}  # List of visible access points
        self.ssid_by_path = {}
        self.path_by_ssid = {}
        self.hidden_ssid_index = 0

        # Initialize background worker thread system
        self._task_queue = queue.Queue()
        self._worker_thread = None
        self._shutdown_event = threading.Event()
        self._thread_lock = threading.Lock()
        
        # NetworkManager device initialization
        self.wifi_dev = None
        self.initialized = False
        
        # Start background thread and initialize
        self._start_worker_thread()
        self._initialize_async()

    def _start_worker_thread(self):
        """Start the background worker thread."""
        with self._thread_lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._shutdown_event.clear()
                self._worker_thread = threading.Thread(target=self._worker_thread_func, daemon=True)
                self._worker_thread.start()
                logging.debug("WiFi Manager background worker thread started")

    def _worker_thread_func(self):
        """Main function of the background worker thread, handles all time-consuming D-Bus operations."""
        logging.debug("WiFi Manager background worker thread running")
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for a task, timeout after 1 second to check for shutdown signal
                task = self._task_queue.get(timeout=1.0)
                
                try:
                    result = None
                    error = None
                    
                    # Execute corresponding operation based on task type
                    if task.task_type == "initialize":
                        result = self._worker_initialize(*task.args, **task.kwargs)
                    elif task.task_type == "rescan":
                        result = self._worker_rescan(*task.args, **task.kwargs)
                    elif task.task_type == "get_networks":
                        result = self._worker_get_networks(*task.args, **task.kwargs)
                    elif task.task_type == "get_network_info":
                        result = self._worker_get_network_info(*task.args, **task.kwargs)
                    elif task.task_type == "connect":
                        result = self._worker_connect(*task.args, **task.kwargs)
                    elif task.task_type == "add_network":
                        result = self._worker_add_network(*task.args, **task.kwargs)
                    elif task.task_type == "delete_network":
                        result = self._worker_delete_network(*task.args, **task.kwargs)
                    elif task.task_type == "update_known_connections":
                        result = self._worker_update_known_connections(*task.args, **task.kwargs)
                    elif task.task_type == "get_connected_ssid":
                        result = self._worker_get_connected_ssid(*task.args, **task.kwargs)
                    elif task.task_type == "get_supplicant_networks":
                        result = self._worker_get_supplicant_networks(*task.args, **task.kwargs)
                    else:
                        error = f"Unknown task type: {task.task_type}"
                        
                except Exception as e:
                    error = str(e)
                    logging.error(f"Background task {task.task_type} failed: {e}")
                
                # If there is a callback function, call it safely via GLib.idle_add
                if task.callback:
                    if error:
                        GLib.idle_add(task.callback, None, error)
                    else:
                        GLib.idle_add(task.callback, result, None)
                        
                self._task_queue.task_done()
                
            except queue.Empty:
                # Timeout, continue loop to check for shutdown signal
                continue
            except Exception as e:
                logging.error(f"Exception in background worker thread: {e}")
                
        logging.info("WiFi Manager background worker thread stopped")

    def _submit_task(self, task_type: str, callback: Optional[Callable] = None, *args, **kwargs):
        """Submit a task to the background thread."""
        if self._shutdown_event.is_set():
            logging.warning("Worker thread is shut down, cannot submit task")
            if callback:
                GLib.idle_add(callback, None, "Worker thread is shut down")
            return
            
        task = WorkerTask(task_type, args, kwargs, callback)
        self._task_queue.put(task)

    def shutdown(self):
        """Shutdown the background worker thread."""
        logging.info("Shutting down WiFi Manager background worker thread...")
        self._shutdown_event.set()
        
        with self._thread_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=5.0)
                if self._worker_thread.is_alive():
                    logging.warning("Background worker thread did not shut down in time")

    # =============== Background Thread Worker Functions ===============
    
    def _worker_initialize(self):
        """Initialization in the background thread."""
        try:
            self.wifi_dev = NetworkManager.NetworkManager.GetDeviceByIpIface(self.interface_name)
            self.wifi_dev.OnAccessPointAdded(self._ap_added)
            self.wifi_dev.OnAccessPointRemoved(self._ap_removed)
            self.wifi_dev.OnStateChanged(self._ap_state_changed)

            access_points = self.wifi_dev.GetAccessPoints()
            logging.debug(f"Found {len(access_points)} access points")
            
            for ap in access_points:
                ssid = self._add_ap(ap)
                logging.debug(f"Added access point: {ssid}")
            
            self._worker_update_known_connections()
            self.initialized = True
            logging.info("WiFi Manager initialized")
            return True
        except Exception as e:
            logging.error(f"WiFi Manager initialization failed: {e}")
            raise

    def _worker_update_known_connections(self):
        """Update known connections in the background thread."""
        self.known_networks = {}
        connections = NetworkManager.Settings.ListConnections()
        logging.debug(f"Checking {len(connections)} NetworkManager connections")
        
        for con in connections:
            settings = con.GetSettings()
            if "802-11-wireless" in settings:
                ssid = settings["802-11-wireless"]['ssid']
                self.known_networks[ssid] = con
                logging.debug(f"Added known network: {ssid}")
                
        logging.debug(f"Found {len(self.known_networks)} known WiFi networks")
        return self.known_networks

    def _worker_rescan(self):
        """Perform WiFi scan in the background thread."""
        try:
            self.wifi_dev.RequestScan({})
            return True
        except dbus.exceptions.DBusException as e:
            logging.error(f"Error during scan: {e}")
            raise

    def _worker_get_networks(self):
        """Get network list in the background thread."""
        known_networks = list(self.known_networks.keys())
        visible_networks = list(self.ssid_by_path.values())
        all_networks = list(set(known_networks + visible_networks))
        
        logging.debug(f"Known networks: {known_networks}")
        logging.debug(f"Visible networks: {visible_networks}")
        logging.debug(f"All networks: {all_networks}")
        
        return all_networks

    def _worker_get_network_info(self, ssid: str):
        """Get network details in the background thread."""
        netinfo = {}
        if ssid in self.known_networks:
            con = self.known_networks[ssid]
            with suppress(NetworkManager.ObjectVanished):
                try:
                    settings = con.GetSettings()
                    if settings and '802-11-wireless' in settings:
                        netinfo.update({
                            "ssid": settings['802-11-wireless']['ssid'],
                            "connected": self._worker_get_connected_ssid() == ssid
                        })
                except Exception as e:
                    logging.debug(f"Error getting settings for network {ssid}: {e}")
        
        path = self.path_by_ssid.get(ssid)
        if path and path in self.visible_networks:
            ap = self.visible_networks[path]
            with suppress(NetworkManager.ObjectVanished):
                try:
                    # Safely get frequency and channel info
                    frequency = getattr(ap, 'Frequency', None)
                    channel_info = None
                    if frequency:
                        try:
                            channel_info = WifiChannels.lookup(str(frequency))
                        except Exception as e:
                            logging.debug(f"Error looking up channel info: {e}")
                    
                    netinfo.update({
                        "mac": getattr(ap, 'HwAddress', ''),
                        "channel": channel_info[1] if channel_info and len(channel_info) > 1 else '',
                        "configured": ssid in self.known_networks,
                        "frequency": str(frequency) if frequency else '',
                        "flags": getattr(ap, 'Flags', 0),
                        "ssid": ssid,
                        "connected": self._get_connected_ap() == ap,
                        "encryption": self._get_encryption(getattr(ap, 'RsnFlags', 0)),
                        "signal_level_dBm": str(getattr(ap, 'Strength', 0))
                    })
                except Exception as e:
                    logging.debug(f"Error getting info for access point {ssid}: {e}")
                    # Provide basic info
                    netinfo.update({
                        "ssid": ssid,
                        "configured": ssid in self.known_networks,
                        "connected": False,
                        "encryption": "",
                        "signal_level_dBm": "0"
                    })
        return netinfo

    def _worker_connect(self, ssid: str):
        """Connect to a WiFi network in the background thread."""
        if ssid in self.known_networks:
            conn = self.known_networks[ssid]
            with suppress(NetworkManager.ObjectVanished):
                msg = f"Connecting to: {ssid}"
                logging.info(msg)
                # Update status via callback on the main thread
                GLib.idle_add(self.callback, "connecting_status", msg)
                NetworkManager.NetworkManager.ActivateConnection(conn, self.wifi_dev, "/")
                return True
        return False

    def _worker_add_network(self, ssid: str, psk: str):
        """Add a new WiFi network in the background thread."""
        new_connection = {
            '802-11-wireless': {
                'mode': 'infrastructure',
                'security': '802-11-wireless-security',
                'ssid': ssid
            },
            '802-11-wireless-security': {
                'auth-alg': 'open',
                'key-mgmt': 'wpa-psk',
                'psk': psk
            },
            'connection': {
                'id': ssid,
                'type': '802-11-wireless',
                'uuid': str(uuid.uuid4())
            },
            'ipv4': {
                'method': 'auto'
            },
            'ipv6': {
                'method': 'auto'
            }
        }
        try:
            NetworkManager.Settings.AddConnection(new_connection)
            # Update the list of known connections
            self._worker_update_known_connections()
            return True
        except dbus.exceptions.DBusException as e:
            msg = _("Invalid password") if "802-11-wireless-security.psk" in str(e) else f"{e}"
            GLib.idle_add(self.callback, "popup", msg)
            logging.info(f"Error adding network: {e}")
            raise

    def _worker_delete_network(self, ssid: str):
        """Delete a WiFi network in the background thread."""
        if ssid in self.known_networks:
            con = self.known_networks[ssid]
            con.Delete()
            # Update the list of known connections
            self._worker_update_known_connections()
            return True
        return False

    def _worker_get_connected_ssid(self):
        """Get the currently connected SSID in the background thread."""
        if self.wifi_dev and self.wifi_dev.SpecificDevice().ActiveAccessPoint:
            return self.wifi_dev.SpecificDevice().ActiveAccessPoint.Ssid
        return None

    def _worker_get_supplicant_networks(self):
        """Get supplicant networks in the background thread."""
        return {ssid: {"ssid": ssid} for ssid in self.known_networks.keys()}

    # =============== Async Public Interface Methods ===============
    
    def _initialize_async(self):
        """Async initialization."""
        self._submit_task("initialize")

    def rescan(self, callback: Optional[Callable] = None):
        """Perform WiFi scan asynchronously."""
        self._submit_task("rescan", callback)

    def get_networks(self, callback: Optional[Callable] = None):
        """Get network list asynchronously."""
        self._submit_task("get_networks", callback)

    def get_network_info(self, ssid: str, callback: Optional[Callable] = None):
        """Get network details asynchronously."""
        self._submit_task("get_network_info", callback, ssid)

    def connect(self, ssid: str, callback: Optional[Callable] = None):
        """Connect to a WiFi network asynchronously."""
        self._submit_task("connect", callback, ssid)

    def add_network(self, ssid: str, psk: str, callback: Optional[Callable] = None):
        """Add a new WiFi network asynchronously."""
        self._submit_task("add_network", callback, ssid, psk)

    def delete_network(self, ssid: str, callback: Optional[Callable] = None):
        """Delete a WiFi network asynchronously."""
        self._submit_task("delete_network", callback, ssid)

    def get_connected_ssid(self, callback: Optional[Callable] = None):
        """Get the currently connected SSID asynchronously."""
        self._submit_task("get_connected_ssid", callback)

    def update_known_connections(self, callback: Optional[Callable] = None):
        """Update known connections asynchronously."""
        self._submit_task("update_known_connections", callback)

    def get_supplicant_networks(self, callback: Optional[Callable] = None):
        """Get supplicant networks asynchronously."""
        self._submit_task("get_supplicant_networks", callback)

    # =============== Signal Handling and Helper Methods ===============
    
    def _ap_added(self, nm, interface, signal, access_point):
        """Access point added callback."""
        with suppress(NetworkManager.ObjectVanished):
            ssid = self._add_ap(access_point)
            for cb in self._callbacks['scan_results']:
                args = (cb, [ssid], [])
                GLib.idle_add(*args)

    def _ap_removed(self, dev, interface, signal, access_point):
        """Access point removed callback."""
        path = access_point.object_path
        if path in self.ssid_by_path:
            ssid = self.ssid_by_path[path]
            self._remove_ap(path)
            for cb in self._callbacks['scan_results']:
                args = (cb, [], [ssid])
                GLib.idle_add(*args)

    def _ap_state_changed(self, nm, interface, signal, old_state, new_state, reason):
        """Device state change callback."""
        msg = ""
        if new_state in (NetworkManager.NM_DEVICE_STATE_UNKNOWN, NetworkManager.NM_DEVICE_STATE_REASON_UNKNOWN):
            msg = "State unknown"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNMANAGED:
            msg = "Error: Not managed by NetworkManager"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNAVAILABLE:
            msg = "Error: Device not available\nPossible reasons: WiFi switch off, missing firmware, etc."
        elif new_state == NetworkManager.NM_DEVICE_STATE_DISCONNECTED:
            msg = "Currently disconnected"
        elif new_state == NetworkManager.NM_DEVICE_STATE_PREPARE:
            msg = "Preparing to connect to the network"
        elif new_state == NetworkManager.NM_DEVICE_STATE_CONFIG:
            msg = "Connecting to the requested network..."
        elif new_state == NetworkManager.NM_DEVICE_STATE_NEED_AUTH:
            msg = "Authenticating"
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CONFIG:
            msg = "Requesting IP address and routing information"
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CHECK:
            msg = "Checking if further action is needed"
        elif new_state == NetworkManager.NM_DEVICE_STATE_SECONDARIES:
            msg = "Waiting for secondary connections (like VPN)"
        elif new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            msg = "Connected"
            self.connected = True
            # Get connected SSID asynchronously
            def on_connected_ssid(ssid, error):
                if not error:
                    for cb in self._callbacks['connected']:
                        args = (cb, ssid, None)
                        GLib.idle_add(*args)
            self.get_connected_ssid(on_connected_ssid)
        elif new_state == NetworkManager.NM_DEVICE_STATE_DEACTIVATING:
            msg = "Disconnecting"
            self.connected = False
        elif new_state == NetworkManager.NM_DEVICE_STATE_FAILED:
            msg = "Connection failed"
            self.connected = False
            self.callback("popup", msg)
        elif new_state == NetworkManager.NM_DEVICE_STATE_REASON_DEPENDENCY_FAILED:
            msg = "Connection dependency failed"
        elif new_state == NetworkManager.NM_DEVICE_STATE_REASON_CARRIER:
            msg = ""
        else:
            logging.debug(f"Device state: {new_state}")
            
        if msg != "":
            self.callback("connecting_status", msg)

    def _add_ap(self, ap):
        """Add an access point."""
        ssid = ap.Ssid
        if ssid == "":
            ssid = _("Hidden Network") + f" {self.hidden_ssid_index}"
            self.hidden_ssid_index += 1
        self.ssid_by_path[ap.object_path] = ssid
        self.path_by_ssid[ssid] = ap.object_path
        self.visible_networks[ap.object_path] = ap
        return ssid

    def _remove_ap(self, path):
        """Remove an access point."""
        ssid = self.ssid_by_path.pop(path, None)
        if ssid:
            self.path_by_ssid.pop(ssid, None)
        self.visible_networks.pop(path, None)

    def _get_connected_ap(self):
        """Get the currently connected access point."""
        if self.wifi_dev:
            return self.wifi_dev.SpecificDevice().ActiveAccessPoint
        return None

    def _visible_networks_by_ssid(self):
        """Get visible networks by SSID."""
        if not self.wifi_dev:
            return {}
        aps = self.wifi_dev.GetAccessPoints()
        ret = {}
        for ap in aps:
            with suppress(NetworkManager.ObjectVanished):
                ret[ap.Ssid] = ap
        return ret

    @staticmethod
    def _get_encryption(flags):
        """Get encryption type."""
        encryption = ""
        if (flags & NetworkManager.NM_802_11_AP_SEC_PAIR_WEP40 or
                flags & NetworkManager.NM_802_11_AP_SEC_PAIR_WEP104 or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_WEP40 or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_WEP104):
            encryption += "WEP "
        if (flags & NetworkManager.NM_802_11_AP_SEC_PAIR_TKIP or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_TKIP):
            encryption += "TKIP "
        if (flags & NetworkManager.NM_802_11_AP_SEC_PAIR_CCMP or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_CCMP):
            encryption += "AES "
        if flags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_PSK:
            encryption += "WPA-PSK "
        if flags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_802_1X:
            encryption += "802.1x "
        return encryption.strip()

    # =============== Callback System ===============
    
    def add_callback(self, name, callback):
        """Add a callback function."""
        if name in self._callbacks and callback not in self._callbacks[name]:
            self._callbacks[name].append(callback)

    def remove_callback(self, name, callback):
        """Remove a callback function."""
        if name in self._callbacks and callback in self._callbacks[name]:
            self._callbacks[name].remove(callback)
            logging.debug(f"Removed callback for {name}")

    def callback(self, cb_type, msg):
        """Trigger callbacks."""
        if cb_type in self._callbacks:
            for cb in self._callbacks[cb_type]:
                GLib.idle_add(cb, msg)

    # =============== Destructor ===============
    
    def __del__(self):
        """Destructor, ensures the background thread is properly shut down."""
        try:
            self.shutdown()
        except:
            pass  # Ignore any exceptions during destruction
