#database.py
# NEW: Using fast JSON-based database for instant operations
from .fast_database import get_database
import logging  # Still need logging for compatibility

# OLD: Keeping old imports commented for fallback
# import webbrowser
# import threading
# import sqlite3
# import pyodbc

#DATABASE Explaination
#DirTbl maps Direction strings to DirRefs (IDs) and Revids(reverse travel). And Dx,Dy,Dz gives information where this direction needs to be placed on the mapper (e,g, x+200 y-200 z=0)
#ExitKindTbl give information about doors that need to be opened when moving along a link. It contains a name (normal , door, locked door), a "Script" how to handle that (NULL, open door, unlock %1,open door)...
#ExitTbl the most important and biggest table. ExitIDs, ExitIdTo, FromID, ToID tell you how to travel. DirType is also relevant, cause this is the direction from DirTbl
#NoteTbl contains extra notes (strings) Only NoteID, ObjID and Note are relevant
#ObjectTbl the second most important table. Hoolds all the data about the rooms. ZoneID tells you in which Zone this room is.  X and Y how positions for the map (Coordinates), RefNumber and ObjId are the same identifier. Name is the first line of the room description and Desc contains the whole room description
#PortalTbl contains all portals, ways that can be entered from anywhere and cannot be drawn as such.
#ZoneTbl contains the Zones of the map. ZoneID references it Name is the caption. MinX MinY MaxX and MaxY show the total size of the zone. Dx and Dy the position and XOffset and YOffset how much they need to be movr to match upper and lower layers.X and Y seems to be the latest view center

# NEW: Get the global fast database instance
_db = get_database()

# OLD: Keeping old variables commented
# DB_FILE = r"..\..\Map.mdb"
# MEMORY_CONN = None
# DB_LOCK = threading.Lock()
# ROOM_NAME_CACHE = {}
# ROOM_DESCRIPTION_CACHE = {}


# OLD: All old database functions commented out
'''
def load_access_db_to_memory():
    global MEMORY_CONN
    logging.info("Starting to load Access DB into memory.")

    tables_to_copy = ['DirTbl', 'ExitKindTbl', 'ExitTbl', 'NoteTbl', 'ObjectTbl', 'PortalTbl', 'ZoneTbl']

    try:
        MEMORY_CONN = sqlite3.connect(":memory:", check_same_thread=False)
        access_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={DB_FILE}'
        with pyodbc.connect(access_conn_str) as access_conn:
            access_cursor = access_conn.cursor()

            for table in tables_to_copy:
                logging.info(f"Loading table: {table}")
                try:
                    rows = access_cursor.execute(f"SELECT * FROM [{table}]").fetchall()
                    cols = [column[0] for column in access_cursor.description]
                    create_statement = f"CREATE TABLE [{table}] ({', '.join(['[' + col + ']' for col in cols])})"
                    MEMORY_CONN.execute(create_statement)
                    insert_statement = f"INSERT INTO [{table}] VALUES ({', '.join(['?' for _ in cols])})"
                    MEMORY_CONN.executemany(insert_statement, rows)
                except Exception as e:
                    logging.error(f"Error loading table {table}: {e}")

            MEMORY_CONN.commit()
        logging.info("Access DB loaded into memory successfully.")
    except Exception as e:
        logging.error(f"Failed to load Access DB into memory: {e}")
        raise

def find_access_driver():
    return next((driver for driver in pyodbc.drivers() if 'ACCESS' in driver.upper()), None)

def execute_query(query, params=(), fetch_one=False):
    with DB_LOCK, MEMORY_CONN:
        cursor = MEMORY_CONN.cursor()
        cursor.execute(query, params)
        return cursor.fetchone() if fetch_one else cursor.fetchall()
'''

# NEW: Fast database functions
def fetch_zones():
    """Get all zones instantly from fast database"""
    return _db.get_all_zones()
    # OLD:
    # return execute_query("SELECT ZoneID, Name FROM ZoneTbl")

def fetch_min_max_levels(zone_id):
    """Get min/max Z levels for zone"""
    rooms = _db.get_rooms_in_zone(zone_id)
    if not rooms:
        return None, None
    z_levels = [r[3] for r in rooms if r[3] is not None]
    if not z_levels:
        return 0, 0
    return min(z_levels), max(z_levels)
    # OLD:
    # min_level = execute_query("SELECT MIN(Z) FROM ObjectTbl WHERE ZoneID = ?", (zone_id,))[0][0]
    # max_level = execute_query("SELECT MAX(Z) FROM ObjectTbl WHERE ZoneID = ?", (zone_id,))[0][0]
    # return min_level, max_level

def fetch_rooms(zone_id, z=None):
    """Get rooms in zone instantly from fast database"""
    return _db.get_rooms_in_zone(zone_id, z)
    # OLD:
    # query = "SELECT ObjID, X, Y, Z, Name FROM ObjectTbl WHERE ZoneID = ?"
    # params = [zone_id]
    # if z is not None:
    #     if z == 0:
    #         query += " AND (Z = ? OR Z IS NULL)"
    #         params.append(z)
    #     else:
    #         query += " AND Z = ?"
    #         params.append(z)
    # return execute_query(query, params)

