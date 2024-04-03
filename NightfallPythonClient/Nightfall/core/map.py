#map.py
import os
import tkinter as tk
import configparser

from tkinter import ttk
from core.database import fetch_rooms, fetch_zones, fetch_exits, fetch_room_name

prev_x = None
prev_y = None
tooltip = None
drawn_bounds = None
center_of_mass = (0, 0)

config_file_path = os.path.join(os.path.dirname(__file__), '../config/settings.ini')

config = configparser.ConfigParser()
config.read(config_file_path)

ROOM_DISTANCE = int(config['Visuals']['RoomDistance'])
BACKGROUND_COLOR = config['Visuals']['BackgroundColor']
ROOM_COLOR = config['Visuals']['RoomColor']
DIRECTED_GRAPH = config['Visuals']['DirectedGraph'] == 'True'
DEFAULT_ZONE = config['General']['DefaultZone']

def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius=25, **kwargs):
    points = [
        x1+radius, y1,
        x1+radius, y1, x2-radius, y1,
        x2-radius, y1, x2, y1,
        x2, y1, x2, y1+radius,
        x2, y1+radius, x2, y2-radius,
        x2, y2-radius, x2, y2,
        x2, y2, x2-radius, y2,
        x2-radius, y2, x1+radius, y2,
        x1+radius, y2, x1, y2,
        x1, y2, x1, y2-radius,
        x1, y2-radius, x1, y1+radius,
        x1, y1+radius, x1, y1,
    ]
    return canvas.create_polygon(points, **kwargs, smooth=True)

def draw_room_with_shadow(canvas, x, y, room_id, room_name):
    shadow_offset = 6
    box_size = 20
    create_rounded_rectangle(canvas, x-box_size+shadow_offset, y-box_size+shadow_offset, x+box_size+shadow_offset, y+box_size+shadow_offset, radius=10, fill="gray20", tags=(room_id, "shadow"))
    room = create_rounded_rectangle(canvas, x-box_size, y-box_size, x+box_size, y+box_size, radius=10, fill=ROOM_COLOR, tags=(room_id, "room"))
    canvas.tag_bind(room, "<Enter>", lambda e, name=room_name: show_room_name(e, name))
    canvas.tag_bind(room, "<Leave>", hide_room_name)

def draw_exits(rooms, exits):
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
                canvas.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], fill=ROOM_COLOR)
            else:
                canvas.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], arrow=tk.LAST, fill=ROOM_COLOR)

def draw_map(rooms, exits):
    global drawn_bounds, center_of_mass
    total_x, total_y, count = 0, 0, 0
    count = 0
    room_size = 20
    shadow_offset = 6
    extra_padding = 10

    offset = room_size + shadow_offset + extra_padding
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

    for room_id, x, y, name in rooms:
        draw_room_with_shadow(canvas, x, y, str(room_id), name)
        min_x, min_y = min(min_x, x - offset), min(min_y, y - offset)
        max_x, max_y = max(max_x, x + offset), max(max_y, y + offset)
        total_x += x
        total_y += y
        count += 1

    if count > 0:
        center_of_mass = (total_x / count, total_y / count)

    center_x, center_y = center_of_mass
    canvas.create_oval(center_x - 5, center_y - 5, center_x + 5, center_y + 5, fill="yellow", outline="yellow",
                       tags="center_of_mass")

    drawn_bounds = (min_x, min_y, max_x, max_y)
    draw_exits(rooms, exits)


def on_mousewheel(event):
    scale = 1.0
    x = canvas.canvasx(event.x)
    y = canvas.canvasy(event.y)
    factor = 1.001 ** event.delta
    canvas.scale(tk.ALL, x, y, factor, factor)
    scale *= factor
    adjust_scrollregion()

def on_middle_click(event):
    canvas.scan_mark(event.x, event.y)

def on_middle_move(event):
    canvas.scan_dragto(event.x, event.y, gain=1)

def adjust_scrollregion():
    canvas.configure(scrollregion=canvas.bbox(tk.ALL))

