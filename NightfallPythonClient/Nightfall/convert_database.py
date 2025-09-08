# convert_database.py - Convert Access DB to optimized JSON format
import json
import os
import sqlite3
import pyodbc
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# Database structure for fast lookups and Levenshtein comparisons
DATABASE_SCHEMA = {
    "version": "2.0",
    "created": None,
    "rooms": {},  # room_id: room_data
    "zones": {},  # zone_id: zone_data
    "exits": {},  # from_id: [(to_id, exit_type), ...]
    "commands": {  # Global and room-specific commands
        "global": {},  # command: description
        "room_specific": {}  # room_id: {command: description}
    },
    "items": {},  # item_id: item_data
    "units": {},  # unit_id: unit_data
    "descriptions_index": [],  # List of (room_id, description) for fast Levenshtein
    "names_index": []  # List of (room_id, name) for fast searching
}

def convert_access_to_json():
    """Convert Access database to optimized JSON format"""
    
    # Paths
    access_db = os.path.join(os.path.dirname(__file__), '../../Map.mdb')
    output_file = os.path.join(os.path.dirname(__file__), 'data/nightfall_world.json')
    
    if not os.path.exists(access_db):
        logging.error(f"Access database not found: {access_db}")
        return False
    
    # Create output directory
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Initialize new database
    new_db = DATABASE_SCHEMA.copy()
    new_db["created"] = datetime.now().isoformat()
    
    try:
        # Connect to Access DB
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={access_db}'
        access_conn = pyodbc.connect(conn_str)
        cursor = access_conn.cursor()
        
        # 1. Convert Zones
        logging.info("Converting zones...")
        cursor.execute("SELECT * FROM ZoneTbl")
        for row in cursor.fetchall():
            zone_id = row.ZoneID if hasattr(row, 'ZoneID') else row[0]
            new_db["zones"][str(zone_id)] = {
                "id": zone_id,
                "name": row.Name if hasattr(row, 'Name') else row[1],
                "bounds": {
                    "min_x": row.MinX if hasattr(row, 'MinX') else None,
                    "min_y": row.MinY if hasattr(row, 'MinY') else None,
                    "max_x": row.MaxX if hasattr(row, 'MaxX') else None,
                    "max_y": row.MaxY if hasattr(row, 'MaxY') else None
                }
            }
        
        # 2. Convert Rooms (ObjectTbl)
        logging.info("Converting rooms...")
        cursor.execute("SELECT * FROM ObjectTbl")
        room_count = 0
        for row in cursor.fetchall():
            room_id = row.ObjID if hasattr(row, 'ObjID') else row[0]
            room_name = row.Name if hasattr(row, 'Name') else ""
            room_desc = row.Desc if hasattr(row, 'Desc') else ""
            
            room_data = {
                "id": room_id,
                "name": room_name,
                "description": room_desc,
                "zone_id": row.ZoneID if hasattr(row, 'ZoneID') else None,
                "position": {
                    "x": row.X if hasattr(row, 'X') else 0,
                    "y": row.Y if hasattr(row, 'Y') else 0,
                    "z": row.Z if hasattr(row, 'Z') else 0
                },
                "exits": [],  # Will be filled later
                "commands": {},  # Room-specific commands
                "items": [],  # Items in this room
                "units": []   # Units/NPCs in this room
            }
            
            new_db["rooms"][str(room_id)] = room_data
            
            # Add to description index for fast Levenshtein
            if room_desc:
                new_db["descriptions_index"].append((room_id, room_desc))
            
            # Add to name index
            if room_name:
                new_db["names_index"].append((room_id, room_name))
            
            room_count += 1
        
        logging.info(f"Converted {room_count} rooms")
        
        # 3. Convert Exits
        logging.info("Converting exits...")
        cursor.execute("SELECT * FROM ExitTbl")
        exit_count = 0
        for row in cursor.fetchall():
            from_id = str(row.FromID if hasattr(row, 'FromID') else row[0])
            to_id = row.ToID if hasattr(row, 'ToID') else row[1]
            exit_type = row.DirType if hasattr(row, 'DirType') else 'unknown'
            
            # Add to exits lookup
            if from_id not in new_db["exits"]:
                new_db["exits"][from_id] = []
            new_db["exits"][from_id].append({
                "to": to_id,
                "type": exit_type,
                "command": row.DirName if hasattr(row, 'DirName') else None
            })
            
            # Add to room's exit list
            if from_id in new_db["rooms"]:
                new_db["rooms"][from_id]["exits"].append({
                    "to": to_id,
                    "type": exit_type,
                    "command": row.DirName if hasattr(row, 'DirName') else None
                })
            
            exit_count += 1
        
        logging.info(f"Converted {exit_count} exits")
        
        # 4. Try to convert Notes (if table exists)
        try:
            logging.info("Converting notes...")
            cursor.execute("SELECT * FROM NoteTbl")
            for row in cursor.fetchall():
                room_id = str(row.ObjID if hasattr(row, 'ObjID') else row[0])
                if room_id in new_db["rooms"]:
                    if "notes" not in new_db["rooms"][room_id]:
                        new_db["rooms"][room_id]["notes"] = []
                    new_db["rooms"][room_id]["notes"].append({
                        "text": row.Note if hasattr(row, 'Note') else row[1],
                        "type": row.NoteType if hasattr(row, 'NoteType') else "general"
                    })
        except:
            logging.info("No notes table found or error reading notes")
        
        # 5. Create optimized lookup structures
        logging.info("Creating optimized lookup structures...")
        
        # Pre-calculate connected rooms for each room
        for room_id, room_data in new_db["rooms"].items():
            connected = set()
            for exit_info in room_data["exits"]:
                connected.add(exit_info["to"])
            room_data["connected_rooms"] = list(connected)
        
        # Create zone-to-rooms mapping
        new_db["zone_rooms"] = {}
        for room_id, room_data in new_db["rooms"].items():
            zone_id = str(room_data["zone_id"])
            if zone_id not in new_db["zone_rooms"]:
                new_db["zone_rooms"][zone_id] = []
            new_db["zone_rooms"][zone_id].append(int(room_id))
        
        # Close Access connection
        access_conn.close()
        
        # 6. Save to JSON
        logging.info(f"Saving to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(new_db, f, indent=2, ensure_ascii=False)
        
        # Calculate file size
        file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
        logging.info(f"Conversion complete! File size: {file_size:.2f} MB")
        
        # Print statistics
        print("\n=== Conversion Statistics ===")
        print(f"Rooms: {len(new_db['rooms'])}")
        print(f"Zones: {len(new_db['zones'])}")
        print(f"Exits: {sum(len(exits) for exits in new_db['exits'].values())}")
        print(f"Description index entries: {len(new_db['descriptions_index'])}")
        print(f"File size: {file_size:.2f} MB")
        print(f"Output: {output_file}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_new_format():
    """Test the new JSON format for performance"""
    import time
    import Levenshtein
    
    json_file = os.path.join(os.path.dirname(__file__), 'data/nightfall_world.json')
    
    if not os.path.exists(json_file):
        print("JSON database not found. Run conversion first.")
        return
    
    print("\n=== Performance Test ===")
    
    # Load JSON
    start = time.time()
    with open(json_file, 'r', encoding='utf-8') as f:
        db = json.load(f)
    load_time = time.time() - start
    print(f"Load time: {load_time:.3f} seconds")
    
    # Test 1: Find room by ID
    start = time.time()
    room = db["rooms"].get("981")
    lookup_time = time.time() - start
    print(f"Room lookup by ID: {lookup_time * 1000:.3f} ms")
    
    # Test 2: Get all rooms in zone
    start = time.time()
    zone_rooms = [db["rooms"][str(rid)] for rid in db["zone_rooms"].get("7", [])]
    zone_time = time.time() - start
    print(f"Get all rooms in zone: {zone_time * 1000:.3f} ms ({len(zone_rooms)} rooms)")
    
    # Test 3: Levenshtein search across all descriptions
    test_text = "You are standing in front of the ancient altar"
    start = time.time()
    best_match = None
    best_score = 0
    
    for room_id, description in db["descriptions_index"]:
        if description:
            score = Levenshtein.ratio(test_text.lower(), description[:100].lower())
            if score > best_score:
                best_score = score
                best_match = room_id
    
    search_time = time.time() - start
    print(f"Levenshtein search across {len(db['descriptions_index'])} descriptions: {search_time:.3f} seconds")
    print(f"Best match: Room {best_match} with {best_score:.1%} similarity")
    
    # Memory usage
    import sys
    memory_usage = sys.getsizeof(db) / (1024 * 1024)
    print(f"Memory usage: ~{memory_usage:.2f} MB")

if __name__ == "__main__":
    print("=== Nightfall Database Converter ===")
    print("Converting Access DB to optimized JSON format...")
    
    if convert_access_to_json():
        print("\nConversion successful!")
        test_new_format()
    else:
        print("\nConversion failed!")