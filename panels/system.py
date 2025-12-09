import logging
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("System")
        super().__init__(screen, title)
        self.current_row = 0
        self.mem_multiplier = None
        self.grid = Gtk.Grid(column_spacing=15, row_spacing=5)
        self.grid.set_margin_start(15)
        self.grid.set_margin_end(15)
        self.grid.set_margin_top(15)
        self.grid.set_margin_bottom(15)

        self.sysinfo = screen.printer.system_info
        if not self.sysinfo:
            logging.debug("Asking for info")
            self.sysinfo = screen.apiclient.send_request("machine/system_info")
            if 'result' in self.sysinfo and 'system_info' in self.sysinfo['result']:
                screen.printer.system_info = self.sysinfo['result']['system_info']
                self.sysinfo = self.sysinfo['result']['system_info']
        logging.debug(self.sysinfo)
        if self.sysinfo:
            self.content.add(self.create_layout())
        else:
            self.content.add(Gtk.Label(label=_("No info available"), vexpand=True))

    def create_layout(self):
        self.populate_info()
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)
        return scroll

    def set_mem_multiplier(self, data):
        memory_units = data.get("memory_units", "kB").lower()
        units_mapping = {
            "kb": 1024,
            "mb": 1024**2,
            "gb": 1024**3,
            "tb": 1024**4,
            "pb": 1024**5,
        }
        self.mem_multiplier = units_mapping.get(memory_units, 1)

    def add_label_to_grid(self, text, column, bold=False):
        if bold:
            text = f"<b>{text}</b>"
        label = Gtk.Label(label=text, use_markup=True, xalign=0, wrap=True)
        self.grid.attach(label, column, self.current_row, 2 - column, 1)
        self.current_row += 1

    def add_separator(self):
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.grid.attach(separator, 0, self.current_row, 2, 1)
        self.current_row += 1

    def get_machine_sn(self):
        """Read machine serial number from /etc/machine_sn file"""
        sn_file = "/etc/machine_sn"
        try:
            if os.path.exists(sn_file):
                with open(sn_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            return line
        except Exception as e:
            logging.error(f"Error reading machine SN: {e}")
        return None

    def populate_info(self):
        # Machine SN
        machine_sn = self.get_machine_sn()
        if machine_sn:
            self.add_label_to_grid("Machine SN", 0, bold=True)
            self.add_label_to_grid(machine_sn, 1)
            self.add_separator()

        # Python
        self.add_label_to_grid("Python", 0, bold=True)
        python_info = self.sysinfo.get("python", {})
        version = python_info.get("version_string", "").split()[0]
        self.add_label_to_grid(f"Version: {version}", 1)
        self.add_separator()

        # CPU
        self.add_label_to_grid("CPU Info", 0, bold=True)
        cpu_info = self.sysinfo.get("cpu_info", {})
        self.add_label_to_grid(f"CPU Count: {cpu_info.get('cpu_count', 'Unknown')}", 1)
        self.add_label_to_grid(f"Bits: {cpu_info.get('bits', 'Unknown')}", 1)
        self.add_label_to_grid(f"Processor: {cpu_info.get('processor', 'Unknown')}", 1)
        if not self.mem_multiplier:
            self.set_mem_multiplier(cpu_info)
        total_memory = int(cpu_info.get("total_memory", 0)) * self.mem_multiplier
        self.add_label_to_grid(f"Total Memory: {self.format_size(total_memory)}", 1)
        self.add_separator()

        # System
        self.add_label_to_grid("Distribution", 0, bold=True)
        os_info = self.sysinfo.get("distribution", {})
        self.add_label_to_grid(f"Name: {os_info.get('name', 'Unknown')}", 1)
        self.add_label_to_grid(f"ID: {os_info.get('id', 'Unknown')}", 1)
        self.add_label_to_grid(f"Version: {os_info.get('version', 'Unknown')}", 1)
        self.add_label_to_grid(f"Codename: {os_info.get('codename', 'Unknown')}", 1)
        self.add_label_to_grid(f"Kernel Version: {os_info.get('kernel_version', 'Unknown')}", 1)
        self.add_separator()

        # Network
        self.add_label_to_grid("Network", 0, bold=True)
        network_info = self.sysinfo.get("network", {})
        for interface, data in network_info.items():
            self.add_label_to_grid(interface, 0, bold=True)
            self.add_label_to_grid(f"MAC Address: {data.get('mac_address', 'Unknown')}", 1)
            for ip in data.get("ip_addresses", []):
                self.add_label_to_grid(f"IP Address: {ip.get('address', 'Unknown')}", 1)
        self.add_separator()

        # CAN Bus
        self.add_label_to_grid("CAN Bus", 0, bold=True)
        canbus_info = self.sysinfo.get("canbus", {})
        for interface, data in canbus_info.items():
            self.add_label_to_grid(interface, 0, bold=True)
            self.add_label_to_grid(f"TX Queue Length: {data.get('tx_queue_len', 'Unknown')}", 1)
            self.add_label_to_grid(f"Bitrate: {data.get('bitrate', 'Unknown')}", 1)
            self.add_label_to_grid(f"Driver: {data.get('driver', 'Unknown')}", 1)