def focus_point(x, y):
    canvas.update_idletasks()
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()

    scale_x = canvas_width / (drawn_bounds[2] - drawn_bounds[0])
    scale_y = canvas_height / (drawn_bounds[3] - drawn_bounds[1])
    scale = min(scale_x, scale_y, 1) * 0.8

    scaled_x = (x - drawn_bounds[0]) * scale
    scaled_y = (y - drawn_bounds[1]) * scale

    move_x = max(0, scaled_x - canvas_width / 2)
    move_y = max(0, scaled_y - canvas_height / 2)

    canvas.xview_moveto(move_x / (canvas_width * scale))
    canvas.yview_moveto(move_y / (canvas_height * scale))
    adjust_scrollregion()

def center_and_zoom_out_map():
    global drawn_bounds, center_of_mass
    if not drawn_bounds:
        return

    canvas.update_idletasks()
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()

    min_x, min_y, max_x, max_y = drawn_bounds
    scale_x = canvas_width / (max_x - min_x)
    scale_y = canvas_height / (max_y - min_y)
    scale = min(scale_x, scale_y, 1)

    canvas.scale("all", 0, 0, scale, scale)

    scaled_center_x = center_of_mass[0] * scale
    scaled_center_y = center_of_mass[1] * scale

    canvas.xview_moveto(max(0, (scaled_center_x - canvas_width / 2) / (canvas_width * scale)))
    canvas.yview_moveto(max(0, (scaled_center_y - canvas_height / 2) / (canvas_height * scale)))
    adjust_scrollregion()


def on_zone_select(event):
    if not event.widget.curselection():
        return
    index = event.widget.curselection()[0]
    zone_name = event.widget.get(index)
    zone_id = zone_dict[zone_name]
    rooms = fetch_rooms(zone_id)
    exits = fetch_exits([room[0] for room in rooms])

    if not rooms:
        print("No rooms found for this zone.")
        return

    canvas.delete("all")
    draw_map(rooms, exits)
    center_and_zoom_out_map()

def show_room_name(event, room_id):
    global tooltip
    room_name = fetch_room_name(room_id)
    if tooltip:
        canvas.delete(tooltip)
    x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
    tooltip = canvas.create_text(x+20, y, text=room_name, fill="black", font=("Arial", "10", "bold"))

def hide_room_name(event):
    global tooltip
    if tooltip:
        canvas.delete(tooltip)
        tooltip = None

def select_default_zone(zone_listbox):
    try:
        index = list(zone_dict.keys()).index(DEFAULT_ZONE)
        zone_listbox.select_set(index)
        zone_listbox.event_generate("<<ListboxSelect>>")
    except ValueError:
        print(f"Default zone '{DEFAULT_ZONE}' not found.")

def create_zone_listbox():
    zones = sorted(fetch_zones(), key=lambda x: x[1])
    global zone_dict
    zone_dict = {zone[1]: zone[0] for zone in zones}

    zone_listbox = tk.Listbox(left_panel, height=len(zones))
    for zone_name, _ in zone_dict.items():
        zone_listbox.insert(tk.END, zone_name)
    zone_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
    zone_listbox.bind('<<ListboxSelect>>', on_zone_select)
    return zone_listbox

root = tk.Tk()
root.title("Map Viewer")
root.geometry("1200x600")

pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
pane.pack(fill=tk.BOTH, expand=True)

left_panel = ttk.Frame(pane, width=120)
right_panel = ttk.Frame(pane, width=1080)

pane.add(left_panel, weight=1)
pane.add(right_panel, weight=5)

canvas = tk.Canvas(right_panel, bg='lightgray')
canvas.pack(fill=tk.BOTH, expand=True)

canvas.bind("<MouseWheel>", on_mousewheel)
canvas.bind("<Button-2>", on_middle_click)
canvas.bind("<B2-Motion>", on_middle_move)

zone_listbox = create_zone_listbox()
select_default_zone(zone_listbox)
root.mainloop()
