import logging
import json
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jinja2 import Template
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title, items=None):
        super().__init__(screen, title)
        self.items = items
        self.j2_data = self._printer.get_printer_status_data()
        self.create_menu_items()
        self.grid = self._gtk.HomogeneousGrid()
        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    def activate(self):
        self.j2_data = self._printer.get_printer_status_data()
        self.add_content()

    def add_content(self):
        for child in self.scroll.get_children():
            self.scroll.remove(child)
        if self._screen.vertical_mode:
            self.scroll.add(self.arrangeMenuItems(self.items, 3))
        else:
            self.scroll.add(self.arrangeMenuItems(self.items, 4))
        if not self.content.get_children():
            self.content.add(self.scroll)

    def arrangeMenuItems(self, items, columns, expand_last=False):
        for child in self.grid.get_children():
            self.grid.remove(child)
        length = len(items)
        i = 0
        for item in items:
            key = list(item)[0]
            if not self.evaluate_enable(item[key]['enable']):
                logging.debug(f"X > {key}")
                continue

            if columns == 4:
                if length <= 4:
                    # Arrange 2 x 2
                    columns = 2
                elif 4 < length <= 6:
                    # Arrange 3 x 2
                    columns = 3

            col = i % columns
            row = int(i / columns)

            width = height = 1
            if expand_last is True and i + 1 == length and length % 2 == 1:
                width = 2

            self.grid.attach(self.labels[key], col, row, width, height)
            i += 1
        return self.grid

    def create_menu_items(self):
        count = sum(bool(self.evaluate_enable(i[next(iter(i))]['enable'])) for i in self.items)
        scale = 1.1 if 12 < count <= 16 else None  # hack to fit a 4th row
        for i in range(len(self.items)):
            key = list(self.items[i])[0]
            item = self.items[i][key]

            name = self._screen.env.from_string(item['name']).render(self.j2_data)
            icon = self._screen.env.from_string(item['icon']).render(self.j2_data) if item['icon'] else None
            style = self._screen.env.from_string(item['style']).render(self.j2_data) if item['style'] else None

            logging.info(f"Processing menu item - Key: {key}, Name: {name}")

            # Add numbers for calibration menu items
            if '__main calibrate' in key:
                logging.info(f"Found calibration menu item: {key}")
                if 'zoffset' in key and 'Z Calibrate' in name:
                    logging.info("Creating Z Calibrate button with number 1")
                    b = self._gtk.Button(icon, None, style or f"color{i % 4 + 1}", scale=scale)
                    label = Gtk.Label()
                    markup_text = f"{name}\n<span size='small'>1</span>"
                    logging.info(f"Setting markup: {markup_text}")
                    label.set_markup(markup_text)
                    label.set_line_wrap(True)
                    label.set_justify(Gtk.Justification.CENTER)
                    label.set_lines(2)
                    b.set_child(label)
                    logging.info("Z Calibrate button created")
                elif 'bedmesh' in key and 'Leveling' in name:
                    logging.info("Creating Leveling button with number 2")
                    b = self._gtk.Button(icon, None, style or f"color{i % 4 + 1}", scale=scale)
                    label = Gtk.Label()
                    markup_text = f"{name}\n<span size='small'>2</span>"
                    logging.info(f"Setting markup: {markup_text}")
                    label.set_markup(markup_text)
                    label.set_line_wrap(True)
                    label.set_justify(Gtk.Justification.CENTER)
                    label.set_lines(2)
                    b.set_child(label)
                    logging.info("Leveling button created")
                elif 'extruder_xyoffset' in key and 'XY Offset' in name:
                    logging.info("Creating XY Offset button with number 3")
                    b = self._gtk.Button(icon, None, style or f"color{i % 4 + 1}", scale=scale)
                    label = Gtk.Label()
                    markup_text = f"{name}\n<span size='small'>3</span>"
                    logging.info(f"Setting markup: {markup_text}")
                    label.set_markup(markup_text)
                    label.set_line_wrap(True)
                    label.set_justify(Gtk.Justification.CENTER)
                    label.set_lines(2)
                    b.set_child(label)
                    logging.info("XY Offset button created")
                elif 'dual_nozzle_height_calibration' in key and 'Z Height Diff' in name:
                    logging.info("Creating Z Height Diff button with number 4")
                    b = self._gtk.Button(icon, None, style or f"color{i % 4 + 1}", scale=scale)
                    label = Gtk.Label()
                    markup_text = f"{name}\n<span size='small'>4</span>"
                    logging.info(f"Setting markup: {markup_text}")
                    label.set_markup(markup_text)
                    label.set_line_wrap(True)
                    label.set_justify(Gtk.Justification.CENTER)
                    label.set_lines(2)
                    b.set_child(label)
                    logging.info("Z Height Diff button created")
            else:
                b = self._gtk.Button(icon, name, style or f"color{i % 4 + 1}", scale=scale)
                label = b.get_child().get_children()[1] if b.get_child() and isinstance(b.get_child(), Gtk.Box) else None
                if label and isinstance(label, Gtk.Label):
                    label.set_line_wrap(True)
                    label.set_justify(Gtk.Justification.CENTER)
                    label.set_lines(2)

            if item['panel']:
                b.connect("clicked", self.menu_item_clicked, item)
            elif item['method']:
                params = {}

                if item['params'] is not False:
                    try:
                        p = self._screen.env.from_string(item['params']).render(self.j2_data)
                        params = json.loads(p)
                    except Exception as e:
                        logging.exception(f"Unable to parse parameters for [{name}]:\n{e}")
                        params = {}

                if item['confirm'] is not None:
                    b.connect("clicked", self._screen._confirm_send_action, item['confirm'], item['method'], params)
                else:
                    b.connect("clicked", self._screen._send_action, item['method'], params)
            else:
                b.connect("clicked", self._screen._go_to_submenu, key)
            self.labels[key] = b

    def evaluate_enable(self, enable):
        if enable == "{{ moonraker_connected }}":
            logging.info(f"moonraker connected {self._screen._ws.connected}")
            return self._screen._ws.connected
        try:
            j2_temp = Template(enable, autoescape=True)
            result = j2_temp.render(self.j2_data)
            return result == 'True'
        except Exception as e:
            logging.debug(f"Error evaluating enable statement: {enable}\n{e}")
            return False