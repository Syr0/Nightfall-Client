#database.py
import webbrowser
import threading
import logging
import sqlite3
import pyodbc

#DATABASE Explaination
#DirTbl maps Direction strings to DirRefs (IDs) and Revids(reverse travel). And Dx,Dy,Dz gives information where this direction needs to be placed on the mapper (e,g, x+200 y-200 z=0)
#ExitKindTbl give information about doors that need to be opened when moving along a link. It contains a name (normal , door, locked door), a "Script" how to handle that (NULL, open door, unlock %1,open door)...
#ExitTbl the most important and biggest table. ExitIDs, ExitIdTo, FromID, ToID tell you how to travel. DirType is also relevant, cause this is the direction from DirTbl
#NoteTbl contains extra notes (strings) Only NoteID, ObjID and Note are relevant
#ObjectTbl the second most important table. Hoolds all the data about the rooms. ZoneID tells you in which Zone this room is.  X and Y how positions for the map (Coordinates), RefNumber and ObjId are the same identifier. Name is the first line of the room description and Desc contains the whole room description
#PortalTbl contains all portals, ways that can be entered from anywhere and cannot be drawn as such.
#ZoneTbl contains the Zones of the map. ZoneID references it Name is the caption. MinX MinY MaxX and MaxY show the total size of the zone. Dx and Dy the position and XOffset and YOffset how much they need to be movr to match upper and lower layers.X and Y seems to be the latest view center

logging.basicConfig(level=logging.INFO, filename="database_logs.log", filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

DB_FILE = r"..\..\Map.mdb"
MEMORY_CONN = None
DB_LOCK = threading.Lock()
ROOM_NAME_CACHE = {}
ROOM_DESCRIPTION_CACHE = {}


def load_access_db_to_memory():
    """Loads the Access database into an in-memory SQLite database."""
    global MEMORY_CONN
    logging.info("Starting to load Access DB into memory.")

    tables_to_copy = ['DirTbl', 'ExitKindTbl', 'ExitTbl', 'NoteTbl', 'ObjectTbl', 'PortalTbl', 'ZoneTbl']

    try:
        # Set check_same_thread to False to allow the connection to be used in multiple threads
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
    """Executes a query on the in-memory SQLite database."""
    with DB_LOCK, MEMORY_CONN:
        cursor = MEMORY_CONN.cursor()
        cursor.execute(query, params)
        return cursor.fetchone() if fetch_one else cursor.fetchall()


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
    result = execute_query("SELECT Name FROM ObjectTbl WHERE ObjID = ?", (room_id,), fetch_one=True)
    if result:
        ROOM_NAME_CACHE[room_id] = result[0]
        return result[0]
    else:
        logging.info(f"No name found for RoomID: {room_id}")
        return "Unknown Room"


def fetch_room_descriptions():
    if not ROOM_DESCRIPTION_CACHE:
        for obj_id, desc in execute_query("SELECT ObjID, Desc FROM ObjectTbl"):
            ROOM_DESCRIPTION_CACHE[obj_id] = desc
    return ROOM_DESCRIPTION_CACHE


def fetch_zone_info():
    query = "SELECT ZoneID, Name, MinX, MinY, MaxX, MaxY FROM ZoneTbl"
    return execute_query(query)


def fetch_room_position(room_id):
    return execute_query("SELECT X, Y FROM ObjectTbl WHERE ObjID = ?", (room_id,), fetch_one=True)


def fetch_connected_rooms(current_room_id):
    connected_room_ids = [row[1] for row in execute_query("SELECT FromID, ToID FROM ExitTbl WHERE FromID = ?", (current_room_id,))]
    placeholders = ', '.join('?' for _ in connected_room_ids)
    query = f"SELECT ObjID, Desc FROM ObjectTbl WHERE ObjID IN ({placeholders})"
    results = execute_query(query, connected_room_ids)
    return {result[0]: result[1].strip().replace('\r\n', ' ').replace('\n', ' ') for result in results}


load_access_db_to_memory()

access_driver = (find_access_driver())
if access_driver is None:
    print("Microsoft Access Driver not found.")
    print("Please download and install the 64-bit Microsoft Access Database Engine 2016 Redistributable.")
    webbrowser.open("https://www.microsoft.com/en-us/download/details.aspx?id=54920")


def fetch_room_zone_id(room_id):
    query = "SELECT ZoneID FROM ObjectTbl WHERE ObjID = ?"
    result = execute_query(query, (room_id,), fetch_one=True)
    if result:
        return result[0]
    else:
        logging.info(f"No ZoneID found for RoomID: {room_id}")
        return None
