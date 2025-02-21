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
            if 'calibrate' in key:
                logging.info(f"Found calibration menu item: {key}")
                if key == 'calibrate zoffset':
                    logging.info("Creating Z Calibrate button with number 1")
                    b = Gtk.Button()
                    b.get_style_context().add_class(style or f"color{i % 4 + 1}")
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    box.set_halign(Gtk.Align.CENTER)
                    box.set_valign(Gtk.Align.CENTER)
                    
                    if icon:
                        img = self._gtk.Image(icon, self._gtk.img_scale * 1.5, self._gtk.img_scale * 1.5)
                        img.set_valign(Gtk.Align.CENTER)
                        img.set_halign(Gtk.Align.CENTER)
                        box.pack_start(img, True, True, 0)
                    
                    title = Gtk.Label()
                    title.set_markup(f'<span size="large">{name}</span>')
                    title.set_line_wrap(True)
                    title.set_justify(Gtk.Justification.CENTER)
                    title.set_halign(Gtk.Align.CENTER)
                    title.set_valign(Gtk.Align.CENTER)
                    box.pack_start(title, True, True, 0)
                    
                    number = Gtk.Label()
                    number.set_markup('<span size="20000" foreground="#FFD700">1</span>')
                    number.set_halign(Gtk.Align.CENTER)
                    number.set_valign(Gtk.Align.CENTER)
                    box.pack_start(number, True, True, 0)
                    
                    b.add(box)
                    box.show_all()
                    logging.info("Z Calibrate button created")
                elif key == 'calibrate bedmesh':
                    logging.info("Creating Leveling button with number 2")
                    b = Gtk.Button()
                    b.get_style_context().add_class(style or f"color{i % 4 + 1}")
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    box.set_halign(Gtk.Align.CENTER)
                    box.set_valign(Gtk.Align.CENTER)
                    
                    if icon:
                        img = self._gtk.Image(icon, self._gtk.img_scale * 1.5, self._gtk.img_scale * 1.5)
                        img.set_valign(Gtk.Align.CENTER)
                        img.set_halign(Gtk.Align.CENTER)
                        box.pack_start(img, True, True, 0)
                    
                    title = Gtk.Label()
                    title.set_markup(f'<span size="large">{name}</span>')
                    title.set_line_wrap(True)
                    title.set_justify(Gtk.Justification.CENTER)
                    title.set_halign(Gtk.Align.CENTER)
                    title.set_valign(Gtk.Align.CENTER)
                    box.pack_start(title, True, True, 0)
                    
                    number = Gtk.Label()
                    number.set_markup('<span size="20000" foreground="#FFD700">2</span>')
                    number.set_halign(Gtk.Align.CENTER)
                    number.set_valign(Gtk.Align.CENTER)
                    box.pack_start(number, True, True, 0)
                    
                    b.add(box)
                    box.show_all()
                    logging.info("Leveling button created")
                elif key == 'calibrate extruder_xyoffset':
                    logging.info("Creating XY Offset button with number 3")
                    b = Gtk.Button()
                    b.get_style_context().add_class(style or f"color{i % 4 + 1}")
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    box.set_halign(Gtk.Align.CENTER)
                    box.set_valign(Gtk.Align.CENTER)
                    
                    if icon:
                        img = self._gtk.Image(icon, self._gtk.img_scale * 1.5, self._gtk.img_scale * 1.5)
                        img.set_valign(Gtk.Align.CENTER)
                        img.set_halign(Gtk.Align.CENTER)
                        box.pack_start(img, True, True, 0)
                    
                    title = Gtk.Label()
                    title.set_markup(f'<span size="large">{name}</span>')
                    title.set_line_wrap(True)
                    title.set_justify(Gtk.Justification.CENTER)
                    title.set_halign(Gtk.Align.CENTER)
                    title.set_valign(Gtk.Align.CENTER)
                    box.pack_start(title, True, True, 0)
                    
                    number = Gtk.Label()
                    number.set_markup('<span size="20000" foreground="#FFD700">3</span>')
                    number.set_halign(Gtk.Align.CENTER)
                    number.set_valign(Gtk.Align.CENTER)
                    box.pack_start(number, True, True, 0)
                    
                    b.add(box)
                    box.show_all()
                    logging.info("XY Offset button created")
                elif key == 'calibrate dual_nozzle_height_calibration':
                    logging.info("Creating Z Height Diff button with number 4")
                    b = Gtk.Button()
                    b.get_style_context().add_class(style or f"color{i % 4 + 1}")
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    box.set_halign(Gtk.Align.CENTER)
                    box.set_valign(Gtk.Align.CENTER)
                    
                    if icon:
                        img = self._gtk.Image(icon, self._gtk.img_scale * 1.5, self._gtk.img_scale * 1.5)
                        img.set_valign(Gtk.Align.CENTER)
                        img.set_halign(Gtk.Align.CENTER)
                        box.pack_start(img, True, True, 0)
                    
                    title = Gtk.Label()
                    title.set_markup(f'<span size="large">{name}</span>')
                    title.set_line_wrap(True)
                    title.set_justify(Gtk.Justification.CENTER)
                    title.set_halign(Gtk.Align.CENTER)
                    title.set_valign(Gtk.Align.CENTER)
                    box.pack_start(title, True, True, 0)
                    
                    number = Gtk.Label()
                    number.set_markup('<span size="20000" foreground="#FFD700">4</span>')
                    number.set_halign(Gtk.Align.CENTER)
                    number.set_valign(Gtk.Align.CENTER)
                    box.pack_start(number, True, True, 0)
                    
                    b.add(box)
                    box.show_all()
                    logging.info("Z Height Diff button created")
                else:
                    logging.info(f"Creating regular button for {key}")
                    b = self._gtk.Button(icon, name, style or f"color{i % 4 + 1}", scale=scale)
                    label = b.get_child().get_children()[1] if b.get_child() and isinstance(b.get_child(), Gtk.Box) else None
                    if label and isinstance(label, Gtk.Label):
                        label.set_line_wrap(True)
                        label.set_justify(Gtk.Justification.CENTER)
                        label.set_lines(2)
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