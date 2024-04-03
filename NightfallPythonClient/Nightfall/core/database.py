#GPT Tasks
#look at this code. I acess a database with map information. I want to draw the map now. use alle the moany information I added for database explaination to catch and write the right data to the database.
#let's start simple.
#create a window and split it vertically into two. on the left side, display all the names of the zones. on the right side (it should be 90% size), print one quadratic field for all the Object found in Objecttable with that ZoneID. PLace them on the given X and Y coordinates of the Object and link them using the ExitTabl with thin black lines. ensure the graphic refreshes when doubleclkicking another zone to load that zone then


#database.py
from map import setup_map_events
import webbrowser
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pyodbc
import ctypes

def find_access_driver():
    for driver in pyodbc.drivers():
        if 'ACCESS' in driver.upper():
            return driver
    return None

#DATABASE Explaination
#DirTbl maps Direction strings to DirRefs (IDs) and Revids(reverse travel). And Dx,Dy,Dz gives information where this direction needs to be placed on the mapper (e,g, x+200 y-200 z=0)
#ExitKindTbl give information about doors that need to be opened when moving along a link. It contains a name (normal , door, locked door), a "Script" how to handle that (NULL, open door, unlock %1,open door)...
#ExitTbl the most important and biggest table. ExitIDs, ExitIdTo, FromID, ToID tell you how to travel. DirType is also relevant, cause this is the direction from DirTbl
#NoteTbl contains extra notes (strings) Only NoteID, ObjID and Note are relevant
#ObjectTbl the second most important table. Hoolds all the data about the rooms. ZoneID tells you in which Zone this room is.  X and Y how positions for the map (Coordinates), RefNumber and ObjId are the same identifier. Name is the first line of the room description and Desc contains the whole room description
#PortalTbl contains all portals, ways that can be entered from anywhere and cannot be drawn as such.
#ZoneTbl contains the Zones of the map. ZoneID references it Name is the caption. MinX MinY MaxX and MaxY show the total size of the zone. Dx and Dy the position and XOffset and YOffset how much they need to be movr to match upper and lower layers.X and Y seems to be the latest view center

db_file = r"C:\Program Files (x86)\zMUD\nightfall\Map\Map.mdb"

access_driver = find_access_driver()
if access_driver is None:
    print("Microsoft Access Driver not found.")
    print("Please download and install the 64-bit Microsoft Access Database Engine 2016 Redistributable.")
    webbrowser.open("https://www.microsoft.com/en-us/download/details.aspx?id=54920")
else:
    conn_str = f'DRIVER={{{access_driver}}};DBQ={db_file}'


root = tk.Tk()
root.title("Map Viewer")
root.geometry("1200x600")

pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
pane.pack(fill=tk.BOTH, expand=True)

left_panel = ttk.Frame(pane, width=120)
right_panel = ttk.Frame(pane, width=1080)

pane.add(left_panel, weight=2)
pane.add(right_panel, weight=8)

zone_var = tk.StringVar()
figure = plt.Figure(figsize=(5, 4), dpi=100)
canvas = FigureCanvasTkAgg(figure, right_panel)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(fill=tk.BOTH, expand=True)

def open_db_connection():
    return pyodbc.connect(conn_str)

def fetch_zones():
    with open_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ZoneID, Name FROM ZoneTbl")
        zones = cursor.fetchall()
    return zones

def fetch_rooms(zone_id):
    with open_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ObjID, X, Y FROM ObjectTbl WHERE ZoneID = ?", (zone_id,))
        rooms = cursor.fetchall()
    return rooms

def fetch_exits(from_obj_ids):
    with open_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in from_obj_ids)
        cursor.execute(f"SELECT FromID, ToID FROM ExitTbl WHERE FromID IN ({placeholders})", from_obj_ids)
        exits = cursor.fetchall()
    return exits


def on_zone_select(event):
    if not event.widget.curselection():
        return
    index = event.widget.curselection()[0]
    zone_name = event.widget.get(index)
    zone_id = zone_dict[zone_name]
    rooms = fetch_rooms(zone_id)

    if not rooms:
        print("No rooms found for this zone.")
        return

    figure.clear()
    ax = figure.add_subplot(111)
    ax.set_aspect('equal', 'box')
    ax.axis('off')

    for room in rooms:
        ax.plot(room[1], room[2], 's', markersize=5, markeredgecolor='black', markerfacecolor='blue')

    exits = fetch_exits([room[0] for room in rooms])
    for exit in exits:
        from_pos = next((room[1:3] for room in rooms if room[0] == exit[0]), None)
        to_pos = next((room[1:3] for room in rooms if room[0] == exit[1]), None)
        if from_pos and to_pos:
            ax.add_line(mlines.Line2D([from_pos[0], to_pos[0]], [from_pos[1], to_pos[1]], linewidth=1, color='black'))
    canvas.draw()

def update_zone_listbox():
    zones = fetch_zones()
    global zone_dict
    zone_dict = {zone[1]: zone[0] for zone in zones}

    zone_listbox = tk.Listbox(left_panel, height=len(zones))
    for zone_name, _ in zone_dict.items():
        zone_listbox.insert(tk.END, zone_name)
    zone_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
    zone_listbox.bind('<<ListboxSelect>>', on_zone_select)

update_zone_listbox()
setup_map_events(canvas, figure)
root.mainloop()