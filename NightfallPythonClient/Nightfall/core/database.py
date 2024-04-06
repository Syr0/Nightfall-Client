#database.py
import webbrowser
import pyodbc
import time

MAX_RETRIES = 3
RETRY_DELAY = 1

#DATABASE Explaination
#DirTbl maps Direction strings to DirRefs (IDs) and Revids(reverse travel). And Dx,Dy,Dz gives information where this direction needs to be placed on the mapper (e,g, x+200 y-200 z=0)
#ExitKindTbl give information about doors that need to be opened when moving along a link. It contains a name (normal , door, locked door), a "Script" how to handle that (NULL, open door, unlock %1,open door)...
#ExitTbl the most important and biggest table. ExitIDs, ExitIdTo, FromID, ToID tell you how to travel. DirType is also relevant, cause this is the direction from DirTbl
#NoteTbl contains extra notes (strings) Only NoteID, ObjID and Note are relevant
#ObjectTbl the second most important table. Hoolds all the data about the rooms. ZoneID tells you in which Zone this room is.  X and Y how positions for the map (Coordinates), RefNumber and ObjId are the same identifier. Name is the first line of the room description and Desc contains the whole room description
#PortalTbl contains all portals, ways that can be entered from anywhere and cannot be drawn as such.
#ZoneTbl contains the Zones of the map. ZoneID references it Name is the caption. MinX MinY MaxX and MaxY show the total size of the zone. Dx and Dy the position and XOffset and YOffset how much they need to be movr to match upper and lower layers.X and Y seems to be the latest view center

DB_FILE  = r"..\..\Map.mdb"
ROOM_DESCRIPTION_CACHE = {}
ROOM_NAME_CACHE = {}

def find_access_driver():
    return next((driver for driver in pyodbc.drivers() if 'ACCESS' in driver.upper()), None)

def execute_query(query, params=(), fetch_one=False):
    conn_str = f'DRIVER={{{find_access_driver()}}};DBQ={DB_FILE}'
    for attempt in range(MAX_RETRIES):
        try:
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchone() if fetch_one else cursor.fetchall()
        except pyodbc.Error as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Database error: {e}. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                raise
    return None if fetch_one else []

def fetch_zones():
    return execute_query("SELECT ZoneID, Name FROM ZoneTbl")

def fetch_rooms(zone_id):
    return execute_query("SELECT ObjID, X, Y, Name FROM ObjectTbl WHERE ZoneID = ?", (zone_id,))

def fetch_exits(from_obj_ids):
    placeholders = ','.join('?' for _ in from_obj_ids)
    return execute_query(f"SELECT FromID, ToID FROM ExitTbl WHERE FromID IN ({placeholders})", from_obj_ids)

def fetch_zone_bounds(zone_id):
    return execute_query("SELECT MinX, MinY, MaxX, MaxY FROM ZoneTbl WHERE ZoneID = ?", (zone_id,), fetch_one=True)

def fetch_room_name(room_id):
    if room_id not in ROOM_NAME_CACHE:
        ROOM_NAME_CACHE[room_id] = execute_query("SELECT Name FROM ObjectTbl WHERE ObjID = ?", (room_id,), fetch_one=True)[0]
    return ROOM_NAME_CACHE.get(room_id)

def fetch_room_descriptions():
    if not ROOM_DESCRIPTION_CACHE:
        for obj_id, desc in execute_query("SELECT ObjID, Desc FROM ObjectTbl"):
            ROOM_DESCRIPTION_CACHE[obj_id] = desc
    return ROOM_DESCRIPTION_CACHE

def fetch_room_zone_id(room_id):
    return execute_query("SELECT ZoneID FROM ObjectTbl WHERE ObjID = ?", (room_id,), fetch_one=True)[0]

def fetch_room_position(room_id):
    return execute_query("SELECT X, Y FROM ObjectTbl WHERE ObjID = ?", (room_id,), fetch_one=True)

def fetch_connected_rooms(current_room_id):
    connected_room_ids = [row.ToID for row in execute_query("SELECT ToID FROM ExitTbl WHERE FromID = ?", (current_room_id,))]
    placeholders = ', '.join('?' for _ in connected_room_ids)
    query = f"SELECT ObjID, Desc FROM ObjectTbl WHERE ObjID IN ({placeholders})"
    return {obj_id: desc.strip().replace('\r\n', ' ').replace('\n', ' ') for obj_id, desc in execute_query(query, connected_room_ids)}


access_driver = (find_access_driver())
if access_driver is None:
    print("Microsoft Access Driver not found.")
    print("Please download and install the 64-bit Microsoft Access Database Engine 2016 Redistributable.")
    webbrowser.open("https://www.microsoft.com/en-us/download/details.aspx?id=54920")
