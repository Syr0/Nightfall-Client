import threading
from core.database import fetch_room_descriptions, fetch_connected_rooms, fetch_room_zone_id, fetch_room_name, fetch_room_position
import Levenshtein

class AutoWalker:
    def __init__(self, map_viewer):
        self.map_viewer = map_viewer
        self.active = False
        self.current_room_id = None

    def is_active(self):
        return self.active

    def set_current_room(self, room_id):
        # Unhighlight previous room if exists
        if self.current_room_id is not None and self.current_room_id != room_id:
            self.map_viewer.unhighlight_room(self.current_room_id)
        
        self.current_room_id = room_id
        new_zone_id = fetch_room_zone_id(room_id)
        
        # Get room position to determine z-level
        room_pos = fetch_room_position(room_id)
        if room_pos and len(room_pos) >= 3:
            z_level = room_pos[2] if room_pos[2] is not None else 0
        else:
            z_level = 0
        
        # Update display and highlight
        def update_display():
            # Update z-level if different
            if z_level != self.map_viewer.current_level:
                self.map_viewer.current_level = z_level
            
            if new_zone_id and (new_zone_id != self.map_viewer.displayed_zone_id or self.map_viewer.displayed_zone_id is None):
                self.map_viewer.display_zone(new_zone_id)
            
            # Ensure room is highlighted after display update
            self.map_viewer.root.after(200, lambda: self.map_viewer.highlight_room(room_id))
        
        self.map_viewer.root.after(0, update_display)

    def toggle_active(self):
        self.active = not self.active

    def analyze_response(self, response, is_look_command=False):
        if not self.active:
            return
        threading.Thread(target=self._process_response, args=(response, is_look_command)).start()

    def _process_response(self, response, is_look_command=False):
        if not self.active or response is None:
            return
        
        login_indicators = ["Welcome back", "Gamedriver", "LPmud", "Reincarnating", 
                          "posts waiting", "Mails waiting", "already existing"]
        if any(indicator in response for indicator in login_indicators):
            return
        
        if len(response) < 80:
            return
        exit_info = self._extract_exit_info(response)
        description = " ".join(response.split())
        words_in_response = set(description.split())

        room_descriptions = fetch_connected_rooms(
            self.current_room_id) if self.current_room_id else fetch_room_descriptions()

        if self.current_room_id:
            current_room_description = fetch_room_descriptions().get(self.current_room_id, "")
            room_descriptions[self.current_room_id] = current_room_description
        best_match = self._find_matching_room_with_exits(exit_info, words_in_response, room_descriptions)
        if best_match:
            if is_look_command:
                try:
                    self._calculate_highlighting(response, best_match, is_look_command)
                except Exception as e:
                    if self.current_room_id != best_match:
                        self.map_viewer.root.after(0, lambda: self.set_current_room(best_match))
            else:
                if self.current_room_id != best_match:
                    self.map_viewer.root.after(0, lambda: self.set_current_room(best_match))

    def _extract_exit_info(self, response):
        import re
        exits_pattern = r"There (?:are|is) (\w+) exits?:\s*([^.]+)\.?"
        match = re.search(exits_pattern, response, re.IGNORECASE)
        
        if match:
            count_word = match.group(1).lower()
            exits_text = match.group(2).lower()
            
            count_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
            exit_count = count_map.get(count_word, 0)
            
            exit_dirs = [e.strip() for e in exits_text.replace(' and ', ', ').split(',')]
            
            return {'count': exit_count, 'directions': exit_dirs}
        
        return None
    
    def _find_matching_room_with_exits(self, exit_info, words_in_response, room_descriptions):
        best_match = None
        best_score = 0
        
        for room_id, description in room_descriptions.items():
            score = 0
            
            if exit_info and description:
                desc_lower = description.lower()
                exit_patterns = [
                    f"there are {exit_info['count']} exits",
                    f"there is {exit_info['count']} exit",
                    f"{exit_info['count']} exits",
                    f"{exit_info['count']} obvious exits"
                ]
                
                for pattern in exit_patterns:
                    if pattern in desc_lower:
                        score += 100
                        break
                
                for direction in exit_info.get('directions', []):
                    if direction in desc_lower:
                        score += 10
            
            description = description or ""
            room_name = fetch_room_name(room_id) or ""
            combined_text = description + " " + room_name
            words_in_description = set(combined_text.split())
            common_words = words_in_response.intersection(words_in_description)
            score += len(common_words)
            
            if score > best_score:
                best_score = score
                best_match = room_id
        
        if not best_match or best_score < 50:
            best_match = self._find_matching_room(words_in_response, room_descriptions)
        
        return best_match
    
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
    
    def _calculate_highlighting(self, response, matched_room_id, is_look_command=False):
        if not is_look_command:
            return
            
        try:
            room_descriptions = fetch_room_descriptions()
            
            response_clean = self._clean_text_for_matching(response)
            
            best_room_id = None
            best_similarity = 0
            best_description = ""
            
            for room_id, description in room_descriptions.items():
                if not description:
                    continue
                    
                db_clean = self._clean_text_for_matching(description)
                
                similarity = Levenshtein.ratio(response_clean[:200], db_clean[:200])
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_room_id = room_id
                    best_description = description
            
            if best_similarity >= 0.6 and best_room_id:
                self.set_current_room(best_room_id)
                matched_room_id = best_room_id
            elif matched_room_id:
                self.set_current_room(matched_room_id)
            
            if best_description and best_similarity >= 0.9:
                db_clean = self._clean_text_for_matching(best_description)
                highlight_map = self._create_highlight_map(response, response_clean, db_clean)
                highlight_map['matched_room'] = best_room_id
                
                if hasattr(self.map_viewer, 'parent') and hasattr(self.map_viewer.parent, 'apply_description_highlighting'):
                    self.map_viewer.root.after(0, lambda: self.map_viewer.parent.apply_description_highlighting(highlight_map))
                
        except Exception as e:
            pass
    
    def _clean_text_for_matching(self, text):
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        text = ansi_escape.sub('', text)
        text = ' '.join(text.split())
        return text.lower()
    
    def _create_highlight_map(self, original_response, response_clean, db_clean):
        m, n = len(response_clean), len(db_clean)
        lcs = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if response_clean[i-1] == db_clean[j-1]:
                    lcs[i][j] = lcs[i-1][j-1] + 1
                else:
                    lcs[i][j] = max(lcs[i-1][j], lcs[i][j-1])
        
        matches = []
        i, j = m, n
        while i > 0 and j > 0:
            if response_clean[i-1] == db_clean[j-1]:
                matches.append(i-1)
                i -= 1
                j -= 1
            elif lcs[i-1][j] > lcs[i][j-1]:
                i -= 1
            else:
                j -= 1
        
        matches.reverse()
        
        highlight_ranges = self._map_to_original_positions(original_response, response_clean, matches)
        
        return {
            'response': original_response,
            'ranges': highlight_ranges,
            'similarity': len(matches) / max(m, n) if max(m, n) > 0 else 0
        }
    
    def _map_to_original_positions(self, original, clean, clean_positions):
        try:
            import re
            ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
            
            original_no_ansi = ansi_escape.sub('', original)
            clean_to_orig = []
            clean_idx = 0
            
            for orig_idx, char in enumerate(original_no_ansi.lower()):
                if clean_idx < len(clean) and char == clean[clean_idx]:
                    clean_to_orig.append(orig_idx)
                    clean_idx += 1
                elif char in ' \t\n\r' and clean_idx < len(clean) and clean[clean_idx] == ' ':
                    clean_to_orig.append(orig_idx)
                    clean_idx += 1
            
            ranges = []
            if clean_positions and clean_to_orig:
                start = clean_to_orig[clean_positions[0]] if clean_positions[0] < len(clean_to_orig) else 0
                for i in range(1, len(clean_positions)):
                    if clean_positions[i] != clean_positions[i-1] + 1:
                        end = clean_to_orig[clean_positions[i-1]] if clean_positions[i-1] < len(clean_to_orig) else start
                        ranges.append((start, end + 1))
                        if clean_positions[i] < len(clean_to_orig):
                            start = clean_to_orig[clean_positions[i]]
                if clean_positions[-1] < len(clean_to_orig):
                    end = clean_to_orig[clean_positions[-1]]
                    ranges.append((start, end + 1))
            
            return ranges
        except Exception as e:
            return []
