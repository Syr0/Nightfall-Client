#map.py
import os
import tkinter as tk
import configparser

from tkinter import ttk
from core.database import fetch_rooms, fetch_zones, fetch_exits, fetch_room_name, fetch_room_position

from gui.tooltip import ToolTip

class MapViewer:
    def __init__(self, parent, pane, root):
        self.parent = parent
        self.pane = pane
        self.root = root
        self.load_config()

        self.this = tk.Canvas(self.parent, bg=self.background_color)
        self.this.pack(fill=tk.BOTH, expand=True)

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

    def display_zone(self, zone_id):
        rooms = fetch_rooms(zone_id)
        exits = fetch_exits([room[0] for room in rooms])
        self.draw_map(rooms, exits)
        self.displayed_zone_id = zone_id

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

        self.this.tag_bind(room_tag, "<Enter>", lambda e, id=room_id: self.show_room_name(e, id))
        self.this.tag_bind(room_tag, "<Leave>", self.hide_room_name)

    def draw_exits(self, rooms, exits):
        bidirectional = set()
        exits_tuples = {(exit.FromID, exit.ToID) for exit in exits}

        for exit in exits_tuples:
            from_id, to_id = exit
            if (to_id, from_id) in exits_tuples:
                bidirectional.add(exit)

        for exit in exits_tuples:
            from_id, to_id = exit
            from_pos = next((room[1:3] for room in rooms if room[0] == from_id), None)
            to_pos = next((room[1:3] for room in rooms if room[0] == to_id), None)
            if from_pos and to_pos:
                if exit in bidirectional:
                    self.this.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], fill=self.room_color)
                else:
                    self.this.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], arrow=tk.LAST, fill=self.room_color)

    def draw_map(self, rooms, exits):
        total_x, total_y, count = 0, 0, 0
        count = 0
        room_size = 20
        shadow_offset = 6
        extra_padding = 10

        offset = room_size + shadow_offset + extra_padding
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

        for room_id, x, y, name in rooms:
            self.draw_room_with_shadow(x, y, str(room_id), name)
            min_x, min_y = min(min_x, x - offset), min(min_y, y - offset)
            max_x, max_y = max(max_x, x + offset), max(max_y, y + offset)
            total_x += x
            total_y += y
            count += 1

        if count > 0:
            self.center_of_mass = (total_x / count, total_y / count)

        center_x, center_y = self.center_of_mass
        self.this.create_oval(center_x - 20, center_y - 20, center_x + 20, center_y + 20, fill="yellow",
                              outline="yellow",
                              tags="center_of_mass")
        self.drawn_bounds = (min_x, min_y, max_x, max_y)
        self.draw_exits(rooms, exits)

    def set_player_position(self, room_id):
        room_tag = f"{room_id}_room"
        self.this.itemconfig(room_tag, outline=self.player_marker_color)

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

    def show_room_name(self, event, room_id):
        room_name = fetch_room_name(room_id)
        if room_id not in self.tooltips:
            self.tooltips[room_id] = ToolTip(self.this)
        self.tooltips[room_id].show_tip(room_name)
        self.this.bind("<Motion>", lambda e: self.update_tooltip_position(e, room_id))

    def update_tooltip_position(self, event, room_id):
        if room_id in self.tooltips:
            self.tooltips[room_id].show_tip(fetch_room_name(room_id))

    def hide_room_name(self, event):
        for tooltip in self.tooltips.values():
            tooltip.hide_tip()
        self.this.unbind("<Motion>")

    def set_current_room(self, room_id):
        if self.current_room_id is not None:
            self.map_viewer.unhighlight_room(self.current_room_id)
        self.current_room_id = room_id
        self.map_viewer.highlight_room(room_id)
        room_position = fetch_room_position(room_id)
        if room_position:
            self.map_viewer.root.after(0, lambda: self.map_viewer.focus_point(*room_position))

    def focus_point(self,x, y):
        self.this.update_idletasks()
        this_width = self.this.winfo_width()
        this_height = self.this.winfo_height()

        scrollregion = self.this.bbox("all")
        if scrollregion is None:
            print("No scroll region set.")
            return

        scrollregion_width = scrollregion[2] - scrollregion[0]
        scrollregion_height = scrollregion[3] - scrollregion[1]

        center_fraction_x = (x - scrollregion[0]) / scrollregion_width
        center_fraction_y = (y - scrollregion[1]) / scrollregion_height

        half_view_fraction_x = this_width / (2 * scrollregion_width)
        half_view_fraction_y = this_height / (2 * scrollregion_height)

        final_scroll_x = center_fraction_x - half_view_fraction_x
        final_scroll_y = center_fraction_y - half_view_fraction_y
        final_scroll_x = max(0, min(final_scroll_x, 1))
        final_scroll_y = max(0, min(final_scroll_y, 1))

        self.this.xview_moveto(final_scroll_x)
        self.this.yview_moveto(final_scroll_y)

    def center_and_zoom_out_map(self):
        if not self.drawn_bounds:
            return
        x, y = self.center_of_mass
        self.focus_point(x, y)

    def on_zone_select(self,event):
        if not self.zone_listbox.curselection():
            return
        index = self.zone_listbox.curselection()[0]
        zone_name = self.zone_listbox.get(index)
        zone_id = self.zone_dict[zone_name]
        rooms = fetch_rooms(zone_id)
        exits = fetch_exits([room[0] for room in rooms])

        if not rooms:
            print("No rooms found for this zone.")
            return

        self.this.delete("all")
        self.draw_map(rooms, exits)
        self.center_and_zoom_out_map()

    def show_room_name(self, event, room_id):
        room_name = fetch_room_name(room_id)
        if room_id not in self.tooltips:
            self.tooltips[room_id] = ToolTip(self.this)
        self.tooltips[room_id].show_tip(room_name, event.x, event.y)

    def hide_room_name(self, event):
        for tooltip in self.tooltips.values():
            tooltip.hide_tip()

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