def fetch_exits_with_zone_info(from_obj_ids):
    """Get exits with zone info instantly from fast database"""
    return _db.get_exits_with_zone_info(from_obj_ids)
    # OLD:
    # placeholders = ','.join('?' for _ in from_obj_ids)
    # query = f"""
    # SELECT e.FromID, e.ToID, o.ZoneID
    # FROM ExitTbl e
    # JOIN ObjectTbl o ON e.ToID = o.ObjID
    # WHERE e.FromID IN ({placeholders})
    # """
    # return execute_query(query, from_obj_ids)

def fetch_zone_bounds(zone_id):
    """Get zone bounds from fast database"""
    zone = _db.get_zone(zone_id)
    if zone and zone.get("bounds"):
        b = zone["bounds"]
        return (b["min_x"], b["min_y"], b["max_x"], b["max_y"])
    return None
    # OLD:
    # return execute_query("SELECT MinX, MinY, MaxX, MaxY FROM ZoneTbl WHERE ZoneID = ?", (zone_id,), fetch_one=True)

def fetch_room_name(room_id):
    """Get room name instantly from fast database"""
    return _db.get_room_name(room_id)
    # OLD:
    # room_id_int = int(room_id)
    # result = execute_query("SELECT Name FROM ObjectTbl WHERE ObjID = ?", (room_id_int,), fetch_one=True)
    # if result:
    #     ROOM_NAME_CACHE[room_id] = result[0]
    #     return result[0]
    # else:
    #     logging.info(f"No name found for RoomID: {room_id}")
    #     return "Unknown Room"

def fetch_room_descriptions():
    """Get all room descriptions instantly from fast database"""
    return _db.get_all_room_descriptions()
    # OLD:
    # if not ROOM_DESCRIPTION_CACHE:
    #     for obj_id, desc in execute_query("SELECT ObjID, Desc FROM ObjectTbl"):
    #         ROOM_DESCRIPTION_CACHE[obj_id] = desc
    # return ROOM_DESCRIPTION_CACHE

def fetch_zone_info():
    """Get all zone info from fast database"""
    zones = []
    for zone_id, zone in _db.data["zones"].items():
        b = zone.get("bounds", {})
        zones.append((int(zone_id), zone["name"], 
                     b.get("min_x"), b.get("min_y"), 
                     b.get("max_x"), b.get("max_y")))
    return zones
    # OLD:
    # query = "SELECT ZoneID, Name, MinX, MinY, MaxX, MaxY FROM ZoneTbl"
    # return execute_query(query)


def fetch_room_position(room_id):
    """Get room position instantly from fast database"""
    return _db.get_room_position(room_id)
    # OLD:
    # result = execute_query("SELECT X, Y, Z FROM ObjectTbl WHERE ObjID = ?", (room_id,), fetch_one=True)
    # if result:
    #     return result[0], result[1], result[2] if len(result) > 2 else None
    # return None


def fetch_connected_rooms(current_room_id):
    """Get connected room descriptions instantly from fast database"""
    return _db.get_connected_room_descriptions(current_room_id)
    # OLD:
    # connected_room_ids = [row[1] for row in execute_query("SELECT FromID, ToID FROM ExitTbl WHERE FromID = ?", (current_room_id,))]
    # placeholders = ', '.join('?' for _ in connected_room_ids)
    # query = f"SELECT ObjID, Desc FROM ObjectTbl WHERE ObjID IN ({placeholders})"
    # results = execute_query(query, connected_room_ids)
    # return {result[0]: result[1].strip().replace('\r\n', ' ').replace('\n', ' ') for result in results}

def fetch_zone_name(zone_id):
    """Get zone name instantly from fast database"""
    return _db.get_zone_name(zone_id)
    # OLD:
    # query = "SELECT Name FROM ZoneTbl WHERE ZoneID = ?"
    # result = execute_query(query, (zone_id,), fetch_one=True)
    # return result[0] if result else "Unknown Zone"

def fetch_room_zone_id(room_id):
    """Get room's zone ID instantly from fast database"""
    return _db.get_room_zone(room_id)
    # OLD:
    # query = "SELECT ZoneID FROM ObjectTbl WHERE ObjID = ?"
    # result = execute_query(query, (room_id,), fetch_one=True)
    # if result:
    #     return result[0]
    # else:
    #     logging.info(f"No ZoneID found for RoomID: {room_id}")
    #     return None


# NEW: Database loads automatically from JSON on import
# No need for explicit loading - happens instantly in FastDatabase.__init__()

# OLD: Access DB loading commented out
# load_access_db_to_memory()
# access_driver = (find_access_driver())
# if access_driver is None:
#     print("Microsoft Access Driver not found.")
#     print("Please download and install the 64-bit Microsoft Access Database Engine 2016 Redistributable.")
#     webbrowser.open("https://www.microsoft.com/en-us/download/details.aspx?id=54920")


