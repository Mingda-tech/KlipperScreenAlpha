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
    """表示一个后台任务的类"""
    def __init__(self, task_type: str, args: tuple = (), kwargs: dict = None, callback: Callable = None):
        self.task_type = task_type
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.callback = callback


class WifiManager:
    """完全异步化的WiFi管理器，所有操作都在后台线程中执行"""
    
    def __init__(self, interface_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DBusGMainLoop(set_as_default=True)
        
        # 回调系统
        self._callbacks = {
            "connected": [],
            "connecting_status": [],
            "scan_results": [],
            "popup": [],
        }
        
        # 状态变量
        self.connected = False
        self.connected_ssid = None
        self.interface_name = interface_name
        self.known_networks = {}  # List of known connections
        self.visible_networks = {}  # List of visible access points
        self.ssid_by_path = {}
        self.path_by_ssid = {}
        self.hidden_ssid_index = 0

        # 初始化后台工作线程系统
        self._task_queue = queue.Queue()
        self._worker_thread = None
        self._shutdown_event = threading.Event()
        self._thread_lock = threading.Lock()
        
        # NetworkManager设备初始化
        self.wifi_dev = None
        self.initialized = False
        
        # 启动后台线程并进行初始化
        self._start_worker_thread()
        self._initialize_async()

    def _start_worker_thread(self):
        """启动后台工作线程"""
        with self._thread_lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._shutdown_event.clear()
                self._worker_thread = threading.Thread(target=self._worker_thread_func, daemon=True)
                self._worker_thread.start()
                logging.info("WiFi Manager后台工作线程已启动")

    def _worker_thread_func(self):
        """后台工作线程的主函数，处理所有耗时的D-Bus操作"""
        logging.info("WiFi Manager后台工作线程开始运行")
        
        while not self._shutdown_event.is_set():
            try:
                # 等待任务，超时1秒以便检查shutdown信号
                task = self._task_queue.get(timeout=1.0)
                
                try:
                    result = None
                    error = None
                    
                    # 根据任务类型执行相应的操作
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
                        error = f"未知的任务类型: {task.task_type}"
                        
                except Exception as e:
                    error = str(e)
                    logging.error(f"后台任务 {task.task_type} 执行失败: {e}")
                
                # 如果有回调函数，通过GLib.idle_add安全地调用回调
                if task.callback:
                    if error:
                        GLib.idle_add(task.callback, None, error)
                    else:
                        GLib.idle_add(task.callback, result, None)
                        
                self._task_queue.task_done()
                
            except queue.Empty:
                # 超时，继续循环检查shutdown信号
                continue
            except Exception as e:
                logging.error(f"后台工作线程出现异常: {e}")
                
        logging.info("WiFi Manager后台工作线程已停止")

    def _submit_task(self, task_type: str, callback: Optional[Callable] = None, *args, **kwargs):
        """提交任务到后台线程"""
        if self._shutdown_event.is_set():
            logging.warning("工作线程已关闭，无法提交任务")
            if callback:
                GLib.idle_add(callback, None, "工作线程已关闭")
            return
            
        task = WorkerTask(task_type, args, kwargs, callback)
        self._task_queue.put(task)

    def shutdown(self):
        """关闭后台工作线程"""
        logging.info("正在关闭WiFi Manager后台工作线程...")
        self._shutdown_event.set()
        
        with self._thread_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=5.0)
                if self._worker_thread.is_alive():
                    logging.warning("后台工作线程未能在规定时间内关闭")

    # =============== 后台线程工作函数 ===============
    
    def _worker_initialize(self):
        """在后台线程中进行初始化"""
        try:
            self.wifi_dev = NetworkManager.NetworkManager.GetDeviceByIpIface(self.interface_name)
            self.wifi_dev.OnAccessPointAdded(self._ap_added)
            self.wifi_dev.OnAccessPointRemoved(self._ap_removed)
            self.wifi_dev.OnStateChanged(self._ap_state_changed)

            access_points = self.wifi_dev.GetAccessPoints()
            logging.info(f"找到 {len(access_points)} 个接入点")
            
            for ap in access_points:
                ssid = self._add_ap(ap)
                logging.debug(f"添加接入点: {ssid}")
            
            self._worker_update_known_connections()
            self.initialized = True
            logging.info("WiFi Manager 初始化完成")
            return True
        except Exception as e:
            logging.error(f"WiFi Manager 初始化失败: {e}")
            raise

    def _worker_update_known_connections(self):
        """在后台线程中更新已知连接"""
        self.known_networks = {}
        connections = NetworkManager.Settings.ListConnections()
        logging.info(f"检查 {len(connections)} 个NetworkManager连接")
        
        for con in connections:
            settings = con.GetSettings()
            if "802-11-wireless" in settings:
                ssid = settings["802-11-wireless"]['ssid']
                self.known_networks[ssid] = con
                logging.debug(f"添加已知网络: {ssid}")
                
        logging.info(f"找到 {len(self.known_networks)} 个已知WiFi网络")
        return self.known_networks

    def _worker_rescan(self):
        """在后台线程中执行WiFi扫描"""
        try:
            self.wifi_dev.RequestScan({})
            return True
        except dbus.exceptions.DBusException as e:
            logging.error(f"扫描时出错: {e}")
            raise

    def _worker_get_networks(self):
        """在后台线程中获取网络列表"""
        known_networks = list(self.known_networks.keys())
        visible_networks = list(self.ssid_by_path.values())
        all_networks = list(set(known_networks + visible_networks))
        
        logging.info(f"已知网络: {known_networks}")
        logging.info(f"可见网络: {visible_networks}")
        logging.info(f"所有网络: {all_networks}")
        
        return all_networks

    def _worker_get_network_info(self, ssid: str):
        """在后台线程中获取网络详细信息"""
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
                    logging.debug(f"获取网络 {ssid} 的设置时出错: {e}")
        
        path = self.path_by_ssid.get(ssid)
        if path and path in self.visible_networks:
            ap = self.visible_networks[path]
            with suppress(NetworkManager.ObjectVanished):
                try:
                    # 安全地获取频率和信道信息
                    frequency = getattr(ap, 'Frequency', None)
                    channel_info = None
                    if frequency:
                        try:
                            channel_info = WifiChannels.lookup(str(frequency))
                        except Exception as e:
                            logging.debug(f"查找信道信息时出错: {e}")
                    
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
                    logging.debug(f"获取接入点 {ssid} 信息时出错: {e}")
                    # 提供基本信息
                    netinfo.update({
                        "ssid": ssid,
                        "configured": ssid in self.known_networks,
                        "connected": False,
                        "encryption": "",
                        "signal_level_dBm": "0"
                    })
        return netinfo

    def _worker_connect(self, ssid: str):
        """在后台线程中连接到WiFi网络"""
        if ssid in self.known_networks:
            conn = self.known_networks[ssid]
            with suppress(NetworkManager.ObjectVanished):
                msg = f"正在连接到: {ssid}"
                logging.info(msg)
                # 通过主线程回调更新状态
                GLib.idle_add(self.callback, "connecting_status", msg)
                NetworkManager.NetworkManager.ActivateConnection(conn, self.wifi_dev, "/")
                return True
        return False

    def _worker_add_network(self, ssid: str, psk: str):
        """在后台线程中添加新的WiFi网络"""
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
            # 更新已知连接列表
            self._worker_update_known_connections()
            return True
        except dbus.exceptions.DBusException as e:
            msg = _("密码无效") if "802-11-wireless-security.psk" in str(e) else f"{e}"
            GLib.idle_add(self.callback, "popup", msg)
            logging.info(f"添加网络时出错: {e}")
            raise

    def _worker_delete_network(self, ssid: str):
        """在后台线程中删除WiFi网络"""
        if ssid in self.known_networks:
            con = self.known_networks[ssid]
            con.Delete()
            # 更新已知连接列表
            self._worker_update_known_connections()
            return True
        return False

    def _worker_get_connected_ssid(self):
        """在后台线程中获取当前连接的SSID"""
        if self.wifi_dev and self.wifi_dev.SpecificDevice().ActiveAccessPoint:
            return self.wifi_dev.SpecificDevice().ActiveAccessPoint.Ssid
        return None

    def _worker_get_supplicant_networks(self):
        """在后台线程中获取supplicant网络"""
        return {ssid: {"ssid": ssid} for ssid in self.known_networks.keys()}

    # =============== 异步公共接口方法 ===============
    
    def _initialize_async(self):
        """异步初始化"""
        self._submit_task("initialize")

    def rescan(self, callback: Optional[Callable] = None):
        """异步执行WiFi扫描"""
        self._submit_task("rescan", callback)

    def get_networks(self, callback: Optional[Callable] = None):
        """异步获取网络列表"""
        self._submit_task("get_networks", callback)

    def get_network_info(self, ssid: str, callback: Optional[Callable] = None):
        """异步获取网络详细信息"""
        self._submit_task("get_network_info", callback, ssid)

    def connect(self, ssid: str, callback: Optional[Callable] = None):
        """异步连接到WiFi网络"""
        self._submit_task("connect", callback, ssid)

    def add_network(self, ssid: str, psk: str, callback: Optional[Callable] = None):
        """异步添加新的WiFi网络"""
        self._submit_task("add_network", callback, ssid, psk)

    def delete_network(self, ssid: str, callback: Optional[Callable] = None):
        """异步删除WiFi网络"""
        self._submit_task("delete_network", callback, ssid)

    def get_connected_ssid(self, callback: Optional[Callable] = None):
        """异步获取当前连接的SSID"""
        self._submit_task("get_connected_ssid", callback)

    def update_known_connections(self, callback: Optional[Callable] = None):
        """异步更新已知连接"""
        self._submit_task("update_known_connections", callback)

    def get_supplicant_networks(self, callback: Optional[Callable] = None):
        """异步获取supplicant网络"""
        self._submit_task("get_supplicant_networks", callback)

    # =============== 信号处理和辅助方法 ===============
    
    def _ap_added(self, nm, interface, signal, access_point):
        """接入点添加回调"""
        with suppress(NetworkManager.ObjectVanished):
            ssid = self._add_ap(access_point)
            for cb in self._callbacks['scan_results']:
                args = (cb, [ssid], [])
                GLib.idle_add(*args)

    def _ap_removed(self, dev, interface, signal, access_point):
        """接入点移除回调"""
        path = access_point.object_path
        if path in self.ssid_by_path:
            ssid = self.ssid_by_path[path]
            self._remove_ap(path)
            for cb in self._callbacks['scan_results']:
                args = (cb, [], [ssid])
                GLib.idle_add(*args)

    def _ap_state_changed(self, nm, interface, signal, old_state, new_state, reason):
        """设备状态改变回调"""
        msg = ""
        if new_state in (NetworkManager.NM_DEVICE_STATE_UNKNOWN, NetworkManager.NM_DEVICE_STATE_REASON_UNKNOWN):
            msg = "状态未知"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNMANAGED:
            msg = "错误：未被NetworkManager管理"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNAVAILABLE:
            msg = "错误：设备不可用\n可能的原因包括WiFi开关关闭、缺少固件等"
        elif new_state == NetworkManager.NM_DEVICE_STATE_DISCONNECTED:
            msg = "当前已断开连接"
        elif new_state == NetworkManager.NM_DEVICE_STATE_PREPARE:
            msg = "准备连接到网络"
        elif new_state == NetworkManager.NM_DEVICE_STATE_CONFIG:
            msg = "正在连接到请求的网络..."
        elif new_state == NetworkManager.NM_DEVICE_STATE_NEED_AUTH:
            msg = "正在认证"
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CONFIG:
            msg = "正在请求IP地址和路由信息"
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CHECK:
            msg = "检查是否需要进一步操作"
        elif new_state == NetworkManager.NM_DEVICE_STATE_SECONDARIES:
            msg = "等待辅助连接（如VPN）"
        elif new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            msg = "已连接"
            self.connected = True
            # 异步获取连接的SSID
            def on_connected_ssid(ssid, error):
                if not error:
                    for cb in self._callbacks['connected']:
                        args = (cb, ssid, None)
                        GLib.idle_add(*args)
            self.get_connected_ssid(on_connected_ssid)
        elif new_state == NetworkManager.NM_DEVICE_STATE_DEACTIVATING:
            msg = "正在断开连接"
            self.connected = False
        elif new_state == NetworkManager.NM_DEVICE_STATE_FAILED:
            msg = "连接失败"
            self.connected = False
            self.callback("popup", msg)
        elif new_state == NetworkManager.NM_DEVICE_STATE_REASON_DEPENDENCY_FAILED:
            msg = "连接依赖失败"
        elif new_state == NetworkManager.NM_DEVICE_STATE_REASON_CARRIER:
            msg = ""
        else:
            logging.info(f"设备状态: {new_state}")
            
        if msg != "":
            self.callback("connecting_status", msg)

    def _add_ap(self, ap):
        """添加接入点"""
        ssid = ap.Ssid
        if ssid == "":
            ssid = _("隐藏网络") + f" {self.hidden_ssid_index}"
            self.hidden_ssid_index += 1
        self.ssid_by_path[ap.object_path] = ssid
        self.path_by_ssid[ssid] = ap.object_path
        self.visible_networks[ap.object_path] = ap
        return ssid

    def _remove_ap(self, path):
        """移除接入点"""
        ssid = self.ssid_by_path.pop(path, None)
        if ssid:
            self.path_by_ssid.pop(ssid, None)
        self.visible_networks.pop(path, None)

    def _get_connected_ap(self):
        """获取当前连接的接入点"""
        if self.wifi_dev:
            return self.wifi_dev.SpecificDevice().ActiveAccessPoint
        return None

    def _visible_networks_by_ssid(self):
        """按SSID获取可见网络"""
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
        """获取加密类型"""
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

    # =============== 回调系统 ===============
    
    def add_callback(self, name, callback):
        """添加回调函数"""
        if name in self._callbacks and callback not in self._callbacks[name]:
            self._callbacks[name].append(callback)

    def remove_callback(self, name, callback):
        """移除回调函数"""
        if name in self._callbacks and callback in self._callbacks[name]:
            self._callbacks[name].remove(callback)
            logging.debug(f"Removed callback for {name}")

    def callback(self, cb_type, msg):
        """触发回调"""
        if cb_type in self._callbacks:
            for cb in self._callbacks[cb_type]:
                GLib.idle_add(cb, msg)

    # =============== 析构函数 ===============
    
    def __del__(self):
        """析构函数，确保后台线程被正确关闭"""
        try:
            self.shutdown()
        except:
            pass  # 忽略析构过程中的任何异常
