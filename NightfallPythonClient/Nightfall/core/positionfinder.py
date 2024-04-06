# positionfinder.py
import threading
from core.database import fetch_zone_name,fetch_room_descriptions, fetch_connected_rooms, fetch_room_zone_id, fetch_room_position, \
    fetch_room_name
import Levenshtein

class AutoWalker:
    def __init__(self, map_viewer):
        self.map_viewer = map_viewer
        self.active = False
        self.current_room_id = None

    def is_active(self):
        return self.active

    def set_current_room(self, room_id):
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
        words_in_response = set(description.split())

        room_descriptions = fetch_connected_rooms(
            self.current_room_id) if self.current_room_id else fetch_room_descriptions()

        if self.current_room_id:
            current_room_description = fetch_room_descriptions().get(self.current_room_id, "")
            room_descriptions[self.current_room_id] = current_room_description

        best_match = self._find_matching_room(words_in_response, room_descriptions)
        if best_match:
            room_zone_id = fetch_room_zone_id(best_match)

            if best_match != self.current_room_id:
                self.map_viewer.root.after(0, lambda: self.set_current_room(best_match))
                if room_zone_id != getattr(self.map_viewer, 'displayed_zone_id', None):
                    self.map_viewer.root.after(0, lambda: self.map_viewer.display_zone(room_zone_id))
            else:
                print("Player is looking around in the current room.")

    def _find_matching_room(self, words_in_response, room_descriptions):
        best_match = None
        max_common_words = 0
        possible_matches = []

        for room_id, description in room_descriptions.items():
            description = description or ""
            room_name = fetch_room_name(room_id) or ""
            combined_text = description + " " + room_name
            words_in_description = set(combined_text.split())
            common_words = words_in_response.intersection(words_in_description)
            common_word_count = len(common_words)

            if common_word_count > max_common_words:
                max_common_words = common_word_count
                possible_matches = [(room_id, combined_text)]
            elif common_word_count == max_common_words and common_word_count > 0:
                possible_matches.append((room_id, combined_text))

        if len(possible_matches) > 1:
            best_match = self._perform_full_text_comparison(words_in_response, possible_matches)
        elif possible_matches:
            best_match = possible_matches[0][0]

        if not best_match:
            print(
                "Couldn't find any room with a description matching the response. Please rework the room descriptions.")

        return best_match

    def _perform_full_text_comparison(self, words_in_response, possible_matches):
        response_text = " ".join(words_in_response).lower()
        highest_similarity = -1
        best_match = None

        for room_id, text in possible_matches:
            prepared_text = text.lower()
            similarity = Levenshtein.ratio(prepared_text, response_text)

            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = room_id

        return best_match

    def _calculate_levenshtein_distance(self, s1, s2):
        if len(s1) < len(s2):
            return self._calculate_levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
