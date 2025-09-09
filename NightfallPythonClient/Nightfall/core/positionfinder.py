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
            # Check if we're changing zones
            zone_changing = new_zone_id and (new_zone_id != self.map_viewer.displayed_zone_id or self.map_viewer.displayed_zone_id is None)
            
            # Update level first (important for zone changes)
            if z_level != self.map_viewer.current_level or zone_changing:
                self.map_viewer.current_level = z_level
                self.map_viewer.level_var.set(f"Level: {z_level}")
            
            # Display new zone or redisplay current zone if level changed
            if zone_changing:
                self.map_viewer.display_zone(new_zone_id)
                # Camera state will be restored automatically or fit to content
            elif z_level != self.map_viewer.current_level and self.map_viewer.displayed_zone_id:
                # Level changed within same zone
                self.map_viewer.display_zone(self.map_viewer.displayed_zone_id)
            
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
            print(f"[POSITION] Not processing: active={self.active}, response={response is not None}")
            return
        
        print(f"[POSITION] Processing response (is_look={is_look_command}, length={len(response)})")
        
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
            print(f"[POSITION] Found matching room: {best_match}")
            
            # Extract items/NPCs from the response
            entities = self._extract_items_and_npcs(response)
            if entities['items'] or entities['npcs']:
                self._save_room_entities(best_match, entities)
            
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
        
        # Multiple patterns to match different exit formats
        patterns = [
            # Main pattern from Stunty - most comprehensive
            r'^\s*There (?:is|are) \w+ (?:visible |obvious )*(?:exit.?|path)s?(?: here)?:\s*(.*)',
            # Alternate: "The path leads north and west."
            r'The path leads?\s+(.+?)\.',
            # Older pattern for fallback
            r"There (?:are|is) (\w+) exits?:\s*([^.]+)\.?",
            # Simple "Exits: north, south"
            r'Exits?:\s*([^.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
            if match:
                # Extract exit directions from the matched text
                if len(match.groups()) == 2:
                    # Pattern with count word
                    count_word = match.group(1).lower()
                    exits_text = match.group(2).lower()
                    count_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
                    exit_count = count_map.get(count_word, 0)
                else:
                    # Pattern without count
                    exits_text = match.group(1).lower()
                    exit_count = 0
                
                # Parse directions from text
                # Handle "north and west" or "north, south, east"
                exits_text = exits_text.replace(' and ', ', ')
                exit_dirs = [e.strip() for e in exits_text.split(',')]
                # Clean up directions
                exit_dirs = [d for d in exit_dirs if d in ['north', 'south', 'east', 'west', 
                                                           'northeast', 'northwest', 'southeast', 'southwest',
                                                           'up', 'down', 'in', 'out', 'enter', 'leave',
                                                           'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw', 'u', 'd']]
                
                if exit_dirs:
                    print(f"[POSITION] Found exits: {exit_dirs}")
                    return {'count': len(exit_dirs), 'directions': exit_dirs}
        
        return None
    
    def _find_matching_room_with_exits(self, exit_info, words_in_response, room_descriptions):
        from core.fast_database import get_database
        db = get_database()
        
        # Collect all candidates with their scores
        candidates = []
        
        for room_id, description in room_descriptions.items():
            description_score = 0
            exit_score = 0
            exit_match_ratio = 0
            
            # Check description similarity
            description = description or ""
            room_name = fetch_room_name(room_id) or ""
            combined_text = description + " " + room_name
            words_in_description = set(combined_text.split())
            common_words = words_in_response.intersection(words_in_description)
            description_score = len(common_words)
            
            # Check if exits match what's in the database
            if exit_info:
                room_exits = db.get_room_exits(room_id)
                if room_exits:
                    # Get exit directions from database
                    db_directions = set()
                    for exit in room_exits:
                        exit_type = exit.get('type', -1)
                        # Map exit types to directions
                        type_to_dir = {
                            0: 'north', 1: 'northeast', 2: 'east', 3: 'southeast',
                            4: 'south', 5: 'southwest', 6: 'west', 7: 'northwest',
                            8: 'up', 9: 'down', 10: 'enter', 11: 'leave'
                        }
                        if exit_type in type_to_dir:
                            db_directions.add(type_to_dir[exit_type])
                            # Also add short forms
                            short_forms = {'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
                                         'northeast': 'ne', 'northwest': 'nw', 'southeast': 'se', 'southwest': 'sw',
                                         'up': 'u', 'down': 'd'}
                            if type_to_dir[exit_type] in short_forms:
                                db_directions.add(short_forms[type_to_dir[exit_type]])
                    
                    # Check if response exits match database exits
                    response_dirs = set(exit_info.get('directions', []))
                    
                    # Expand short forms in response to match
                    expanded_response = response_dirs.copy()
                    expand_map = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west',
                                'ne': 'northeast', 'nw': 'northwest', 'se': 'southeast', 'sw': 'southwest',
                                'u': 'up', 'd': 'down'}
                    for short, long in expand_map.items():
                        if short in response_dirs:
                            expanded_response.add(long)
                        if long in response_dirs:
                            expanded_response.add(short)
                    
                    # Check for match
                    matching_exits = expanded_response.intersection(db_directions)
                    if len(expanded_response) > 0 or len(db_directions) > 0:
                        exit_match_ratio = len(matching_exits) / max(len(expanded_response), len(db_directions))
                        exit_score = int(200 * exit_match_ratio)  # Up to 200 points for perfect exit match
            
            total_score = description_score + exit_score
            if total_score > 0:
                candidates.append({
                    'room_id': room_id,
                    'total_score': total_score,
                    'description_score': description_score,
                    'exit_score': exit_score,
                    'exit_match_ratio': exit_match_ratio
                })
        
        # Sort candidates by total score (descending)
        candidates.sort(key=lambda x: x['total_score'], reverse=True)
        
        if not candidates:
            print("[POSITION] No matching rooms found")
            return None
        
        # Get the top score
        top_score = candidates[0]['total_score']
        
        # Find all candidates within 20% of the top score
        threshold = top_score * 0.8
        top_candidates = [c for c in candidates if c['total_score'] >= threshold]
        
        print(f"[POSITION] Found {len(top_candidates)} candidates with similar scores (top score: {top_score})")
        
        # Among top candidates, prefer the one with best exit match
        best_candidate = None
        best_exit_ratio = -1
        
        for candidate in top_candidates[:10]:  # Check top 10 candidates max
            room_id = candidate['room_id']
            exit_ratio = candidate['exit_match_ratio']
            
            print(f"[POSITION] Candidate room {room_id}: desc_score={candidate['description_score']}, "
                  f"exit_score={candidate['exit_score']}, exit_match={exit_ratio:.2f}")
            
            # Prefer candidates with better exit matches
            if exit_ratio > best_exit_ratio:
                best_exit_ratio = exit_ratio
                best_candidate = candidate
            elif exit_ratio == best_exit_ratio and best_candidate:
                # If exit match is same, prefer higher description score
                if candidate['description_score'] > best_candidate['description_score']:
                    best_candidate = candidate
        
        if best_candidate:
            if best_candidate['exit_match_ratio'] >= 0.8:
                print(f"[POSITION] Selected room {best_candidate['room_id']} with excellent exit match ({best_candidate['exit_match_ratio']:.2f})")
            elif best_candidate['exit_match_ratio'] >= 0.5:
                print(f"[POSITION] Selected room {best_candidate['room_id']} with partial exit match ({best_candidate['exit_match_ratio']:.2f})")
            else:
                print(f"[POSITION] Selected room {best_candidate['room_id']} based on description (poor exit match: {best_candidate['exit_match_ratio']:.2f})")
            return best_candidate['room_id']
        
        # Fallback
        print("[POSITION] Using fallback room selection")
        return candidates[0]['room_id'] if candidates else None
    
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
    
    def _extract_items_and_npcs(self, response):
        """Extract items and NPCs from room description, distinguishing by ANSI codes"""
        import re
        
        # Keep original with ANSI codes to detect NPCs vs items
        lines_with_ansi = response.split('\n')
        # Also get clean lines for text extraction
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        lines = [ansi_escape.sub('', line) for line in lines_with_ansi]
        
        # Find where exits line is (items/NPCs come after)
        exit_line_idx = -1
        for i, line in enumerate(lines):
            if re.search(r'(?:There (?:is|are)|The path leads|Exits?:)', line, re.IGNORECASE):
                exit_line_idx = i
                break
        
        if exit_line_idx == -1:
            return []
        
        items = []
        npcs = []
        
        # Look at lines after the exit line
        i = exit_line_idx + 1
        while i < len(lines):
            line = lines[i].strip()
            line_with_ansi = lines_with_ansi[i].strip() if i < len(lines_with_ansi) else ""
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Skip prompt lines
            if line.startswith('>') or line == '>' or '> ' in line:
                i += 1
                continue
            
            # Check if this line is incomplete (doesn't end with period and is short)
            # This likely means it was split mid-word
            if not line.endswith('.') and len(line) < 20:
                # Check if next line exists and looks like a continuation
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    next_line_with_ansi = lines_with_ansi[i + 1].strip() if i + 1 < len(lines_with_ansi) else ""
                    
                    # If next line starts with lowercase or is a continuation, combine them
                    if next_line and (next_line[0].islower() or next_line.startswith('rd,')):
                        print(f"[DEBUG] Combining split lines: '{line}' + '{next_line}'")
                        # Combine the lines
                        line = line + next_line
                        line_with_ansi = line_with_ansi + next_line_with_ansi
                        # Skip the next line since we combined it
                        i += 1
            
            # Check if it's an NPC (bold+35 or direct 95) or item (35)
            # Need to check for both [1;35m and [35;1m patterns, as well as [95m
            is_npc = False
            has_purple = False
            
            # Debug: Show exact ANSI codes in the line
            import re
            ansi_codes = re.findall(r'\x1b\[[0-9;]*m', line_with_ansi)
            if ansi_codes and ('35' in str(ansi_codes) or '95' in str(ansi_codes)):
                print(f"[DEBUG] Full line: '{line}'")
                print(f"[DEBUG] Line length: {len(line)}, ends with period: {line.endswith('.')}")
                print(f"[DEBUG] ANSI codes found: {ansi_codes}")
            
            # Check if line has both bold AND magenta (NPCs)
            # Server sends them as separate sequences: [1m][35m] not [1;35m]
            has_bold = '\x1b[1m' in line_with_ansi
            has_magenta = '\x1b[35m' in line_with_ansi or '\x1b[0;35m' in line_with_ansi
            has_bright_magenta = '\x1b[95m' in line_with_ansi
            
            if has_bold and has_magenta:
                # Bold + Magenta = NPC
                is_npc = True
                has_purple = True
                print(f"[DEBUG] Detected as NPC (bold + magenta separate)")
            elif has_bright_magenta:
                # Direct bright magenta = NPC
                is_npc = True
                has_purple = True
                print(f"[DEBUG] Detected as NPC (bright magenta)")
            elif has_magenta and not has_bold:
                # Just magenta without bold = Item
                is_npc = False
                has_purple = True
                print(f"[DEBUG] Detected as ITEM (plain magenta, no bold)")
            # elif '\x1b[35m' in line_with_ansi:  # This is redundant now
                # Need to make sure it's not part of [1;35m or [35;1]
                # Check if 35 appears without bold
                import re
                # Look for [35m or sequences like [0;35m but not [1;35m or [35;1]
                if re.search(r'\x1b\[(?:0;)?35m', line_with_ansi) and not re.search(r'\x1b\[(?:1;35|35;1)m', line_with_ansi):
                    is_npc = False
                    has_purple = True
                    print(f"[DEBUG] Detected as ITEM (plain magenta)")
            
            if not has_purple:
                # No purple color, skip
                continue
            
            # Common patterns for items/NPCs:
            # "A stone obelisk with an inscription."
            # "Marvin, the cheerful juggler."
            # "An armourers cart."
            
            # Skip if it looks like a room description continuation
            if len(line) > 100:
                continue
            
            # Extract entity name - NPCs might not end with period
            entity_name = line.strip()
            
            # Remove period if present
            if entity_name.endswith('.'):
                entity_name = entity_name[:-1].strip()
            
            # Clean up common prefixes
            if entity_name.lower().startswith('a '):
                entity_name = entity_name[2:]
            elif entity_name.lower().startswith('an '):
                entity_name = entity_name[3:]
            elif entity_name.lower().startswith('the '):
                entity_name = entity_name[4:]
                
            if entity_name:
                if is_npc:
                    npcs.append(entity_name)
                    print(f"[POSITION] Found NPC: {entity_name}")
                else:
                    items.append(entity_name)
                    print(f"[POSITION] Found item: {entity_name}")
            
            # Move to next line
            i += 1
        
        return {'items': items, 'npcs': npcs}
    
    def _save_room_entities(self, room_id, entities):
        """Save items and NPCs to separate databases"""
        import json
        import os
        from datetime import datetime
        
        current_time = datetime.now().isoformat()
        room_key = str(room_id)
        
        # Save items to items database
        if entities['items']:
            items_file = os.path.join(os.path.dirname(__file__), '../data/room_items.json')
            try:
                if os.path.exists(items_file):
                    with open(items_file, 'r', encoding='utf-8') as f:
                        items_data = json.load(f)
                else:
                    items_data = {}
            except Exception as e:
                print(f"[POSITION] Error loading items data: {e}")
                items_data = {}
            
            if room_key not in items_data:
                items_data[room_key] = {'items': [], 'last_seen': {}}
            
            for item in entities['items']:
                if item not in items_data[room_key]['items']:
                    items_data[room_key]['items'].append(item)
                items_data[room_key]['last_seen'][item] = current_time
            
            try:
                os.makedirs(os.path.dirname(items_file), exist_ok=True)
                with open(items_file, 'w', encoding='utf-8') as f:
                    json.dump(items_data, f, indent=2, ensure_ascii=False)
                print(f"[POSITION] Saved {len(entities['items'])} items for room {room_id}")
            except Exception as e:
                print(f"[POSITION] Error saving items data: {e}")
        
        # Save NPCs to NPCs database
        if entities['npcs']:
            npcs_file = os.path.join(os.path.dirname(__file__), '../data/room_npcs.json')
            try:
                if os.path.exists(npcs_file):
                    with open(npcs_file, 'r', encoding='utf-8') as f:
                        npcs_data = json.load(f)
                else:
                    npcs_data = {}
            except Exception as e:
                print(f"[POSITION] Error loading NPCs data: {e}")
                npcs_data = {}
            
            if room_key not in npcs_data:
                npcs_data[room_key] = {'npcs': [], 'last_seen': {}}
            
            for npc in entities['npcs']:
                if npc not in npcs_data[room_key]['npcs']:
                    npcs_data[room_key]['npcs'].append(npc)
                npcs_data[room_key]['last_seen'][npc] = current_time
            
            try:
                os.makedirs(os.path.dirname(npcs_file), exist_ok=True)
                with open(npcs_file, 'w', encoding='utf-8') as f:
                    json.dump(npcs_data, f, indent=2, ensure_ascii=False)
                print(f"[POSITION] Saved {len(entities['npcs'])} NPCs for room {room_id}")
            except Exception as e:
                print(f"[POSITION] Error saving NPCs data: {e}")
    
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
