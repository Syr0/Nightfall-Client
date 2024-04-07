#map.py
import os
import tkinter as tk
import configparser

from tkinter import ttk
from core.database import fetch_rooms, fetch_zones, fetch_exits_with_zone_info, fetch_room_name, fetch_room_position, \
    fetch_zone_name
import map.camera
from gui.tooltip import ToolTip

def calculate_direction(from_pos, to_pos):
    dir_x = to_pos[0] - from_pos[0]
    dir_y = to_pos[1] - from_pos[1]
    mag = (dir_x**2 + dir_y**2) ** 0.5
    if mag == 0:
        return 0, 0
    return dir_x / mag, dir_y / mag

class MapViewer:
    def __init__(self, parent, pane, root):
        self.parent = parent
        self.pane = pane
        self.root = root
        self.current_room_id = None
        self.displayed_zone_id = None
        self.global_view_state = None
        self.current_level = 0
        self.scale = 1.0
        self.levels_dict = {}
        self.load_config()

        self.this = tk.Canvas(self.parent, bg=self.background_color)
        self.this.pack(fill=tk.BOTH, expand=True)
        self.camera = map.camera.Camera(self.this)

        self.level_var = tk.StringVar()
        self.level_var.set(f"Level: {self.current_level}")

        self.initialize_level_ui()

        self.zone_dict = self.fetch_zone_dict()
        self.initialize_ui()
        self.tooltips = {}

        self.global_view_state = self.capture_current_view()


    def initialize_ui(self):
        zone_listbox_frame = ttk.Frame(self.pane, width=200)
        self.zone_listbox = tk.Listbox(zone_listbox_frame, height=10)
        for zone_name in sorted(self.zone_dict.keys()):
            self.zone_listbox.insert(tk.END, zone_name)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.zone_listbox.bind('<<ListboxSelect>>', self.on_zone_select)
        self.pane.add(zone_listbox_frame, weight=1)

    def initialize_canvas(self):
        self.this = tk.Canvas(self.parent, bg=self.background_color)
        self.this.pack(fill=tk.BOTH, expand=True)

    def load_config(self):
        config_file_path = os.path.join(os.path.dirname(__file__), '../config/settings.ini')
        config = configparser.ConfigParser()
        config.read(config_file_path)

        self.player_marker_color = config['Visuals']['PlayerMarkerColor']
        self.background_color = config['Visuals']['BackgroundColor']
        self.room_distance = int(config['Visuals']['RoomDistance'])
        self.room_color = config['Visuals']['RoomColor']
        self.directed_graph = config.getboolean('Visuals', 'DirectedGraph')
        self.default_zone = config['General']['DefaultZone']
        self.note_color = config['Visuals'].get('ZoneLeavingColor', '#FFA500')

    def fetch_zone_dict(self):
        zones = fetch_zones()
        return {zone[1]: zone[0] for zone in zones}


    def initialize_level_ui(self):
        self.level_frame = tk.Frame(self.this)
        self.level_frame.pack(side=tk.TOP, fill=tk.X)

    def display_zone(self, zone_id, preserve_view=False, centered_room_id=None):
        self.displayed_zone_id = zone_id
        self.this.delete("all")
        rooms = fetch_rooms(zone_id, z=self.current_level)
        exits_info = self.exits_with_zone_info([room[0] for room in rooms])

        self.draw_map(rooms, exits_info)
        self.camera.apply_current_zoom()
        print(f"Display Zone: Zone ID = {zone_id}, Level = {self.current_level}, Camera Zoom = {self.camera.zoom}")

    def change_level(self, delta):
        self.camera.log_current_position()

        print(f"Changing Level: Current Level = {self.current_level}, Delta = {delta}")
        new_level = self.current_level + delta
        self.current_level = new_level
        self.display_zone(self.displayed_zone_id, preserve_view=True)
        print(f"Level Change Complete: New Level = {self.current_level}")

    def capture_current_view(self):
        bbox = self.this.bbox("all")
        if bbox is None:
            return (0, 0, 1.0, 0, 0, 100, 100)
        else:
            x1, y1, x2, y2 = bbox
            scroll_x = self.this.xview()[0]
            scroll_y = self.this.yview()[0]
            return (scroll_x, scroll_y, self.scale, x1, y1, x2, y2)

    def exits_with_zone_info(self, from_obj_ids):
        exits_info = fetch_exits_with_zone_info(from_obj_ids)
        detailed_exits_info = []
        for from_id, to_id, to_zone_id in exits_info:
            from_pos = fetch_room_position(from_id)
            to_pos = fetch_room_position(to_id)
            if from_pos and to_pos:
                dir_x, dir_y = calculate_direction(from_pos, to_pos)
                detailed_exits_info.append((from_id, to_id, to_zone_id, dir_x, dir_y))
            else:
                print(f"Position not found for from_id: {from_id} or to_id: {to_id}")
        return detailed_exits_info

    def create_rounded_rectangle(self, x1, y1, x2, y2, radius=25, **kwargs):
        return self.this.create_polygon([x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y1+radius, x1, y1], **kwargs, smooth=True)

    def draw_room_with_shadow(self, x, y, room_id, room_name):
        box_size = 20
        shadow_offset = 6
        tag_id = str(room_id)

        shadow_tag = f"{tag_id}_shadow"
        self.create_rounded_rectangle(x - box_size + shadow_offset, y - box_size + shadow_offset,
                                      x + box_size + shadow_offset, y + box_size + shadow_offset, radius=10,
                                      fill="gray20", tags=(shadow_tag,))
        room_tag = f"{tag_id}_room"
        self.create_rounded_rectangle(x - box_size, y - box_size, x + box_size, y + box_size, radius=10,
                                      fill=self.room_color, tags=(room_tag,))
        self.this.tag_bind(room_tag, "<Enter>", lambda e, id=room_id: self.show_room_name(e, id, e.x, e.y))
        self.this.tag_bind(room_tag, "<Leave>", self.hide_room_name)

    def draw_exits(self, rooms, exits):
        bidirectional = set()
        exits_tuples = {(exit[0], exit[1]) for exit in exits}

        for from_id, to_id in exits_tuples:
            if (to_id, from_id) in exits_tuples:
                bidirectional.add((from_id, to_id))

        for from_id, to_id in exits_tuples:
            from_pos = next((room[1:3] for room in rooms if room[0] == from_id), None)
            to_pos = next((room[1:3] for room in rooms if room[0] == to_id), None)
            if from_pos and to_pos:
                if (from_id, to_id) in bidirectional:
                    self.this.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], fill=self.room_color)
                else:
                    self.this.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], arrow=tk.LAST,fill=self.room_color)
    def draw_map(self, rooms, exits_info):
        total_x, total_y, count = 0, 0, 0
        room_size = 20
        shadow_offset = 6
        extra_padding = 10
        offset = room_size + shadow_offset + extra_padding
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

        for room_id, x, y, z, name in rooms:
            if z != self.current_level:
                continue

            self.draw_room_with_shadow(x, y, str(room_id), name)
            min_x, min_y = min(min_x, x - offset), min(min_y, y - offset)
            max_x, max_y = max(max_x, x + offset), max(max_y, y + offset)
            total_x += x
            total_y += y
            count += 1

        self.drawn_bounds = (min_x, min_y, max_x, max_y)
        self.draw_exits(rooms, [exit[:2] for exit in exits_info])

        for exit_info in exits_info:
            from_id, to_id, to_zone_id, _, _ = exit_info
            if to_zone_id != self.displayed_zone_id:
                to_zone_name = fetch_zone_name(to_zone_id)
                from_room_position = fetch_room_position(from_id)
                if from_room_position:
                    x, y = from_room_position
                    self.place_zone_change_note(x, y, to_zone_name)

    def place_zone_change_note(self, x, y, zone_name):
        note_text = f"To {zone_name}"
        self.this.create_text(x, y - 20, text=note_text, fill=self.note_color, font=('Helvetica', '10', 'bold'))


    def show_room_name(self, event, room_id, event_x, event_y):
        room_name = fetch_room_name(room_id)
        if room_id not in self.tooltips:
            self.tooltips[room_id] = ToolTip(self.this)
        self.tooltips[room_id].show_tip(room_name, event_x, event_y)
        self.this.bind("<Motion>", lambda e: self.update_tooltip_position(e, room_id, e.x, e.y))

    def update_tooltip_position(self, event, room_id, event_x, event_y):
        if room_id in self.tooltips:
            self.tooltips[room_id].show_tip(fetch_room_name(room_id), event_x, event_y)

    def hide_room_name(self, event):
        for tooltip in self.tooltips.values():
            tooltip.hide_tip()
        self.this.unbind("<Motion>")

    def on_zone_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            zone_name = event.widget.get(index)
            zone_id = self.zone_dict[zone_name]
            self.current_level = 0
            self.display_zone(zone_id)

    def unhighlight_room(self, room_id):
        room_tag = f"{room_id}_room"
        self.this.itemconfig(room_tag, fill=self.room_color)

    def highlight_room(self, room_id):
        if hasattr(self, 'current_highlight'):
            self.unhighlight_room(self.current_highlight)
        self.current_highlight = room_id

        room_tag = f"{room_id}_room"
        self.this.itemconfig(room_tag, fill="#FF6EC7")
