#map.py
import os
import tkinter as tk
import configparser

from tkinter import ttk
from core.database import fetch_rooms, fetch_zones, fetch_exits_with_zone_info, fetch_room_name, fetch_room_position, \
    fetch_zone_name
import map.camera
from gui.tooltip import ToolTip
from map.room_customization import RoomCustomization, RoomCustomizationDialog

def calculate_direction(from_pos, to_pos):
    dir_x = to_pos[0] - from_pos[0]
    dir_y = to_pos[1] - from_pos[1]
    mag = (dir_x**2 + dir_y**2) ** 0.5
    if mag == 0:
        return 0, 0
    return dir_x / mag, dir_y / mag

class MapViewer:
    def __init__(self, parent, pane, root, theme_manager=None):
        self.parent = parent
        self.pane = pane
        self.root = root
        self.theme_manager = theme_manager
        self.current_room_id = None
        self.displayed_zone_id = None
        self.current_level = 0
        self.levels_dict = {}
        self.has_found_position = False
        self.last_zone_id = None
        self.load_config()
        
        # Apply theme if available
        if self.theme_manager:
            theme = self.theme_manager.get_theme()['map']
            self.background_color = theme['bg']
            self.room_color = theme['room_color']
            self.note_color = theme['zone_note_color']

        self.this = tk.Canvas(self.parent, bg=self.background_color, highlightthickness=0)
        self.this.pack(fill=tk.BOTH, expand=True)
        self.camera = map.camera.Camera(self.this)  # Keep camera for manual zoom
        
        # Initialize room customization manager
        self.room_customization = RoomCustomization()

        self.level_var = tk.StringVar()
        self.level_var.set(f"Level: {self.current_level}")

        self.initialize_level_ui()

        self.zone_dict = self.fetch_zone_dict()
        self.initialize_ui()
        self.tooltips = {}
        
        # Bind right-click for room customization
        self.this.bind("<Button-3>", self.on_right_click)
        self.this.bind("<Double-Button-1>", self.on_double_click)
        # Bind ESC to stop autowalk
        self.this.bind("<Escape>", lambda e: self.stop_autowalk())
        # Bind Ctrl+F for room search
        self.this.bind("<Control-f>", lambda e: self.show_room_search_dialog())
        # Focus canvas to receive keyboard events
        self.this.focus_set()

        # Camera handles all view state now


    def initialize_ui(self):
        # Use tk.Frame for theme support
        zone_listbox_frame = tk.Frame(self.pane, width=200, bg=self.background_color)
        
        # Apply theme to listbox
        listbox_bg = self.background_color
        listbox_fg = "#FFFFFF" if self.background_color[1] < '5' else "#000000"  # Auto contrast
        select_bg = self.player_marker_color if hasattr(self, 'player_marker_color') else "#0078D4"
        
        self.zone_listbox = tk.Listbox(
            zone_listbox_frame, 
            height=10,
            bg=listbox_bg,
            fg=listbox_fg,
            selectbackground=select_bg,
            selectforeground="#FFFFFF",
            font=("Consolas", 10),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=listbox_bg,
            highlightcolor=select_bg
        )
        
        # Add scrollbar with theme
        scrollbar = tk.Scrollbar(zone_listbox_frame, bg=listbox_bg)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.zone_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.zone_listbox.yview)
        
        for zone_name in sorted(self.zone_dict.keys()):
            self.zone_listbox.insert(tk.END, zone_name)
        
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.zone_listbox.bind('<<ListboxSelect>>', self.on_zone_select)
        # Add keyboard navigation for zone list
        self.zone_listbox.bind('<KeyPress>', self.on_zone_list_keypress)
        self.pane.add(zone_listbox_frame, weight=1)
        
        # Store sorted zone names for quick access
        self.sorted_zone_names = sorted(self.zone_dict.keys())

    def load_config(self):
        config_file_path = os.path.join(os.path.dirname(__file__), '../config/settings.ini')
        config = configparser.ConfigParser()
        config.read(config_file_path)

        # Load defaults from config
        self.player_marker_color = config['Visuals']['PlayerMarkerColor']
        self.background_color = config['Visuals']['BackgroundColor']
        self.room_distance = int(config['Visuals']['RoomDistance'])
        self.room_color = config['Visuals']['RoomColor']
        self.directed_graph = config.getboolean('Visuals', 'DirectedGraph')
        self.default_zone = config['General']['DefaultZone']
        self.note_color = config['Visuals'].get('ZoneLeavingColor', '#FFA500')
        
        # Override with theme if available
        if hasattr(self, 'theme_manager') and self.theme_manager:
            theme = self.theme_manager.get_theme()['map']
            self.background_color = theme['bg']
            self.room_color = theme['room_color']
            self.note_color = theme['zone_note_color']
            self.player_marker_color = theme['room_highlight']
            self.connection_color = theme.get('connection_color', '#808080')
            # Calculate subtle crosshair color based on background
            bg = theme['bg']
            if bg.startswith('#'):
                # Parse hex color and make it slightly different from background
                r = int(bg[1:3], 16)
                g = int(bg[3:5], 16)
                b = int(bg[5:7], 16)
                # Make it slightly lighter or darker
                if (r + g + b) / 3 < 128:  # Dark background
                    self.crosshair_color = f"#{min(255, r+40):02x}{min(255, g+40):02x}{min(255, b+40):02x}"
                else:  # Light background
                    self.crosshair_color = f"#{max(0, r-40):02x}{max(0, g-40):02x}{max(0, b-40):02x}"
            else:
                self.crosshair_color = "#888888"

    def fetch_zone_dict(self):
        zones = fetch_zones()
        return {zone[1]: zone[0] for zone in zones}

    def initialize_level_ui(self):
        self.level_frame = tk.Frame(self.parent)
        self.level_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Get theme colors
        if self.theme_manager:
            theme = self.theme_manager.get_theme()
            bg_color = theme.get('bg', self.background_color)
            fg_color = theme.get('fg', '#FFFFFF')
            button_bg = theme.get('button_bg', bg_color)
            button_fg = theme.get('button_fg', fg_color)
            hover_color = theme.get('map', {}).get('room_highlight', '#FF6EC7')
        else:
            bg_color = self.background_color
            fg_color = '#FFFFFF' if bg_color[1] < '5' else '#000000'
            button_bg = bg_color
            button_fg = fg_color
            hover_color = '#FF6EC7'
        
        # Create toolbar frame with theme
        toolbar = tk.Frame(self.level_frame, height=35, bg=bg_color)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        # Level label with theme
        level_label = tk.Label(toolbar, textvariable=self.level_var, bg=bg_color, fg=fg_color, font=('Consolas', 10))
        level_label.pack(side=tk.LEFT, padx=10)
        
        # Up button (icon only) with theme
        up_btn = tk.Button(toolbar, text="⬆", command=lambda: self.change_level(1), 
                          width=3, bg=button_bg, fg=button_fg, relief="flat", 
                          font=('Arial', 12), cursor="hand2")
        up_btn.pack(side=tk.LEFT, padx=2)
        
        # Down button (icon only) with theme
        down_btn = tk.Button(toolbar, text="⬇", command=lambda: self.change_level(-1), 
                            width=3, bg=button_bg, fg=button_fg, relief="flat",
                            font=('Arial', 12), cursor="hand2")
        down_btn.pack(side=tk.LEFT, padx=2)
        
        # Manual position finding button - circle with crosshair
        find_btn = tk.Canvas(toolbar, width=30, height=30, highlightthickness=0, bg=bg_color)
        find_btn.pack(side=tk.LEFT, padx=5)
        
        # Draw circle with theme color
        find_btn.create_oval(5, 5, 25, 25, outline=fg_color, width=2)
        # Draw crosshair
        find_btn.create_line(15, 9, 15, 21, fill=fg_color, width=1)
        find_btn.create_line(9, 15, 21, 15, fill=fg_color, width=1)
        
        # Bind click to manual position finding
        find_btn.bind("<Button-1>", lambda e: self.manual_find_position())
        
        # Player location button - center on current room
        location_btn = tk.Canvas(toolbar, width=30, height=30, highlightthickness=0, bg=bg_color)
        location_btn.pack(side=tk.LEFT, padx=5)
        
        # Draw location pin icon
        location_btn.create_oval(10, 8, 20, 18, fill=hover_color, outline=fg_color, width=1)
        location_btn.create_polygon(15, 18, 11, 25, 15, 22, 19, 25, fill=hover_color, outline=fg_color, width=1)
        location_btn.create_oval(13, 11, 17, 15, fill=bg_color, outline="")
        
        # Bind click to center on player
        def center_on_player(e=None):
            if hasattr(self, 'current_highlight') and self.current_highlight:
                self.center_on_room(self.current_highlight)
        location_btn.bind("<Button-1>", center_on_player)
        
        # Search button
        search_btn = tk.Canvas(toolbar, width=30, height=30, highlightthickness=0, bg=bg_color)
        search_btn.pack(side=tk.LEFT, padx=5)
        
        # Draw magnifying glass icon
        search_btn.create_oval(8, 8, 18, 18, outline=fg_color, width=2)
        search_btn.create_line(16, 16, 22, 22, fill=fg_color, width=2)
        
        # Bind click to search
        search_btn.bind("<Button-1>", lambda e: self.show_room_search_dialog())
        
        # Add hover effects for all canvas buttons
        def add_hover(canvas, redraw_func):
            def on_enter(e):
                canvas.delete("all")
                redraw_func(hover_color, "hover")
            def on_leave(e):
                canvas.delete("all")
                redraw_func(fg_color, "normal")
            canvas.bind("<Enter>", on_enter)
            canvas.bind("<Leave>", on_leave)
        
        # Hover for find button
        def redraw_find(color, state):
            find_btn.create_oval(5, 5, 25, 25, outline=color, width=2, tags=state)
            find_btn.create_line(15, 9, 15, 21, fill=color, width=1, tags=state)
            find_btn.create_line(9, 15, 21, 15, fill=color, width=1, tags=state)
        add_hover(find_btn, redraw_find)
        
        # Hover for location button
        def redraw_location(color, state):
            fill_color = hover_color if state == "hover" else hover_color
            location_btn.create_oval(10, 8, 20, 18, fill=fill_color, outline=color, width=1, tags=state)
            location_btn.create_polygon(15, 18, 11, 25, 15, 22, 19, 25, fill=fill_color, outline=color, width=1, tags=state)
            location_btn.create_oval(13, 11, 17, 15, fill=bg_color, outline="", tags=state)
        add_hover(location_btn, redraw_location)
        
        # Hover for search button
        def redraw_search(color, state):
            search_btn.create_oval(8, 8, 18, 18, outline=color, width=2, tags=state)
            search_btn.create_line(16, 16, 22, 22, fill=color, width=2, tags=state)
        add_hover(search_btn, redraw_search)

    def display_zone(self, zone_id, auto_fit=True):
        self.displayed_zone_id = zone_id
        self.this.delete("all")
        rooms = fetch_rooms(zone_id, z=self.current_level)
        exits_info = self.exits_with_zone_info([room[0] for room in rooms])

        self.draw_map(rooms, exits_info)
        # Fit all rooms in view after drawing (unless disabled)
        if auto_fit:
            self.this.after(100, self.camera.fit_to_content)


    def change_level(self, delta):
        new_level = self.current_level + delta
        self.current_level = new_level
        self.level_var.set(f"Level: {self.current_level}")
        # Display zone with auto-fit to show all rooms at new level
        self.display_zone(self.displayed_zone_id)  # Will auto-fit by default
    
    def manual_find_position(self):
        """Manually trigger position finding by sending 'l' command"""
        if hasattr(self, 'parent') and hasattr(self.parent, 'connection'):
            print("[MAP] Manual position finding - sending 'l' command")
            self.parent.awaiting_response_for_command = True
            self.parent.last_command = 'l'
            self.parent.connection.send('l')

    def exits_with_zone_info(self, from_obj_ids):
        exits_info = fetch_exits_with_zone_info(from_obj_ids)
        detailed_exits_info = []
        for from_id, to_id, to_zone_id in exits_info:
            from_pos = fetch_room_position(from_id)
            to_pos = fetch_room_position(to_id)
            if from_pos and to_pos:
                # Extract x, y coordinates from position tuples
                from_xy = (from_pos[0], from_pos[1])
                to_xy = (to_pos[0], to_pos[1])
                dir_x, dir_y = calculate_direction(from_xy, to_xy)
                detailed_exits_info.append((from_id, to_id, to_zone_id, dir_x, dir_y))
            else:
                pass
        return detailed_exits_info

    def create_rounded_rectangle(self, x1, y1, x2, y2, radius=25, **kwargs):
        return self.this.create_polygon([x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y1+radius, x1, y1], **kwargs, smooth=True)

    def draw_room_with_shadow(self, x, y, room_id, room_name):
        box_size = 20
        shadow_offset = 6
        tag_id = str(room_id)

        # Shadow with theme-aware color
        shadow_tag = f"{tag_id}_shadow"
        shadow_color = "#202020" if hasattr(self, 'background_color') and self.background_color[1] < '5' else "gray80"
        self.create_rounded_rectangle(x - box_size + shadow_offset, y - box_size + shadow_offset,
                                      x + box_size + shadow_offset, y + box_size + shadow_offset, radius=10,
                                      fill=shadow_color, tags=(shadow_tag,))
        room_tag = f"{tag_id}_room"
        
        # Check for custom color, otherwise use theme color
        custom = self.room_customization.get_room_customization(room_id)
        room_fill_color = custom.get('color', self.room_color)
        
        self.create_rounded_rectangle(x - box_size, y - box_size, x + box_size, y + box_size, radius=10,
                                      fill=room_fill_color, tags=(room_tag,))
        
        # Add custom note indicator if note exists
        if custom.get('note'):
            # Use N instead of emoji for better compatibility
            note_indicator = self.this.create_text(x + box_size - 5, y - box_size + 5, 
                                                  text="N", font=('Arial', 8, 'bold'), 
                                                  fill=self.note_color,
                                                  tags=(f"{tag_id}_note",))
        
        self.this.tag_bind(room_tag, "<Enter>", lambda e, id=room_id: self.show_room_name(e, id, e.x, e.y))
        self.this.tag_bind(room_tag, "<Leave>", self.hide_room_name)

    def draw_exits(self, rooms, exits):
        bidirectional = set()
        exits_tuples = {(exit[0], exit[1]) for exit in exits}

        for from_id, to_id in exits_tuples:
            if (to_id, from_id) in exits_tuples:
                bidirectional.add((from_id, to_id))

        for from_id, to_id in exits_tuples:
            from_pos = next((room[1:3] for room in rooms if room[0] == from_id), None)
            to_pos = next((room[1:3] for room in rooms if room[0] == to_id), None)
            if from_pos and to_pos:
                line_color = getattr(self, 'connection_color', self.room_color)
                if (from_id, to_id) in bidirectional:
                    self.this.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], fill=line_color, width=2)
                else:
                    self.this.create_line(from_pos[0], from_pos[1], to_pos[0], to_pos[1], arrow=tk.LAST, fill=line_color, width=2)
    def draw_map(self, rooms, exits_info):
        total_x, total_y, count = 0, 0, 0
        room_size = 20
        shadow_offset = 6
        extra_padding = 10
        offset = room_size + shadow_offset + extra_padding
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

        # Draw exits first (behind rooms)
        self.draw_exits(rooms, [exit[:2] for exit in exits_info])
        
        # Draw rooms on top
        for room_id, x, y, z, name in rooms:
            # Handle None z-values as level 0
            if z is None:
                z = 0
            if z != self.current_level:
                continue
            self.draw_room_with_shadow(x, y, str(room_id), name)
            min_x, min_y = min(min_x, x - offset), min(min_y, y - offset)
            max_x, max_y = max(max_x, x + offset), max(max_y, y + offset)
            total_x += x
            total_y += y
            count += 1

        self.drawn_bounds = (min_x, min_y, max_x, max_y)
        
        # Draw zone change notes
        for exit_info in exits_info:
            from_id, to_id, to_zone_id, _, _ = exit_info
            if to_zone_id != self.displayed_zone_id:
                to_zone_name = fetch_zone_name(to_zone_id)
                from_room_position = fetch_room_position(from_id)
                if from_room_position:
                    x = from_room_position[0]
                    y = from_room_position[1]
                    self.place_zone_change_note(x, y, to_zone_name)
        
        # Store bounds for reference
        if count > 0:
            self.drawn_bounds = (min_x, min_y, max_x, max_y)
            # Camera will handle fitting in display_zone

    def place_zone_change_note(self, x, y, zone_name):
        note_text = f"To {zone_name}"
        # Add zone_note tag to enable double-click functionality
        zone_id = self.zone_dict.get(zone_name)
        tags = ("zone_note", f"zone_{zone_id}") if zone_id else ("zone_note",)
        self.this.create_text(x, y - 20, text=note_text, fill=self.note_color, 
                              font=('Helvetica', '10', 'bold'), tags=tags)


    def show_room_name(self, event, room_id, event_x, event_y):
        room_name = fetch_room_name(room_id)
        
        # Add custom note to tooltip if exists
        custom = self.room_customization.get_room_customization(room_id)
        if custom.get('note'):
            room_name = f"{room_name}\n\nNote: {custom['note']}"
        
        if room_id not in self.tooltips:
            self.tooltips[room_id] = ToolTip(self.this)
        self.tooltips[room_id].show_tip(room_name, event_x, event_y)
        self.this.bind("<Motion>", lambda e: self.update_tooltip_position(e, room_id, e.x, e.y))

    def update_tooltip_position(self, event, room_id, event_x, event_y):
        if room_id in self.tooltips:
            room_name = fetch_room_name(room_id)
            # Add custom note to tooltip if exists
            custom = self.room_customization.get_room_customization(room_id)
            if custom.get('note'):
                room_name = f"{room_name}\n\nNote: {custom['note']}"
            self.tooltips[room_id].show_tip(room_name, event_x, event_y)

    def hide_room_name(self, event):
        for tooltip in self.tooltips.values():
            tooltip.hide_tip()
        self.this.unbind("<Motion>")

    def on_zone_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            zone_name = event.widget.get(index)
            zone_id = self.zone_dict[zone_name]
            self.current_level = 0
            self.level_var.set(f"Level: {self.current_level}")
            self.display_zone(zone_id)  # Will auto-fit by default
            # No need for extra fit_map_to_view since display_zone handles it
    
    def on_zone_list_keypress(self, event):
        """Handle keyboard navigation in zone list"""
        if not event.char or not event.char.isalpha():
            return
        
        # Find first zone starting with typed letter
        target_char = event.char.upper()
        for i, zone_name in enumerate(self.sorted_zone_names):
            if zone_name.upper().startswith(target_char):
                # Select and show the zone
                self.zone_listbox.selection_clear(0, tk.END)
                self.zone_listbox.selection_set(i)
                self.zone_listbox.see(i)
                self.zone_listbox.event_generate('<<ListboxSelect>>')
                break
    
    def show_room_search_dialog(self):
        """Show dialog to search for rooms by description"""
        import tkinter.simpledialog as simpledialog
        from core.fast_database import get_database
        
        # Create search dialog
        search_text = simpledialog.askstring(
            "Search Rooms",
            "Enter text to search in room descriptions:",
            parent=self.this
        )
        
        if not search_text:
            return
        
        # Search in database
        db = get_database()
        search_lower = search_text.lower()
        matches = []
        
        # Search through all room descriptions
        for room_id, description in db.data["descriptions_index"]:
            if description and search_lower in description.lower():
                room = db.get_room(room_id)
                if room:
                    room_name = room.get("name", "Unknown")
                    zone_id = room.get("zone_id")
                    zone_name = db.get_zone_name(zone_id) if zone_id else "Unknown Zone"
                    matches.append((room_id, room_name, zone_name, description[:100]))
        
        if not matches:
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Search Results", f"No rooms found containing '{search_text}'")
            return
        
        # Show results in a new window
        self.show_search_results(matches, search_text)
    
    def show_search_results(self, matches, search_text):
        """Display search results in a window"""
        # Create results window
        results_window = tk.Toplevel(self.root)
        results_window.title(f"Search Results: '{search_text}'")
        results_window.geometry("600x400")
        
        # Apply theme if available
        if self.theme_manager:
            theme = self.theme_manager.get_theme()
            bg_color = theme.get('bg', self.background_color)
            fg_color = theme.get('fg', '#FFFFFF')
            results_window.configure(bg=bg_color)
        else:
            bg_color = self.background_color
            fg_color = '#FFFFFF' if bg_color[1] < '5' else '#000000'
        
        # Create frame with scrollbar
        frame = tk.Frame(results_window, bg=bg_color)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create listbox for results
        listbox = tk.Listbox(
            frame,
            bg=bg_color,
            fg=fg_color,
            selectbackground=self.player_marker_color,
            selectforeground='#FFFFFF',
            font=('Consolas', 10),
            height=20
        )
        
        scrollbar = tk.Scrollbar(frame, bg=bg_color)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)
        
        # Add results to listbox
        room_data = []
        for room_id, room_name, zone_name, desc_preview in matches:
            display_text = f"[{zone_name}] {room_name} - {desc_preview}..."
            listbox.insert(tk.END, display_text)
            room_data.append((room_id, zone_name))
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add info label
        info_label = tk.Label(
            results_window,
            text=f"Found {len(matches)} rooms. Double-click to go to room.",
            bg=bg_color,
            fg=fg_color
        )
        info_label.pack(pady=5)
        
        # Handle double-click to go to room
        def on_result_double_click(event):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                room_id, zone_name = room_data[index]
                
                # Get zone_id from zone_name
                zone_id = self.zone_dict.get(zone_name)
                if zone_id:
                    # Display the zone and highlight the room
                    self.current_level = 0
                    self.display_zone(zone_id)
                    self.this.after(100, lambda: self.highlight_room(str(room_id)))
                    self.this.after(200, lambda: self.center_on_room(str(room_id)))
                
                # Close the search window
                results_window.destroy()
        
        listbox.bind('<Double-Button-1>', on_result_double_click)

    def unhighlight_room(self, room_id):
        room_id = str(room_id)
        room_tag = f"{room_id}_room"
        if self.this.find_withtag(room_tag):
            # Check for custom color when unhighlighting
            custom = self.room_customization.get_room_customization(room_id)
            fill_color = custom.get('color', self.room_color)
            self.this.itemconfig(room_tag, fill=fill_color)
    
    def update_position_indicator(self, room_id):
        """Add crosshair lines at current position"""
        self.this.delete("position_indicator")
        
        room_tag = f"{room_id}_room"
        room_coords = self.this.bbox(room_tag)
        
        if room_coords:
            x = (room_coords[0] + room_coords[2]) / 2
            y = (room_coords[1] + room_coords[3]) / 2
            
            # Force update to get proper canvas bounds
            self.this.update_idletasks()
            
            # Get full canvas bounds
            canvas_bbox = self.this.bbox("all")
            if canvas_bbox:
                min_x, min_y, max_x, max_y = canvas_bbox
                # Extend well beyond visible area
                min_x -= 5000
                max_x += 5000
                min_y -= 5000
                max_y += 5000
            else:
                min_x, min_y = x - 10000, y - 10000
                max_x, max_y = x + 10000, y + 10000
            
            # Use theme-aware color
            color = getattr(self, 'crosshair_color', '#888888')
            
            self.this.create_line(
                min_x, y,
                max_x, y,
                fill=color,
                width=1,
                tags=("position_indicator",)
            )
            
            self.this.create_line(
                x, min_y,
                x, max_y,
                fill=color,
                width=1,
                tags=("position_indicator",)
            )
            
            self.this.tag_lower("position_indicator")
            self.this.tag_raise("connection", "position_indicator")

    def highlight_room(self, room_id):
        # Ensure room_id is a string for tag matching
        room_id = str(room_id)
        
        # Unhighlight previous room if different
        if hasattr(self, 'current_highlight') and self.current_highlight != room_id:
            self.unhighlight_room(self.current_highlight)
        
        self.current_highlight = room_id
        self.current_room_id = room_id
        
        # If no zone is displayed, we need to display it first
        if not self.displayed_zone_id:
            # Get the zone for this room and display it
            from core.database import fetch_room_zone_id
            zone_id = fetch_room_zone_id(room_id)
            if zone_id:
                # Don't auto-fit when displaying zone from position tracking
                self.display_zone(zone_id, auto_fit=False)
        
        room_tag = f"{room_id}_room"
        # Check if the room exists on canvas before trying to highlight
        if self.this.find_withtag(room_tag):
            highlight_color = getattr(self, 'player_marker_color', '#FF6EC7')
            self.this.itemconfig(room_tag, fill=highlight_color)
            self.update_position_indicator(room_id)
            
            # Don't auto-fit when highlighting - let manual zone selection control fitting
            # Mark that we've found a position
            self.has_found_position = True
            self.last_zone_id = self.displayed_zone_id
    
    def apply_theme(self, map_theme):
        """Apply a theme to the map"""
        self.background_color = map_theme['bg']
        self.room_color = map_theme['room_color']
        self.note_color = map_theme['zone_note_color']
        self.player_marker_color = map_theme['room_highlight']
        self.connection_color = map_theme.get('connection_color', '#808080')
        
        # Calculate subtle crosshair color based on background
        bg = map_theme['bg']
        if bg.startswith('#'):
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            if (r + g + b) / 3 < 128:  # Dark background
                self.crosshair_color = f"#{min(255, r+40):02x}{min(255, g+40):02x}{min(255, b+40):02x}"
            else:  # Light background
                self.crosshair_color = f"#{max(0, r-40):02x}{max(0, g-40):02x}{max(0, b-40):02x}"
        else:
            self.crosshair_color = "#888888"
        
        # Update canvas background
        self.this.config(bg=self.background_color)
        
        # Update existing items colors without redrawing
        # Update all room colors
        for item in self.this.find_withtag("room"):
            tags = self.this.gettags(item)
            # Skip highlighted room
            if not any("_room" in tag and hasattr(self, 'current_highlight') and 
                      tag == f"{self.current_highlight}_room" for tag in tags):
                self.this.itemconfig(item, fill=self.room_color)
        
        # Update connection colors
        for item in self.this.find_withtag("connection"):
            self.this.itemconfig(item, fill=self.connection_color)
        
        # Update note colors
        for item in self.this.find_withtag("note"):
            self.this.itemconfig(item, fill=self.note_color)
        
        # Update crosshair color
        for item in self.this.find_withtag("position_indicator"):
            self.this.itemconfig(item, fill=self.crosshair_color)
        
        # Update zone listbox with theme
        if hasattr(self, 'zone_listbox'):
            listbox_fg = "#FFFFFF" if self.background_color[1] < '5' else "#000000"
            self.zone_listbox.config(
                bg=self.background_color,
                fg=listbox_fg,
                selectbackground=self.player_marker_color,
                highlightbackground=self.background_color,
                highlightcolor=self.player_marker_color
            )
            # Update parent frame
            if self.zone_listbox.master:
                self.zone_listbox.master.config(bg=self.background_color)
    
    def on_double_click(self, event):
        # Convert event coordinates to canvas coordinates
        canvas_x = self.this.canvasx(event.x)
        canvas_y = self.this.canvasy(event.y)
        clicked_items = self.this.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)
        
        for item in clicked_items:
            tags = self.this.gettags(item)
            
            # Check for zone note first (higher priority)
            for tag in tags:
                if tag.startswith("zone_"):
                    try:
                        zone_id = int(tag.replace("zone_", ""))
                        # Open the clicked zone
                        self.current_level = 0  # Reset to level 0 when changing zones
                        self.level_var.set(f"Level: {self.current_level}")
                        self.display_zone(zone_id)  # Will auto-fit by default
                        return
                    except ValueError:
                        pass
            
            # Then check for room click (pathfinding)
            for tag in tags:
                if tag.endswith("_room"):
                    try:
                        target_room_id = int(tag.replace("_room", ""))
                        self.pathfind_to_room(target_room_id)
                        return
                    except ValueError:
                        pass
    
    def pathfind_to_room(self, target_room_id):
        if not hasattr(self, 'current_room_id') or not self.current_room_id:
            return
        
        current = int(self.current_room_id)
        target = int(target_room_id)
        
        if current == target:
            return
        
        # Store the target for recalculation after each step
        self.autowalk_target = target
        print(f"[PATHFIND] Setting autowalk target to room {target}")
        
        # Start the autowalk process
        self.send_next_walk_command()
    
    def find_path(self, start, end):
        from collections import deque
        from core.fast_database import get_database
        
        # Map exit types to direction commands
        EXIT_TYPE_TO_COMMAND = {
            0: "n",    # north
            1: "ne",   # northeast  
            2: "e",    # east
            3: "se",   # southeast
            4: "s",    # south
            5: "sw",   # southwest
            6: "w",    # west
            7: "nw",   # northwest
            8: "u",    # up
            9: "d",    # down
            10: "enter", # enter
            11: "leave"  # leave
        }
        
        db = get_database()
        queue = deque([(start, [])])
        visited = {start}
        
        while queue:
            current_room, path = queue.popleft()
            
            if current_room == end:
                return path
            
            exits = db.get_exits_from_room(current_room)
            for exit_info in exits:
                next_room = exit_info["to"]
                if next_room not in visited:
                    visited.add(next_room)
                    # Get command from mapping or use custom command if specified
                    if exit_info.get("command"):
                        direction = exit_info["command"]
                    else:
                        exit_type = exit_info.get("type", -1)
                        direction = EXIT_TYPE_TO_COMMAND.get(exit_type, f"unknown_{exit_type}")
                    new_path = path + [direction]
                    queue.append((next_room, new_path))
        
        return None
    
    def execute_path(self, path):
        # Deprecated - we now recalculate path after each step
        # This is kept for backward compatibility but not used
        pass
    
    def send_next_walk_command(self):
        # Check if we have a target
        if not hasattr(self, 'autowalk_target') or not self.autowalk_target:
            return
        
        # Check current position
        if not hasattr(self, 'current_room_id') or not self.current_room_id:
            print("[AUTO-WALK] Lost position, stopping")
            self.autowalk_target = None
            return
        
        current = int(self.current_room_id)
        target = self.autowalk_target
        
        # Check if we've reached the target
        if current == target:
            print(f"[AUTO-WALK] Reached target room {target}")
            self.autowalk_target = None
            return
        
        # Recalculate path from current position
        print(f"[AUTO-WALK] Recalculating path from {current} to {target}")
        path = self.find_path(current, target)
        
        if not path:
            print(f"[AUTO-WALK] No path found from {current} to {target}")
            self.autowalk_target = None
            return
        
        if hasattr(self, 'parent') and hasattr(self.parent, 'connection'):
            # Take the first step of the recalculated path
            command = path[0]
            print(f"[AUTO-WALK] Next step: {command} (total path: {len(path)} steps)")
            
            # Send the command
            self.parent.awaiting_response_for_command = True
            self.parent.last_command = command
            self.parent.connection.send(command)
            
            # Schedule next recalculation after room update
            # Increased delay to ensure position update completes
            self.this.after(1000, self.send_next_walk_command)
    
    def stop_autowalk(self):
        """Stop the current autowalk"""
        if hasattr(self, 'autowalk_target'):
            print(f"[AUTO-WALK] Stopped (was heading to room {self.autowalk_target})")
            self.autowalk_target = None
    
    def on_right_click(self, event):
        """Handle right-click on map"""
        # Convert canvas coordinates to actual coordinates
        canvas_x = self.this.canvasx(event.x)
        canvas_y = self.this.canvasy(event.y)
        
        # Find the closest item at click position
        clicked_item = self.this.find_closest(canvas_x, canvas_y)
        if clicked_item:
            # Get all tags for the clicked item
            tags = self.this.gettags(clicked_item)
            
            # Look for room tag
            room_id = None
            for tag in tags:
                if tag.endswith('_room'):
                    room_id = tag.replace('_room', '')
                    break
            
            if room_id:
                self.show_room_customization_dialog(room_id)
    
    def show_room_customization_dialog(self, room_id):
        """Show dialog for customizing room"""
        # Get current customization
        current = self.room_customization.get_room_customization(room_id)
        current_note = current.get('note', '')
        current_color = current.get('color', None)
        
        # Show dialog
        dialog = RoomCustomizationDialog(
            self.this,
            room_id,
            current_note,
            current_color
        )
        
        result = dialog.show()
        
        if result is not None:
            # Save customization
            success = self.room_customization.set_room_customization(
                room_id,
                note=result['note'],
                color=result['color']
            )
            
            if success:
                # Refresh the current zone to show changes
                if self.displayed_zone_id:
                    self.display_zone(self.displayed_zone_id)
                    # Re-highlight current room if needed
                    if hasattr(self, 'current_room_id') and self.current_room_id:
                        self.highlight_room(self.current_room_id)
            else:
                pass
    
    def center_view_on_bounds(self, min_x, min_y, max_x, max_y):
        """Deprecated - camera handles this automatically"""
        pass
    
    def fit_map_to_view(self):
        """Let camera handle fitting content to view"""
        self.camera.fit_to_content()
    
    def center_on_room(self, room_id):
        """Center the view on a specific room using camera"""
        room_tag = f"{room_id}_room"
        room_coords = self.this.bbox(room_tag)
        
        if room_coords:
            # Get room center
            room_x = (room_coords[0] + room_coords[2]) / 2
            room_y = (room_coords[1] + room_coords[3]) / 2
            
            # Let camera handle centering
            self.camera.center_on_point(room_x, room_y)