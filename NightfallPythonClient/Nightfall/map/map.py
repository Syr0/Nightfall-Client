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
        self.global_view_state = None
        self.current_level = 0
        self.scale = 1.0
        self.levels_dict = {}
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

        self.global_view_state = self.capture_current_view()


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
        self.pane.add(zone_listbox_frame, weight=1)

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
            self.position_indicator_fill = theme.get('position_indicator', '#F5F5F520')
            self.position_indicator_outline = theme.get('position_outline', '#E8E8E840')

    def fetch_zone_dict(self):
        zones = fetch_zones()
        return {zone[1]: zone[0] for zone in zones}

    def initialize_level_ui(self):
        self.level_frame = tk.Frame(self.this)
        self.level_frame.pack(side=tk.TOP, fill=tk.X)

    def display_zone(self, zone_id):
        self.displayed_zone_id = zone_id
        self.this.delete("all")
        rooms = fetch_rooms(zone_id, z=self.current_level)
        exits_info = self.exits_with_zone_info([room[0] for room in rooms])

        self.draw_map(rooms, exits_info)
        print(f"Display Zone: Zone ID = {zone_id}, Level = {self.current_level}")
        
        # Update scroll region but don't auto-zoom
        if hasattr(self, 'drawn_bounds') and self.drawn_bounds:
            min_x, min_y, max_x, max_y = self.drawn_bounds
            self.center_view_on_bounds(min_x, min_y, max_x, max_y)


    def change_level(self, delta):
        print(f"Changing Level: Current Level = {self.current_level}, Delta = {delta}")
        new_level = self.current_level + delta

        self.current_level = new_level
        self.display_zone(self.displayed_zone_id)

        print(f"Level Change Complete: New Level = {self.current_level}")

    def capture_current_view(self):
        bbox = self.this.bbox("all")
        if bbox is None:
            return (0, 0, 1.0, 0, 0, 100, 100)
        else:
            x1, y1, x2, y2 = bbox
            scroll_x = self.this.xview()[0]
            scroll_y = self.this.yview()[0]
            return (scroll_x, scroll_y, self.scale, x1, y1, x2, y2)

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
                print(f"Position not found for from_id: {from_id} or to_id: {to_id}")
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
        
        # Auto-fit view to show all rooms - ensure this happens after drawing
        if count > 0:
            # Use after to ensure canvas is updated
            self.this.after(50, lambda: self.center_view_on_bounds(min_x, min_y, max_x, max_y))

    def place_zone_change_note(self, x, y, zone_name):
        note_text = f"To {zone_name}"
        self.this.create_text(x, y - 20, text=note_text, fill=self.note_color, font=('Helvetica', '10', 'bold'))


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
            self.display_zone(zone_id)

    def unhighlight_room(self, room_id):
        room_id = str(room_id)
        room_tag = f"{room_id}_room"
        if self.this.find_withtag(room_tag):
            # Check for custom color when unhighlighting
            custom = self.room_customization.get_room_customization(room_id)
            fill_color = custom.get('color', self.room_color)
            self.this.itemconfig(room_tag, fill=fill_color)
    
    def update_position_indicator(self, room_id):
        """Add a very subtle circle around current position"""
        # Remove old position indicator
        self.this.delete("position_indicator")
        
        # Find the room rectangle on canvas
        room_tag = f"{room_id}_room"
        room_coords = self.this.bbox(room_tag)  # Use bbox for accurate bounds
        
        if room_coords:
            # Get exact center of room
            x = (room_coords[0] + room_coords[2]) / 2
            y = (room_coords[1] + room_coords[3]) / 2
            
            # Smaller, more subtle circle
            radius = 40
            
            # Very light, subtle circle
            self.this.create_oval(
                x - radius, y - radius,
                x + radius, y + radius,
                fill='',  # No fill, just outline
                outline='#C0C0C0',  # Light grey outline
                width=1,  # Thin line
                dash=(5, 5),  # Dashed line for subtlety
                tags=("position_indicator",)
            )
            
            # Put it behind everything
            self.this.tag_lower("position_indicator")
            
            # Lower the indicator to be behind connections
            self.this.tag_lower("position_indicator")
            # Make sure connections stay above indicator but below rooms
            self.this.tag_raise("connection", "position_indicator")

    def highlight_room(self, room_id):
        # Ensure room_id is a string for tag matching
        room_id = str(room_id)
        
        # Unhighlight previous room if different
        if hasattr(self, 'current_highlight') and self.current_highlight != room_id:
            self.unhighlight_room(self.current_highlight)
        
        self.current_highlight = room_id
        self.current_room_id = room_id
        
        room_tag = f"{room_id}_room"
        # Check if the room exists on canvas before trying to highlight
        if self.this.find_withtag(room_tag):
            highlight_color = getattr(self, 'player_marker_color', '#FF6EC7')
            self.this.itemconfig(room_tag, fill=highlight_color)
            # Add position indicator circle
            self.update_position_indicator(room_id)
            print(f"[Map] Highlighted room {room_id}")
        else:
            print(f"[Map] Room {room_id} not found on current display")
    
    def apply_theme(self, map_theme):
        """Apply a theme to the map"""
        self.background_color = map_theme['bg']
        self.room_color = map_theme['room_color']
        self.note_color = map_theme['zone_note_color']
        self.player_marker_color = map_theme['room_highlight']
        self.connection_color = map_theme.get('connection_color', '#808080')
        self.position_indicator_fill = map_theme.get('position_indicator', '#F5F5F520')
        self.position_indicator_outline = map_theme.get('position_outline', '#E8E8E840')
        
        # Update canvas background
        self.this.config(bg=self.background_color)
        
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
                print(f"[Customization] Saved customization for room {room_id}")
                # Refresh the current zone to show changes
                if self.displayed_zone_id:
                    self.display_zone(self.displayed_zone_id)
                    # Re-highlight current room if needed
                    if hasattr(self, 'current_room_id') and self.current_room_id:
                        self.highlight_room(self.current_room_id)
            else:
                print(f"[Customization] Failed to save customization for room {room_id}")
    
    def center_view_on_bounds(self, min_x, min_y, max_x, max_y):
        """Just update scroll region - don't mess with zoom or position"""
        # Set scroll region
        padding = 1000
        self.this.config(scrollregion=(min_x - padding, min_y - padding, 
                                       max_x + padding, max_y + padding))