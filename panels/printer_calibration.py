# -*- coding: utf-8 -*-
import logging
import os
import gi
import math

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from datetime import datetime
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    cur_directory = "gcodes"
    dir_panels = {}
    filelist = {'calibration': {'directories': [], 'files': []}}
    
    def __init__(self, screen, title):
        super().__init__(screen, title)
        sortdir = self._config.get_main_config().get("print_sort_dir", "name_asc")
        sortdir = sortdir.split('_')
        if sortdir[0] not in ["name", "date"] or sortdir[1] not in ["asc", "desc"]:
            sortdir = ["name", "asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1]  # 0 for asc, 1 for desc
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date")
        }
        self.summary_dict = {
            'Acceleration_Tower' :  'Sample part to properly acceleration and jerk parameter. It’s important to do this step after calibrating the filament temperature to ensure consistent results.',
            'Bed_Level_Calibration' :  'This part is designed to help you check that you are correctly leveling you printer bed.',
            'Bi-Color_Calibration_Cube' :  'This model allow you to print a calibration cube in Bi-Color Mode',
            'Bridge_Test' :  'This is an elegant Bridge test.',
            'Calibrate_Cube' :  'This model is focused on testing dimensional accuracy, infill/perimeter overlap settings, material flow, and ringing/ghosting.',
            'Cube_bi-color' :  'This model allow you to print a calibration cube in Bi-Color Mode',
            'Dimensional_Accuracy_Test' :  'Test part to analyse the Dimensional Accuracy of your print.',
            'Extruder_Offset_Calibration_Part' :  'This model allow you to print a Calibration Multi Extruder part used to calibrate the X & Y Offset between 2 Extruder.',
            'Flow_Test' :  'If your flow rate is well calibrated, your top and bottom layers should look great.',
            'FlowTower_Test' :  'This part is used to print a tower, printed with a different flow percentage setting for each floor.',
            'Hole_Test' :  'Test part to analyse the best hole offset to use in the conception of your parts.',
            'Lithophane_Test' :  'This part is used to print a Lithophane test part.',
            'Max_Flow_Test' :  'Test the maximum printing speed of your extrusion system. ',
            'Multi-Flow_Test' :  'This test will creates 11 parts with a specific Flow rates already associated with the part.',
            'Overhang_Test' :  'Overhang Test',
            'PETG_TempTower' :  'This part is used to print a tower, printed with a different temperature setting for each floor.',
            'PLA_TempTower' :  'This part is used to print a tower, printed with a different temperature setting for each floor.',
            'Pressure_Adv_Tower' :  'Sample part and Postprocessing script to calibrate Linear/Pressure Advance.',
            'Retract_Test' :  'Test part used to test the retract settings. This model is different from the test part : Retract-Tower.',
            'Retract_Tower' :  'Sample part to properly calibrate the retraction. It’s important to do this step after calibrating the filament temperature to ensure consistent results.',
            'Support_Test' :  'Sample part to test support structures.',
            'Thin_Wall_Test' :  'The purpose of this item is to test your settings in the case of geometry with thin walls and irregular thickness.',
            'Tolerance_Test' :  'Test part to analyse the best offset to use in the design of your parts.',
            'XY_Calibration_Test' :  'This model is focused on testing dimensional accuracy.',
        }
        self.all_files = []
        self.pos = 0
        self.sort_icon = ["arrow-up", "arrow-down"]
        self.scroll = self._gtk.ScrolledWindow()
        self.files = {}
        self.directories = {}
        self.labels['directories'] = {}
        self.labels['files'] = {}
        self.source = ""
        self.time_24 = self._config.get_main_config().getboolean("24htime", True)
        logging.info(f"24h time is {self.time_24}")

        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)
        for i, (name, val) in enumerate(self.sort_items.items(), start=1):
            s = self._gtk.Button(None, val, f"color{i % 4}", .5, Gtk.PositionType.RIGHT, 1)
            s.get_style_context().add_class("buttons_slim")
            if name == self.sort_current[0]:
                s.set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]], self._gtk.img_scale * self.bts))
            s.connect("clicked", self.change_sort, name)
            self.labels[f'sort_{name}'] = s
            sbox.add(s)
        refresh = self._gtk.Button("refresh", style="color4", scale=self.bts)
        refresh.get_style_context().add_class("buttons_slim")
        refresh.connect('clicked', self._refresh_files)
        sbox.add(refresh)
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)

        pbox = Gtk.Box(spacing=0)
        pbox.set_hexpand(True)
        pbox.set_vexpand(False)
        self.labels['path'] = Gtk.Label()
        pbox.add(self.labels['path'])
        self.labels['path_box'] = pbox

        self.main = self._gtk.HomogeneousGrid()
        # self.main.set_vexpand(True)
        # self.main.pack_start(sbox, False, False, 0)
        # self.main.pack_start(pbox, False, False, 0)
        # self.main.pack_start(self.scroll, True, True, 0)

        self.dir_panels['calibration'] = Gtk.Grid()
        self.labels['back'] = self._gtk.Button("arrow-left", None, "color1", .66)
        self.labels['back'].connect("clicked", self.on_back)
        self.labels['next'] = self._gtk.Button("arrow-right", None, "color1", .66)
        self.labels['next'].connect("clicked", self.on_next)

        self.main.attach(self.labels['back'], 0, 0, 1, 3)
        self.main.attach(self.dir_panels['calibration'], 1, 0, 8, 3)
        self.main.attach(self.labels['next'], 9, 0, 1, 3)
        # self.change_dir(None, os.path.dirname(self.cur_directory))
        GLib.idle_add(self.reload_files)

        # self.scroll.add(self.dir_panels['calibration'])
        # self.content.add(self.dir_panels['calibration'])
        self.content.add(self.main)
        self._screen.files.add_file_callback(self._callback)
        self.showing_rename = False
        self.current_index = 0

    def on_back(self, widget):
        if self.current_index > 0:
            for child in self.dir_panels['calibration'].get_children():
                self.dir_panels['calibration'].remove(child)
            self.current_index -= 1
            self.reload_files()
        
    
    def on_next(self, widget):
        max_index = math.ceil(len(self.all_files) / 6) - 1
        if self.current_index < max_index:
            for child in self.dir_panels['calibration'].get_children():
                self.dir_panels['calibration'].remove(child)
            self.current_index += 1
            self.reload_files()


    def activate(self):
        if self.cur_directory != "gcodes":
            self.change_dir(None, "gcodes")
        self._refresh_files()

    def add_directory(self, directory, show=True):
        parent_dir = os.path.dirname(directory)
        if directory not in self.filelist:
            self.filelist[directory] = {'directories': [], 'files': [], 'modified': 0}
            self.filelist[parent_dir]['directories'].append(directory)

        if directory not in self.labels['directories']:
            self._create_row(directory)
        reverse = self.sort_current[1] != 0
        dirs = sorted(
            self.filelist[parent_dir]['directories'],
            reverse=reverse, key=lambda item: self.filelist[item]['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[parent_dir]['directories'], reverse=reverse)

        pos = dirs.index(directory)

        self.dir_panels[parent_dir].insert_row(pos)
        self.dir_panels[parent_dir].attach(self.directories[directory], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[parent_dir].show_all()

    def add_file(self, filepath, show=True):
        fileinfo = self.get_file_info(filepath)
        if fileinfo is None:
            return
        filename = os.path.basename(filepath)
        if filename.startswith("."):
            return
        # directory = os.path.dirname(os.path.join("gcodes", filepath))
        # d = directory.split(os.sep)
        # for i in range(1, len(d)):
        #     curdir = os.path.join(*d[:i])
        #     newdir = os.path.join(*d[:i + 1])
        #     if newdir not in self.filelist[curdir]['directories']:
        #         if d[i].startswith("."):
        #             return
        #         self.add_directory(newdir)

        # if filename not in self.filelist[directory]['files']:
        #     for i in range(1, len(d)):
        #         curdir = os.path.join(*d[:i + 1])
        #         if curdir != "gcodes" and fileinfo['modified'] > self.filelist[curdir]['modified']:
        #             self.filelist[curdir]['modified'] = fileinfo['modified']
        #             if self.time_24:
        #                 time = f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>'
        #             else:
        #                 time = f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %I:%M %p}</b>'
        #             info = _("Modified") + time
        #             info += "\n" + _("Size") + f':<b>  {self.format_size(fileinfo["size"])}</b>'
        #             self.labels['directories'][curdir]['info'].set_markup(info)
        #     self.filelist[directory]['files'].append(filename)

        if filepath not in self.files:
            self._create_row(filepath, filename)
        # reverse = self.sort_current[1] != 0
        # files = sorted(
        #     self.filelist[directory]['files'],
        #     reverse=reverse,
        #     key=lambda item: self._screen.files.get_file_info(f"{directory}/{item}"[7:])['modified']
        # ) if self.sort_current[0] == "date" else sorted(self.filelist[directory]['files'], reverse=reverse)

        # pos = files.index(filename)
        # pos += len(self.filelist[directory]['directories'])
        # logging.debug(f"pos = {pos}  bbbbbbbbbb")

        directory = 'calibration'
        col = math.floor(self.pos / 2)
        if self.pos % 2:
            self.dir_panels[directory].attach(self.files[filepath], 1, col, 1, 1)
            xx = 1
        else:
            self.dir_panels[directory].insert_row(col)
            self.dir_panels[directory].attach(self.files[filepath], 0, col, 1, 1)
        self.pos += 1

        if show is True:
            self.dir_panels[directory].show_all()
        return False

    def _create_row(self, fullpath, filename=None):
        name = Gtk.Label()
        name.get_style_context().add_class("print-filename")
        if filename:
            name.set_markup(f'<big><b>{os.path.splitext(filename)[0].replace("_", " ")}</b></big>')
        else:
            name.set_markup(f"<big><b>{os.path.split(fullpath)[-1]}</b></big>")
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.CHAR)

        info = Gtk.Label()
        info.set_hexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("print-info")

        delete = self._gtk.Button("delete", style="color1", scale=self.bts)
        delete.set_hexpand(False)
        rename = self._gtk.Button("files", style="color2", scale=self.bts)
        rename.set_hexpand(False)

        if filename:
            # action = self._gtk.Button("print", style="color3")
            # action.connect("clicked", self.confirm_print, fullpath)
            info.set_markup(self.get_file_info_str(fullpath))
            icon = Gtk.Button()
            icon.connect("clicked", self.confirm_print, fullpath)
            # delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")
            # rename.connect("clicked", self.show_rename, f"gcodes/{fullpath}")
            GLib.idle_add(self.image_load, fullpath)
        else:
            # action = self._gtk.Button("load", style="color3")
            # action.connect("clicked", self.change_dir, fullpath)
            icon = self._gtk.Button("folder")
            icon.connect("clicked", self.change_dir, fullpath)
            # delete.connect("clicked", self.confirm_delete_directory, fullpath)
            # rename.connect("clicked", self.show_rename, fullpath)
        icon.set_hexpand(False)
        # action.set_hexpand(False)
        # action.set_halign(Gtk.Align.END)

        # delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")

        row = Gtk.Grid()
        row.get_style_context().add_class("frame-item")
        # row.set_hexpand(True)
        row.set_vexpand(True)
        row.attach(icon, 0, 0, 1, 2)
        row.attach(name, 1, 0, 3, 1)
        row.attach(info, 1, 1, 1, 1)
        # row.attach(rename, 2, 1, 1, 1)
        # row.attach(delete, 3, 1, 1, 1)

        # if not filename or (filename and os.path.splitext(filename)[1] in [".gcode", ".g", ".gco"]):
        #     row.attach(action, 4, 0, 1, 2)

        if filename is not None:
            self.files[fullpath] = row
            self.labels['files'][fullpath] = {
                "icon": icon,
                "info": info,
                "name": name
            }
        else:
            self.directories[fullpath] = row
            self.labels['directories'][fullpath] = {
                "info": info,
                "name": name
            }
            self.dir_panels[fullpath] = Gtk.Grid()

    def image_load(self, filepath):
        pixbuf = self.get_image_from_file(filepath, small=True)
        if pixbuf is not None:
            self.labels['files'][filepath]['icon'].set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        else:
            self.labels['files'][filepath]['icon'].set_image(self._gtk.Image("file"))
        return False

    def confirm_delete_file(self, widget, filepath):
        logging.debug(f"Sending delete_file {filepath}")
        params = {"path": f"{filepath}"}
        self._screen._confirm_send_action(
            None,
            _("Delete File?") + "\n\n" + filepath,
            "server.files.delete_file",
            params
        )

    def confirm_delete_directory(self, widget, dirpath):
        logging.debug(f"Sending delete_directory {dirpath}")
        params = {"path": f"{dirpath}", "force": True}
        self._screen._confirm_send_action(
            None,
            _("Delete Directory?") + "\n\n" + dirpath,
            "server.files.delete_directory",
            params
        )

    def get_image_from_file(self, fullname, width = None, height = None, small = False):
        path = os.path.dirname(fullname)
        name = os.path.basename(fullname)
        root, extension = os.path.splitext(name)
        thumbPath = os.path.join(path, '.thumbs')
        thumb = os.path.join(thumbPath, root + "-128x128.png")
        if small: 
            thumb = os.path.join(thumbPath, root + "-32x32.png")

        width = width if width is not None else self._gtk.img_width
        height = height if height is not None else self._gtk.img_height
        if os.path.exists(thumb):
            return self._gtk.PixbufFromFile(thumb, width, height)
        return None
        
    def back(self):
        if self.showing_rename:
            self.hide_rename()
            return True
        if os.path.dirname(self.cur_directory):
            self.change_dir(None, os.path.dirname(self.cur_directory))
            return True
        return False

    def change_dir(self, widget, directory):
        if directory not in self.dir_panels:
            return
        logging.debug(f"Changing dir to {directory}")

        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.cur_directory = directory
        self.labels['path'].set_text(f"  {self.cur_directory[7:]}")

        self.scroll.add(self.dir_panels[directory])
        self.content.show_all()

    def change_sort(self, widget, key):
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logging.info(f"Changing sort_{oldkey} to {self.sort_items[self.sort_current[0]]}")
            self.labels[f'sort_{oldkey}'].set_image(None)
            self.labels[f'sort_{oldkey}'].show_all()
            self.sort_current = [key, 0]
        self.labels[f'sort_{key}'].set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]],
                                                             self._gtk.img_scale * self.bts))
        self.labels[f'sort_{key}'].show()
        GLib.idle_add(self.reload_files)

        self._config.set("main", "print_sort_dir", f'{key}_{"asc" if self.sort_current[1] == 0 else "desc"}')
        self._config.save_user_config_options()

    def confirm_print(self, widget, filename):

        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        basename = os.path.basename(filename)
        root = os.path.splitext(basename)[0]
        label = Gtk.Label()
        if root in self.summary_dict:
            label.set_markup(f"<b>{self.summary_dict[root]}</b>\n")
        else :
            name = root.replace("_", " ")
            label.set_markup(f"<b>{name}</b>\n")
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.add(label)

        pixbuf = self.get_image_from_file(filename, self._screen.width * .9, self._screen.height * .5)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 1)

        self._gtk.Dialog(_("Print") + f' {filename}', buttons, grid, self.confirm_print_response, os.path.join(".calibration", basename))

    def confirm_print_response(self, dialog, response_id, filename):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.info(f"Starting print: {filename}")
            self._screen._ws.klippy.print_start(filename)

    def delete_file(self, filename):
        directory = os.path.join("gcodes", os.path.dirname(filename)) if os.path.dirname(filename) else "gcodes"
        if directory not in self.filelist or os.path.basename(filename).startswith("."):
            return
        try:
            self.filelist[directory]["files"].pop(self.filelist[directory]["files"].index(os.path.basename(filename)))
        except Exception as e:
            logging.exception(e)
        dir_parts = directory.split(os.sep)
        i = len(dir_parts)
        while i > 1:
            cur_dir = os.path.join(*dir_parts[:i])
            if len(self.filelist[cur_dir]['directories']) > 0 or len(self.filelist[cur_dir]['files']) > 0:
                break
            parent_dir = os.path.dirname(cur_dir)

            if self.cur_directory == cur_dir:
                self.change_dir(None, parent_dir)

            del self.filelist[cur_dir]
            self.filelist[parent_dir]['directories'].pop(self.filelist[parent_dir]['directories'].index(cur_dir))
            self.dir_panels[parent_dir].remove(self.directories[cur_dir])
            del self.directories[cur_dir]
            del self.labels['directories'][cur_dir]
            self.dir_panels[parent_dir].show_all()
            i -= 1

        try:
            self.dir_panels[directory].remove(self.files[filename])
        except Exception as e:
            logging.exception(e)
        self.dir_panels[directory].show_all()
        self.files.pop(filename)

    def get_file_info_str(self, filename):

        fileinfo = self.get_file_info(filename)
        if fileinfo is None:
            return
        # info = _("Uploaded")
        # if self.time_24:
        #     info += f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>\n'
        # else:
        #     info += f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %I:%M %p}</b>\n'
        info = ""
        if "size" in fileinfo:
            info += _("Size") + f':  <b>{self.format_size(fileinfo["size"])}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Print Time") + f':  <b>{self.format_time(fileinfo["estimated_time"])}</b>'
        return info

    def get_file_info(self, file_path):
        fileinfo = {}
        file_size = os.path.getsize(file_path)
        fileinfo['size'] = file_size

        try:
            # Open the file for reading
            with open(file_path, "r") as file:
                # Perform operations on the file
                for line in file:
                    if line.startswith(';TIME:'):
                        fileinfo['estimated_time'] = int(line.strip().split(':')[1])
                        break
        except FileNotFoundError:
            print("The file does not exist.")
        except IOError as e:
            print(f"An error occurred: {e}")
        finally:
            # Close the file in the "finally" block to ensure it's always closed
            if 'file' in locals():
                file.close()        

        return fileinfo

    def reload_files(self, widget=None):
        self.filelist = {'calibration': {'directories': [], 'files': []}}
        for dirpan in self.dir_panels:
            for child in self.dir_panels[dirpan].get_children():
                self.dir_panels[dirpan].remove(child)

        # flist = sorted(self._screen.files.get_file_list(), key=lambda item: '/' in item)
        flist = sorted(self.get_file_list(), key=lambda item: '/' in item)
        self.all_files = flist
        start_index = self.current_index * 6
        end_index = min(start_index + 6, len(flist))
        logging.debug(f"start_index = {start_index}--------------")
        logging.debug(f"end_index = {end_index}--------------")
        # for file in flist:
        for i in range(start_index, end_index):
            logging.debug(f"file_path = {flist[i]}--------------")
            logging.debug(f"i = {i}--------------+")
            GLib.idle_add(self.add_file, flist[i])
        return False

    def update_file(self, filename):
        if filename not in self.labels['files']:
            logging.debug(f"Cannot update file, file not in labels: {filename}")
            return

        logging.info(f"Updating file {filename}")
        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        GLib.idle_add(self.image_load, filename)

    def _callback(self, newfiles, deletedfiles, updatedfiles=None):
        logging.debug(f"newfiles: {newfiles}")
        for file in newfiles:
            self.add_file(file)
        logging.debug(f"deletedfiles: {deletedfiles}")
        for file in deletedfiles:
            self.delete_file(file)
        if updatedfiles is not None:
            logging.debug(f"updatefiles: {updatedfiles}")
            for file in updatedfiles:
                self.update_file(file)
        return False

    def _refresh_files(self, widget=None):
        self._files.refresh_files()
        return False

    def show_rename(self, widget, fullpath):
        self.source = fullpath
        logging.info(self.source)

        for child in self.content.get_children():
            self.content.remove(child)

        if "rename_file" not in self.labels:
            self._create_rename_box(fullpath)
        self.content.add(self.labels['rename_file'])
        self.labels['new_name'].set_text(fullpath[7:])
        self.labels['new_name'].grab_focus_without_selecting()
        self.showing_rename = True

    def _create_rename_box(self, fullpath):
        lbl = self._gtk.Label(_("Rename/Move:"))
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(False)
        self.labels['new_name'] = Gtk.Entry()
        self.labels['new_name'].set_text(fullpath)
        self.labels['new_name'].set_hexpand(True)
        self.labels['new_name'].connect("activate", self.rename)
        self.labels['new_name'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("complete", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.rename)

        box = Gtk.Box()
        box.pack_start(self.labels['new_name'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['rename_file'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.labels['rename_file'].set_valign(Gtk.Align.CENTER)
        self.labels['rename_file'].set_hexpand(True)
        self.labels['rename_file'].set_vexpand(True)
        self.labels['rename_file'].pack_start(lbl, True, True, 5)
        self.labels['rename_file'].pack_start(box, True, True, 5)

    def hide_rename(self):
        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.main)
        self.content.show()
        self.showing_rename = False

    def rename(self, widget):
        params = {"source": self.source, "dest": f"gcodes/{self.labels['new_name'].get_text()}"}
        self._screen._send_action(
            widget,
            "server.files.move",
            params
        )
        self.back()
        GLib.timeout_add_seconds(2, self._refresh_files)


    def get_file_list(self):
        folder_path = None
        if "virtual_sdcard" in self._screen.printer.get_config_section_list():
            vsd = self._screen.printer.get_config_section("virtual_sdcard")
            if "path" in vsd:
                folder_path = os.path.expanduser(vsd['path'])  
        if folder_path is None:
            return      
        folder_path = os.path.join(folder_path, '.calibration')
        files = []
        for filename in os.listdir(folder_path):
            if filename.endswith(('.gcode', '.g', '.gco')):
                files.append(os.path.join(folder_path, filename))
        files.sort()
        return files