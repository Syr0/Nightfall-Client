#These are you tasks:
#1) when a player enter a room with a different zone then the current one, show that zone in the UI
#2) when a player moves up or down, ensure to clean the current map view and redraw the equivalent level of map. ensure there can be multiple levels in one zone. do not draw all of them on one map, but on several levels on one map.
#3) make these levels switchable by a +1 and -1 buttons on the top right inside the canvas. show the current level right beside it
# Print me whole functions to adapt / create. do not use placeholders or comments



#map.py
import os
import tkinter as tk
import configparser

from tkinter import ttk
from core.database import fetch_rooms, fetch_zones, fetch_exits_with_zone_info, fetch_room_name, fetch_room_position, \
    fetch_zone_name, fetch_min_max_levels

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
        self.current_room_id = None
        self.parent = parent
        self.pane = pane
        self.root = root
        self.displayed_zone_id = None
        self.current_level = 0
        self.levels_dict = {}

        self.load_config()

        self.this = tk.Canvas(self.parent, bg=self.background_color)
        self.this.pack(fill=tk.BOTH, expand=True)

        self.level_var = tk.StringVar()
        self.level_var.set(f"Level: {self.current_level}")

        self.initialize_level_ui()

        self.zone_dict = self.fetch_zone_dict()
        self.setup_bindings()
        self.initialize_ui()
        self.tooltips = {}


    def initialize_ui(self):
        zone_listbox_frame = ttk.Frame(self.pane, width=200)
        self.zone_listbox = tk.Listbox(zone_listbox_frame, height=10)
        for zone_name in sorted(self.zone_dict.keys()):
            self.zone_listbox.insert(tk.END, zone_name)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.zone_listbox.bind('<<ListboxSelect>>', self.on_zone_select)
        self.pane.add(zone_listbox_frame, weight=1)

    def set_parent(self, parent):
        self.parent = parent
        self.initialize_canvas()
        self.setup_bindings()

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

    def setup_bindings(self):
        self.this.bind("<MouseWheel>", self.on_mousewheel)
        self.this.bind("<Button-2>", self.on_middle_click)
        self.this.bind("<B2-Motion>", self.on_middle_move)

    def fetch_zone_dict(self):
        zones = fetch_zones()
        return {zone[1]: zone[0] for zone in zones}

    def draw_initial_map(self):
        default_zone_id = self.zone_dict.get(self.default_zone, None)
        if default_zone_id:
            self.display_zone(default_zone_id)

    def initialize_level_ui(self):
        self.level_frame = tk.Frame(self.this)
        self.level_up_button = tk.Button(self.level_frame, text="+1", command=self.level_up)
        self.level_down_button = tk.Button(self.level_frame, text="-1", command=self.level_down)
        self.level_label = tk.Label(self.level_frame, textvariable=self.level_var)

        self.level_up_button.pack(side=tk.LEFT)
        self.level_label.pack(side=tk.LEFT)
        self.level_down_button.pack(side=tk.LEFT)

        self.level_frame.pack(side=tk.TOP, fill=tk.X)

    def display_zone(self, zone_id):
        self.displayed_zone_id = zone_id
        self.this.delete("all")
        rooms = fetch_rooms(zone_id, self.current_level)
        exits_info = self.exits_with_zone_info([room[0] for room in rooms])
        self.draw_map(rooms, exits_info)
        self.update_level_ui()

    def update_level_ui(self):
        self.level_var.set(f"Level: {self.current_level}")
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
    def draw_exit_with_note(self, from_x, from_y, dir_x, dir_y, note):
        end_x, end_y = from_x + dir_x * 100, from_y + dir_y * 100
        self.this.create_line(from_x, from_y, end_x, end_y, fill=self.note_color, arrow=tk.LAST)
        self.this.create_text(end_x, end_y, text=note, fill=self.note_color, anchor="w")

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

        if count > 0:
            center_x, center_y = total_x / count, total_y / count
            self.this.create_oval(center_x - 20, center_y - 20, center_x + 20, center_y + 20, fill="yellow",
                                  outline="yellow", tags="center_of_mass")
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
        self.update_level_ui()

    def level_up(self):
        min_level, max_level = fetch_min_max_levels(self.displayed_zone_id)
        if self.current_level < max_level:
            self.current_level += 1
            self.display_zone(self.displayed_zone_id)

    def level_down(self):
        min_level, max_level = fetch_min_max_levels(self.displayed_zone_id)
        if self.current_level > min_level:
            self.current_level -= 1
            self.display_zone(self.displayed_zone_id)

    def place_zone_change_note(self, x, y, zone_name):
        note_text = f"To {zone_name}"
        self.this.create_text(x, y - 20, text=note_text, fill=self.note_color, font=('Helvetica', '10', 'bold'))

    def on_mousewheel(self, event):
        scale = 1.0
        x = self.this.canvasx(event.x)
        y = self.this.canvasy(event.y)

        factor = 1.001 ** event.delta
        self.this.scale(tk.ALL, x, y, factor, factor)
        scale *= factor
        self.adjust_scrollregion()

    def on_middle_click(self, event):
        self.this.scan_mark(event.x, event.y)

    def on_middle_move(self, event):
        self.this.scan_dragto(event.x, event.y, gain=1)

    def adjust_scrollregion(self):
        self.this.configure(scrollregion=self.this.bbox(tk.ALL))

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

    def set_current_room(self, room_id):
        if self.current_room_id is not None:
            self.unhighlight_room(self.current_room_id)
        self.current_room_id = room_id
        self.highlight_room(room_id)

    def on_zone_select(self, event):
        selection = self.zone_listbox.curselection()
        if selection:
            index = self.zone_listbox.curselection()[0]
            zone_name = self.zone_listbox.get(index)
            zone_id = self.zone_dict[zone_name]
            self.display_zone(zone_id)
            rooms = fetch_rooms(zone_id)
            exits_info = self.exits_with_zone_info([room[0] for room in rooms])

            self.this.delete("all")
            self.draw_map(rooms, exits_info)

    def select_default_zone(self,zone_listbox):
        try:
            index = list(self.zone_dict.keys()).index(self.default_zone)
            zone_listbox.select_set(index)
            zone_listbox.event_generate("<<ListboxSelect>>")
        except ValueError:
            print(f"Default zone '{self.default_zone}' not found.")

    def unhighlight_room(self, room_id):
        room_tag = f"{room_id}_room"
        self.this.itemconfig(room_tag, fill=self.room_color)

    def highlight_room(self, room_id):
        if hasattr(self, 'current_highlight'):
            self.unhighlight_room(self.current_highlight)
        self.current_highlight = room_id

        room_tag = f"{room_id}_room"
        self.this.itemconfig(room_tag, fill="#FF6EC7")

    def draw_zone_change_note(self, x, y, zone_name):
        note_text = f"To {zone_name}"
        self.this.create_text(x, y - 30, text=note_text, fill="blue", font=('Helvetica', '10', 'bold'))

