# autowalker.py
import threading
from core.database import fetch_room_descriptions, fetch_connected_rooms, fetch_room_zone_id, fetch_room_position, \
    fetch_room_name


#Task
#"If toogled on, ensure that every time a response comes from the game server, the strings inside are compared with all the descriptions of rooms connected to the current location (need to be specified, too). if it matches, set that new room to the current player position (and hightlight it).
# unhighlight the last room. If there is no current room specified or the toggle was just now activated(and there was no movement since that), then search all the database for descriptions close to the current received one. Select the roomID of the best match. ensure not to compary linefeeds and carrieg returns"

class AutoWalker:
    def __init__(self, map_viewer):
        self.map_viewer = map_viewer
        self.active = False
        self.current_room_id = None

    def is_active(self):
        return self.active

    def set_current_room(self, room_id):
        print(f"Setting current room: {room_id}")
        if self.current_room_id is not None:
            self.map_viewer.unhighlight_room(self.current_room_id)
        self.current_room_id = room_id
        self.map_viewer.highlight_room(room_id)

    def toggle_active(self):
        self.active = not self.active
        if self.active and self.current_room_id is None:
            self.analyze_response(None)

    def analyze_response(self, response):
        if not self.active:
            return
        threading.Thread(target=self._process_response, args=(response,)).start()

    def _process_response(self, response):
        if not self.active or response is None:
            return
        description = " ".join(response.split())
        print(f"Received response description: {description}")  # Debug output
        words_in_response = set(description.split())

        room_descriptions = fetch_connected_rooms(
            self.current_room_id) if self.current_room_id else fetch_room_descriptions()

        best_match = self._find_matching_room(words_in_response, room_descriptions)
        if best_match:
            room_zone_id = fetch_room_zone_id(best_match)
            room_x, room_y = fetch_room_position(best_match)
            print(f"Best match found: Room ID {best_match}, Zone ID {room_zone_id}, Position ({room_x}, {room_y})")  # Debug output
            self.map_viewer.root.after(0, lambda: self.set_current_room(best_match))
            if room_zone_id != getattr(self.map_viewer, 'displayed_zone_id', None):
                self.map_viewer.root.after(0, lambda: self.map_viewer.display_zone(room_zone_id))
            if room_x is not None and room_y is not None:
                self.map_viewer.root.after(0, lambda: self.map_viewer.focus_point(room_x, room_y))

    def _find_matching_room(self, words_in_response, room_descriptions):
        best_match = None
        max_common_words = 0

        for room_id, description in room_descriptions.items():
            description = description or ""
            room_name = fetch_room_name(room_id) or ""
            combined_text = description + " " + room_name
            words_in_description = set(combined_text.split())
            common_words = words_in_response.intersection(words_in_description)
            if len(common_words) > max_common_words:
                max_common_words = len(common_words)
                best_match = room_id

        if best_match is None:
            print("Couldn't find any room with description matching the response.")

        return best_match
