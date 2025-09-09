# fast_database.py - Optimized JSON-based database for lightning-fast operations
import json
import os
import logging
import time
from functools import lru_cache
import Levenshtein

class FastDatabase:
    """
    Optimized database using JSON for ultra-fast operations.
    Everything is kept in memory for instant access.
    """
    
    def __init__(self):
        self.data = None
        self.loaded = False
        self.json_file = os.path.join(os.path.dirname(__file__), '../data/nightfall_world.json')
        self.load_database()
    
    def load_database(self):
        """Load the entire database into memory"""
        if not os.path.exists(self.json_file):
            logging.warning(f"Database file not found: {self.json_file}")
            logging.info("Run convert_database.py first to create the optimized database")
            # Create empty structure
            self.data = {
                "rooms": {},
                "zones": {},
                "exits": {},
                "descriptions_index": [],
                "names_index": [],
                "zone_rooms": {}
            }
            return False
        
        try:
            start = time.time()
            with open(self.json_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            self.loaded = True
            load_time = time.time() - start
            logging.info(f"Database loaded in {load_time:.3f} seconds")
            return True
        except Exception as e:
            logging.error(f"Failed to load database: {e}")
            self.data = {
                "rooms": {},
                "zones": {},
                "exits": {},
                "descriptions_index": [],
                "names_index": [],
                "zone_rooms": {}
            }
            return False
    
    # === ROOM OPERATIONS (instant) ===
    
    def get_room(self, room_id):
        """Get room data instantly"""
        return self.data["rooms"].get(str(room_id))
    
    def get_room_name(self, room_id):
        """Get room name instantly"""
        room = self.get_room(room_id)
        return room["name"] if room else "Unknown Room"
    
    def get_room_description(self, room_id):
        """Get room description instantly"""
        room = self.get_room(room_id)
        return room["description"] if room else ""
    
    def get_room_position(self, room_id):
        """Get room position instantly"""
        room = self.get_room(room_id)
        if room and room.get("position"):
            pos = room["position"]
            return (pos["x"], pos["y"], pos.get("z", 0))
        return None
    
    def get_room_zone(self, room_id):
        """Get room's zone ID instantly"""
        room = self.get_room(room_id)
        return room["zone_id"] if room else None
    
    def get_room_exits(self, room_id):
        """Get room exits instantly"""
        room = self.get_room(room_id)
        return room["exits"] if room else []
    
    def get_connected_rooms(self, room_id):
        """Get connected room IDs instantly"""
        room = self.get_room(room_id)
        return room.get("connected_rooms", []) if room else []
    
    # === ZONE OPERATIONS (instant) ===
    
    def get_zone(self, zone_id):
        """Get zone data instantly"""
        return self.data["zones"].get(str(zone_id))
    
    def get_zone_name(self, zone_id):
        """Get zone name instantly"""
        zone = self.get_zone(zone_id)
        return zone["name"] if zone else "Unknown Zone"
    
    def get_all_zones(self):
        """Get all zones instantly"""
        return [(int(zid), zone["name"]) for zid, zone in self.data["zones"].items()]
    
    def get_rooms_in_zone(self, zone_id, z_level=None):
        """Get all rooms in a zone instantly"""
        room_ids = self.data["zone_rooms"].get(str(zone_id), [])
        rooms = []
        
        for rid in room_ids:
            room = self.get_room(rid)
            if room:
                pos = room["position"]
                room_z = pos.get("z", 0) if pos else 0
                
                # Filter by z-level if specified
                if z_level is not None:
                    # Include rooms with matching z or None z when z_level is 0
                    if z_level == 0 and (room_z == 0 or room_z is None):
                        rooms.append((room["id"], pos["x"], pos["y"], room_z, room["name"]))
                    elif room_z == z_level:
                        rooms.append((room["id"], pos["x"], pos["y"], room_z, room["name"]))
                else:
                    rooms.append((room["id"], pos["x"], pos["y"], room_z, room["name"]))
        
        return rooms
    
    # === EXIT OPERATIONS (instant) ===
    
    def get_exits_from_room(self, room_id):
        """Get all exits from a room instantly"""
        return self.data["exits"].get(str(room_id), [])
    
    def get_exits_with_zone_info(self, from_room_ids):
        """Get exits with zone information instantly"""
        results = []
        for from_id in from_room_ids:
            exits = self.get_exits_from_room(from_id)
            for exit_info in exits:
                to_id = exit_info["to"]
                to_room = self.get_room(to_id)
                if to_room:
                    results.append((from_id, to_id, to_room["zone_id"]))
        return results
    
    # === SEARCH OPERATIONS (optimized) ===
    
    @lru_cache(maxsize=128)
    def find_room_by_description(self, search_text, threshold=0.9):
        """
        Find room by description using Levenshtein.
        Cached for repeated searches.
        """
        search_lower = search_text.lower()[:200]  # Compare first 200 chars
        best_match = None
        best_score = 0
        
        for room_id, description in self.data["descriptions_index"]:
            if description:
                desc_lower = description.lower()[:200]
                score = Levenshtein.ratio(search_lower, desc_lower)
                if score > best_score:
                    best_score = score
                    best_match = room_id
                    if score >= threshold:
                        break  # Good enough match found
        
        return (best_match, best_score) if best_score >= threshold else (None, 0)
    
    def find_rooms_by_name(self, search_name):
        """Find rooms by name (partial match)"""
        search_lower = search_name.lower()
        matches = []
        
        for room_id, name in self.data["names_index"]:
            if search_lower in name.lower():
                matches.append(room_id)
        
        return matches
    
    def get_all_room_descriptions(self):
        """Get all room descriptions for position finding"""
        return {room_id: desc for room_id, desc in self.data["descriptions_index"]}
    
    def get_connected_room_descriptions(self, current_room_id):
        """Get descriptions of connected rooms for position finding"""
        if not current_room_id:
            return self.get_all_room_descriptions()
        
        connected_ids = self.get_connected_rooms(current_room_id)
        descriptions = {}
        
        for rid in connected_ids:
            room = self.get_room(rid)
            if room and room.get("description"):
                # Keep consistent - use integer keys like the old database
                descriptions[int(rid) if isinstance(rid, str) else rid] = room["description"]
        
        # Include current room (convert to int for consistency)
        current_room_id_int = int(current_room_id) if isinstance(current_room_id, str) else current_room_id
        current = self.get_room(current_room_id)
        if current and current.get("description"):
            descriptions[current_room_id_int] = current["description"]
        
        return descriptions
    
    # === BATCH OPERATIONS (optimized) ===
    
    def get_all_rooms(self):
        """Get all rooms (careful with memory!)"""
        return self.data["rooms"]
    
    def get_statistics(self):
        """Get database statistics"""
        return {
            "rooms": len(self.data["rooms"]),
            "zones": len(self.data["zones"]),
            "exits": sum(len(exits) for exits in self.data["exits"].values()),
            "descriptions": len(self.data["descriptions_index"]),
            "loaded": self.loaded
        }
    
    def delete_room(self, room_id):
        """Delete a room from the database"""
        try:
            room_id_str = str(room_id)
            
            # Check if room exists
            if room_id_str not in self.data["rooms"]:
                return False
            
            # Delete the room
            del self.data["rooms"][room_id_str]
            
            # Delete exits from this room
            if room_id_str in self.data["exits"]:
                del self.data["exits"][room_id_str]
            
            # Delete exits TO this room from other rooms
            for from_room, exits in list(self.data["exits"].items()):
                # Remove any exits that lead to the deleted room
                self.data["exits"][from_room] = {
                    direction: to_room 
                    for direction, to_room in exits.items() 
                    if str(to_room) != room_id_str
                }
                # Clean up empty exit dicts
                if not self.data["exits"][from_room]:
                    del self.data["exits"][from_room]
            
            # Remove from zone rooms list
            for zone_id, zone_data in self.data["zones"].items():
                if "rooms" in zone_data and room_id_str in zone_data["rooms"]:
                    zone_data["rooms"].remove(room_id_str)
            
            # Remove from descriptions index if present
            if room_id_str in self.data["descriptions_index"]:
                desc = self.data["descriptions_index"][room_id_str]
                if desc in self.data["descriptions"]:
                    rooms_with_desc = self.data["descriptions"][desc]
                    if room_id_str in rooms_with_desc:
                        rooms_with_desc.remove(room_id_str)
                    # Clean up empty description lists
                    if not rooms_with_desc:
                        del self.data["descriptions"][desc]
                del self.data["descriptions_index"][room_id_str]
            
            # Save changes back to file
            import json
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error deleting room {room_id}: {e}")
            return False

# Global instance for easy access
_db_instance = None

def get_database():
    """Get or create the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = FastDatabase()
    return _db_instance

# === COMPATIBILITY FUNCTIONS (drop-in replacements for old database.py) ===

def fetch_rooms(zone_id, z=None):
    """Compatibility: Get rooms in zone"""
    return get_database().get_rooms_in_zone(zone_id, z)

def fetch_zones():
    """Compatibility: Get all zones"""
    return get_database().get_all_zones()

def fetch_exits_with_zone_info(from_obj_ids):
    """Compatibility: Get exits with zone info"""
    return get_database().get_exits_with_zone_info(from_obj_ids)

def fetch_room_name(room_id):
    """Compatibility: Get room name"""
    return get_database().get_room_name(room_id)

def fetch_room_position(room_id):
    """Compatibility: Get room position"""
    return get_database().get_room_position(room_id)

def fetch_zone_name(zone_id):
    """Compatibility: Get zone name"""
    return get_database().get_zone_name(zone_id)

def fetch_room_descriptions():
    """Compatibility: Get all room descriptions"""
    return get_database().get_all_room_descriptions()

def fetch_connected_rooms(current_room_id):
    """Compatibility: Get connected room descriptions"""
    return get_database().get_connected_room_descriptions(current_room_id)

def fetch_room_zone_id(room_id):
    """Compatibility: Get room's zone ID"""
    return get_database().get_room_zone(room_id)

# Performance test
if __name__ == "__main__":
    import time
    
    print("=== Fast Database Performance Test ===")
    
    db = get_database()
    stats = db.get_statistics()
    print(f"Loaded: {stats['loaded']}")
    print(f"Rooms: {stats['rooms']}")
    print(f"Zones: {stats['zones']}")
    
    # Test lookups
    start = time.time()
    for i in range(1000):
        room = db.get_room(981)
    print(f"1000 room lookups: {(time.time() - start) * 1000:.2f} ms")
    
    # Test Levenshtein search
    start = time.time()
    result = db.find_room_by_description("You are standing in front of the ancient altar")
    print(f"Levenshtein search: {(time.time() - start) * 1000:.2f} ms")
    print(f"Result: {result}")