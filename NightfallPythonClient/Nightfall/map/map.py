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
        # Bind Ctrl+I for item search
        self.this.bind("<Control-i>", lambda e: self.show_item_search_dialog())
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
        # Don't create our own toolbar - parent will provide one
        pass
    
    def add_map_controls_to_toolbar(self, toolbar):
        """Add map-specific controls to the main toolbar"""
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
        
        # Add separator
        sep1 = tk.Frame(toolbar, width=2, bg=fg_color)
        sep1.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Level controls (replacing duplicates)
        level_label = tk.Label(toolbar, textvariable=self.level_var, bg=bg_color, fg=fg_color, font=('Consolas', 10))
        level_label.pack(side=tk.LEFT, padx=5)
        
        up_btn = tk.Button(toolbar, text="⬆", command=lambda: self.change_level(1), 
                          width=2, bg=button_bg, fg=button_fg, relief="flat", 
                          font=('Arial', 10), cursor="hand2")
        up_btn.pack(side=tk.LEFT, padx=1)
        
        down_btn = tk.Button(toolbar, text="⬇", command=lambda: self.change_level(-1), 
                            width=2, bg=button_bg, fg=button_fg, relief="flat",
                            font=('Arial', 10), cursor="hand2")
        down_btn.pack(side=tk.LEFT, padx=1)
        
        # Position finding button
        find_btn = tk.Canvas(toolbar, width=25, height=25, highlightthickness=0, bg=bg_color)
        find_btn.pack(side=tk.LEFT, padx=3)
        find_btn.create_oval(3, 3, 22, 22, outline=fg_color, width=2)
        find_btn.create_line(12, 7, 12, 18, fill=fg_color, width=1)
        find_btn.create_line(7, 12, 18, 12, fill=fg_color, width=1)
        find_btn.bind("<Button-1>", lambda e: self.manual_find_position())
        self._add_tooltip(find_btn, "Find Position (L)")
        
        # Center on player button
        location_btn = tk.Canvas(toolbar, width=25, height=25, highlightthickness=0, bg=bg_color)
        location_btn.pack(side=tk.LEFT, padx=3)
        location_btn.create_oval(8, 6, 17, 15, fill=hover_color, outline=fg_color, width=1)
        location_btn.create_polygon(12, 15, 9, 21, 12, 19, 15, 21, fill=hover_color, outline=fg_color, width=1)
        location_btn.create_oval(10, 8, 14, 12, fill=bg_color, outline="")
        def center_on_player(e=None):
            if hasattr(self, 'current_highlight') and self.current_highlight:
                self.center_on_room(self.current_highlight)
        location_btn.bind("<Button-1>", center_on_player)
        self._add_tooltip(location_btn, "Center on Player")
        
        # Room search button
        room_search_btn = tk.Canvas(toolbar, width=25, height=25, highlightthickness=0, bg=bg_color)
        room_search_btn.pack(side=tk.LEFT, padx=3)
        room_search_btn.create_oval(6, 6, 16, 16, outline=fg_color, width=2)
        room_search_btn.create_line(14, 14, 20, 20, fill=fg_color, width=2)
        room_search_btn.bind("<Button-1>", lambda e: self.show_room_search_dialog())
        self._add_tooltip(room_search_btn, "Search Rooms (Ctrl+F)")
        
        # Item search button
        item_search_btn = tk.Canvas(toolbar, width=25, height=25, highlightthickness=0, bg=bg_color)
        item_search_btn.pack(side=tk.LEFT, padx=3)
        # Draw box/package icon for items
        item_search_btn.create_rectangle(7, 10, 18, 20, outline=fg_color, width=2)
        item_search_btn.create_line(7, 13, 18, 13, fill=fg_color, width=1)
        item_search_btn.create_line(12, 7, 12, 13, fill=fg_color, width=1)
        item_search_btn.bind("<Button-1>", lambda e: self.show_item_search_dialog())
        self._add_tooltip(item_search_btn, "Search Items (Ctrl+I)")
        
        # Simple hover effect for all buttons
        for btn in [find_btn, location_btn, room_search_btn, item_search_btn]:
            self._add_hover_effect(btn, hover_color, fg_color)
    
    def _add_hover_effect(self, canvas, hover_color, normal_color):
        """Add simple color change on hover"""
        def on_enter(e):
            for item in canvas.find_all():
                item_type = canvas.type(item)
                try:
                    # Different item types have different options
                    if item_type in ['oval', 'rectangle', 'polygon']:
                        current_outline = canvas.itemcget(item, 'outline')
                        if current_outline and current_outline != '':
                            canvas.itemconfig(item, outline=hover_color)
                        current_fill = canvas.itemcget(item, 'fill')
                        if current_fill and current_fill != '' and current_fill != self.background_color:
                            canvas.itemconfig(item, fill=hover_color)
                    elif item_type == 'line':
                        canvas.itemconfig(item, fill=hover_color)
                except tk.TclError:
                    pass  # Item doesn't support this option
        
        def on_leave(e):
            for item in canvas.find_all():
                item_type = canvas.type(item)
                try:
                    if item_type in ['oval', 'rectangle', 'polygon']:
                        current_outline = canvas.itemcget(item, 'outline')
                        if current_outline and current_outline != '':
                            canvas.itemconfig(item, outline=normal_color)
                        current_fill = canvas.itemcget(item, 'fill')
                        # Keep hover color for location pin oval
                        if current_fill and current_fill != '' and current_fill != self.background_color:
                            if not (item_type == 'oval' and current_fill == hover_color):
                                canvas.itemconfig(item, fill=normal_color)
                    elif item_type == 'line':
                        canvas.itemconfig(item, fill=normal_color)
                except tk.TclError:
                    pass
        
        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
    
    def _add_tooltip(self, widget, text):
        """Add simple tooltip on hover"""
        widget.tooltip = None
        widget.tooltip_timer = None
        
        def show_tooltip():
            if widget.tooltip is None:
                widget.tooltip = tk.Toplevel()
                widget.tooltip.wm_overrideredirect(True)
                x = widget.winfo_rootx() + 15
                y = widget.winfo_rooty() + 25
                widget.tooltip.wm_geometry(f"+{x}+{y}")
                label = tk.Label(widget.tooltip, text=text, bg="#333333", fg="white", 
                               font=('Arial', 9), padx=5, pady=2)
                label.pack()
        
        def on_enter(e):
            if widget.tooltip_timer:
                widget.after_cancel(widget.tooltip_timer)
            widget.tooltip_timer = widget.after(500, show_tooltip)
        
        def on_leave(e):
            if widget.tooltip_timer:
                widget.after_cancel(widget.tooltip_timer)
                widget.tooltip_timer = None
            if widget.tooltip:
                widget.tooltip.destroy()
                widget.tooltip = None
        
        # Use add='+' to not override existing bindings
        widget.bind("<Enter>", on_enter, add='+')
        widget.bind("<Leave>", on_leave, add='+')

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
    
    def show_item_search_dialog(self):
        """Show dialog to search for items/NPCs"""
        import tkinter.simpledialog as simpledialog
        import json
        import os
        from core.fast_database import get_database
        
        # Create search dialog
        search_text = simpledialog.askstring(
            "Search Items/NPCs",
            "Enter item or NPC name to search for:",
            parent=self.this
        )
        
        if not search_text:
            return
        
        # Load items database
        items_file = os.path.join(os.path.dirname(__file__), '../data/room_items.json')
        
        try:
            if os.path.exists(items_file):
                with open(items_file, 'r', encoding='utf-8') as f:
                    items_data = json.load(f)
            else:
                import tkinter.messagebox as messagebox
                messagebox.showinfo("No Items", "No items database found. Explore rooms to build it!")
                return
        except Exception as e:
            print(f"[ITEM SEARCH] Error loading items: {e}")
            return
        
        # Search for items
        search_lower = search_text.lower()
        matches = []
        db = get_database()
        
        for room_id, room_data in items_data.items():
            for item in room_data['items']:
                if search_lower in item.lower():
                    # Get room info
                    room = db.get_room(room_id)
                    if room:
                        room_name = room.get("name", "Unknown")
                        zone_id = room.get("zone_id")
                        zone_name = db.get_zone_name(zone_id) if zone_id else "Unknown Zone"
                        last_seen = room_data['last_seen'].get(item, "Unknown")
                        matches.append((room_id, room_name, zone_name, item, last_seen))
        
        if not matches:
            import tkinter.messagebox as messagebox
            messagebox.showinfo("Search Results", f"No items/NPCs found containing '{search_text}'")
            return
        
        # Show results
        self.show_item_search_results(matches, search_text)
    
    def show_item_search_results(self, matches, search_text):
        """Display item search results"""
        # Create results window
        results_window = tk.Toplevel(self.root)
        results_window.title(f"Item Search: '{search_text}'")
        results_window.geometry("800x500")
        
        # Apply theme if available
        if self.theme_manager:
            theme = self.theme_manager.get_theme()
            bg_color = theme.get('bg', self.background_color)
            fg_color = theme.get('fg', '#FFFFFF')
            results_window.configure(bg=bg_color)
        else:
            bg_color = self.background_color
            fg_color = '#FFFFFF' if bg_color[1] < '5' else '#000000'
        
        # Create main frame
        main_frame = tk.Frame(results_window, bg=bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview for better display
        from tkinter import ttk
        
        # Configure treeview style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", 
                       background=bg_color,
                       foreground=fg_color,
                       fieldbackground=bg_color,
                       borderwidth=0)
        style.configure("Treeview.Heading",
                       background=bg_color,
                       foreground=fg_color,
                       borderwidth=1)
        style.map('Treeview',
                 background=[('selected', self.player_marker_color)],
                 foreground=[('selected', '#FFFFFF')])
        
        # Create treeview with columns
        columns = ('Item/NPC', 'Location', 'Zone', 'Last Seen')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
        
        # Define column headings and widths
        tree.heading('Item/NPC', text='Item/NPC Name')
        tree.heading('Location', text='Room')
        tree.heading('Zone', text='Zone')
        tree.heading('Last Seen', text='Last Seen')
        
        tree.column('Item/NPC', width=250)
        tree.column('Location', width=200)
        tree.column('Zone', width=150)
        tree.column('Last Seen', width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add results to treeview
        item_data = []
        for room_id, room_name, zone_name, item_name, last_seen in matches:
            # Format timestamp
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_seen)
                time_str = dt.strftime("%m/%d %H:%M")
            except:
                time_str = "Unknown"
            
            # Insert with item name first
            tree.insert('', 'end', values=(item_name, room_name, zone_name, time_str))
            item_data.append((room_id, zone_name, item_name))
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add info label
        info_frame = tk.Frame(results_window, bg=bg_color)
        info_frame.pack(fill=tk.X, pady=5)
        
        info_label = tk.Label(
            info_frame,
            text=f"Found {len(matches)} items/NPCs matching '{search_text}'. Double-click to go to location.",
            bg=bg_color,
            fg=fg_color,
            font=('Consolas', 10)
        )
        info_label.pack()
        
        # Add selected item display
        selected_label = tk.Label(
            info_frame,
            text="",
            bg=bg_color,
            fg=hover_color if 'hover_color' in locals() else '#FF6EC7',
            font=('Consolas', 10, 'bold')
        )
        selected_label.pack(pady=2)
        
        def on_select(event):
            """Update selected item display"""
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                values = item['values']
                selected_label.config(text=f"Selected: {values[0]} in {values[1]}")
        
        # Handle double-click to go to room
        def on_result_double_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                index = tree.index(selection[0])
                room_id, zone_name, item_name = item_data[index]
                
                # Get zone_id from zone_name
                zone_id = self.zone_dict.get(zone_name)
                if zone_id:
                    print(f"[ITEM SEARCH] Going to room {room_id} for item '{item_name}'")
                    # Display the zone and highlight the room
                    self.current_level = 0
                    self.display_zone(zone_id)
                    self.this.after(100, lambda: self.highlight_room(str(room_id)))
                    self.this.after(200, lambda: self.center_on_room(str(room_id)))
                
                # Close the search window
                results_window.destroy()
        
        tree.bind('<<TreeviewSelect>>', on_select)
        tree.bind('<Double-Button-1>', on_result_double_click)
        
        # Focus and select first item if exists
        if len(matches) > 0:
            first_item = tree.get_children()[0]
            tree.selection_set(first_item)
            tree.focus(first_item)

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
        
        # Check if autowalking and position changed
        if hasattr(self, 'autowalk_target') and self.autowalk_target:
            if hasattr(self, 'autowalk_last_position'):
                last_pos = self.autowalk_last_position
                current_pos = int(room_id)
                
                if last_pos != current_pos:
                    # Position changed successfully
                    print(f"[AUTO-WALK] Moved from {last_pos} to {current_pos}")
                    self.autowalk_waiting = False
                    # Reset failed attempts since we made progress
                    if hasattr(self, 'autowalk_failed_attempts'):
                        self.autowalk_failed_attempts = {}
                    # Continue walking after a short delay
                    self.this.after(500, self.send_next_walk_command)
                else:
                    # Position didn't change - might have hit a wall
                    print(f"[AUTO-WALK] Position unchanged at {current_pos}, might be blocked")
        
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
        
        # Prevent sending commands too quickly
        if hasattr(self, 'autowalk_waiting') and self.autowalk_waiting:
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
        
        # Check if we're stuck trying the same thing
        if hasattr(self, 'autowalk_failed_attempts'):
            if self.autowalk_failed_attempts.get(current, 0) >= 3:
                print(f"[AUTO-WALK] Failed 3 times from room {current}, giving up")
                self.autowalk_target = None
                self.autowalk_failed_attempts = {}
                return
        else:
            self.autowalk_failed_attempts = {}
        
        # Recalculate path from current position
        print(f"[AUTO-WALK] Calculating path from {current} to {target}")
        path = self.find_path(current, target)
        
        if not path:
            print(f"[AUTO-WALK] No path found from {current} to {target}")
            self.autowalk_target = None
            return
        
        if hasattr(self, 'parent') and hasattr(self.parent, 'connection'):
            # Store the last position and command
            self.autowalk_last_position = current
            self.autowalk_last_command = path[0]
            
            # Take the first step of the recalculated path
            command = path[0]
            print(f"[AUTO-WALK] Sending: {command} (path length: {len(path)})")
            
            # Mark that we're waiting for position update
            self.autowalk_waiting = True
            
            # Send the command
            self.parent.awaiting_response_for_command = True
            self.parent.last_command = command
            self.parent.connection.send(command)
            
            # Set a timeout in case position never updates (e.g., hit a wall)
            self.this.after(2000, self.check_autowalk_progress)
    
    def stop_autowalk(self):
        """Stop the current autowalk"""
        if hasattr(self, 'autowalk_target'):
            print(f"[AUTO-WALK] Stopped (was heading to room {self.autowalk_target})")
            self.autowalk_target = None
            self.autowalk_waiting = False
            self.autowalk_last_position = None
            self.autowalk_failed_attempts = {}
    
    def check_autowalk_progress(self):
        """Check if autowalk is stuck"""
        if not hasattr(self, 'autowalk_waiting') or not self.autowalk_waiting:
            return
        
        if hasattr(self, 'autowalk_last_position') and hasattr(self, 'current_room_id'):
            current_pos = int(self.current_room_id)
            if self.autowalk_last_position == current_pos:
                # No movement happened
                print(f"[AUTO-WALK] No progress from room {current_pos} using '{self.autowalk_last_command}'")
                
                # Track failed attempts from this position
                if not hasattr(self, 'autowalk_failed_attempts'):
                    self.autowalk_failed_attempts = {}
                self.autowalk_failed_attempts[current_pos] = self.autowalk_failed_attempts.get(current_pos, 0) + 1
                
                self.autowalk_waiting = False
                
                # Try again if we haven't failed too many times
                if hasattr(self, 'autowalk_target') and self.autowalk_target:
                    if self.autowalk_failed_attempts[current_pos] < 3:
                        print(f"[AUTO-WALK] Retry attempt {self.autowalk_failed_attempts[current_pos]}/3")
                        self.this.after(500, self.send_next_walk_command)
                    else:
                        print(f"[AUTO-WALK] Too many failures, stopping")
                        self.stop_autowalk()
    
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