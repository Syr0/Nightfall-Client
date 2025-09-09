import json
import os

class Camera:
    def __init__(self, canvas, initial_position=(0, 0), initial_zoom=1.0):
        self.canvas = canvas
        self.position = initial_position
        self.zoom = initial_zoom
        self.start_pan_pos = None
        self.zone_states = {}  # Store camera state per zone
        self.states_file = os.path.join(os.path.dirname(__file__), '../data/camera_states.json')
        self.load_states_from_file()

        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.on_pan)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

        self.apply_current_zoom()

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.start_pan_pos = (event.x, event.y)

    def on_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        dx = (self.start_pan_pos[0] - event.x) / self.zoom
        dy = (self.start_pan_pos[1] - event.y) / self.zoom
        self.position = (self.position[0] + dx, self.position[1] + dy)
        self.start_pan_pos = (event.x, event.y)
        
        # Auto-save camera state when panning if we have a zone
        if hasattr(self, 'current_zone_id') and self.current_zone_id:
            # Throttle saves - only save after pan is done
            if hasattr(self, '_save_timer'):
                self.canvas.after_cancel(self._save_timer)
            self._save_timer = self.canvas.after(500, lambda: self.save_zone_state(self.current_zone_id))

    def on_zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        factor = 1.001 ** event.delta
        new_zoom = self.zoom * factor
        
        # Allow much wider zoom range
        new_zoom = max(0.001, min(50.0, new_zoom))

        relative_factor = new_zoom / self.zoom
        self.zoom = new_zoom
        self.canvas.scale("all", x, y, relative_factor, relative_factor)
        self.update_scroll_region()
        
        print(f"[CAMERA] Zoom changed to {self.zoom:.6f}")
        
        # Auto-save camera state when zooming if we have a zone
        if hasattr(self, 'current_zone_id') and self.current_zone_id:
            self.save_zone_state(self.current_zone_id)

    def update_scroll_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def apply_current_zoom(self):
        self.canvas.scale("all", 0, 0, self.zoom, self.zoom)
        self.update_scroll_region()

    def log_current_position(self):
        pass
    
    def save_zone_state(self, zone_id):
        """Save current camera state for a zone"""
        if zone_id:
            # Get current view position
            x1 = self.canvas.canvasx(0)
            y1 = self.canvas.canvasy(0)
            self.zone_states[zone_id] = {
                'zoom': self.zoom,
                'view_x': x1,
                'view_y': y1,
                'position': self.position
            }
            print(f"[CAMERA] Saved state for {zone_id}: zoom={self.zoom:.6f}, view=({x1:.0f},{y1:.0f})")
            # Also save to file for persistence
            self.save_states_to_file()
    
    def restore_zone_state(self, zone_id):
        """Restore camera state for a zone"""
        if zone_id and zone_id in self.zone_states:
            state = self.zone_states[zone_id]
            
            # IMPORTANT: Clear ALL transformations first
            self.canvas.delete("all")  # This will be redrawn by caller
            
            # Set zoom directly without any scaling first
            saved_zoom = state['zoom']
            # Allow wider range but sanity check
            saved_zoom = max(0.001, min(50.0, saved_zoom))
            self.zoom = saved_zoom
            
            # Position will be set by the caller after drawing
            self.position = state.get('position', (0, 0))
            
            # Store the view position to restore after drawing
            self.pending_view_x = state.get('view_x', 0)
            self.pending_view_y = state.get('view_y', 0)
            
            print(f"[CAMERA] Will restore state for {zone_id}: zoom={self.zoom:.6f}, view=({self.pending_view_x:.0f},{self.pending_view_y:.0f})")
            return True
        else:
            print(f"[CAMERA] No saved state for {zone_id}, starting with zoom=1.0")
            # Reset to default zoom when no state
            self.zoom = 1.0
            self.position = (0, 0)
        return False
    
    def apply_pending_view(self):
        """Apply pending view position after map is drawn"""
        if hasattr(self, 'pending_view_x') and hasattr(self, 'pending_view_y'):
            # Apply the zoom to all new items
            if self.zoom != 1.0:
                self.canvas.scale("all", 0, 0, self.zoom, self.zoom)
            
            # Restore view position
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
            self.canvas.scan_mark(0, 0)
            self.canvas.scan_dragto(int(-self.pending_view_x), int(-self.pending_view_y), gain=1)
            
            # Clear pending
            del self.pending_view_x
            del self.pending_view_y
            
            self.update_scroll_region()
            print(f"[CAMERA] Applied pending view state")
    
    def save_states_to_file(self):
        """Save all zone camera states to file"""
        try:
            os.makedirs(os.path.dirname(self.states_file), exist_ok=True)
            with open(self.states_file, 'w') as f:
                json.dump(self.zone_states, f, indent=2)
        except Exception as e:
            print(f"[CAMERA] Could not save states: {e}")
    
    def load_states_from_file(self):
        """Load zone camera states from file"""
        try:
            if os.path.exists(self.states_file):
                with open(self.states_file, 'r') as f:
                    self.zone_states = json.load(f)
                print(f"[CAMERA] Loaded {len(self.zone_states)} zone states")
        except Exception as e:
            print(f"[CAMERA] Could not load states: {e}")
            self.zone_states = {}
    
    def center_on_point(self, x, y):
        """Center the view on a specific point"""
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready, try again
            self.canvas.after(50, lambda: self.center_on_point(x, y))
            return
        
        # Get current bbox to check scroll region
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
            
        # Calculate offset to center the point
        canvas_center_x = canvas_width / 2
        canvas_center_y = canvas_height / 2
        
        # Calculate how much to move everything
        dx = canvas_center_x - x
        dy = canvas_center_y - y
        
        # Move all items
        self.canvas.move("all", dx, dy)
        
        # Update scroll region after moving
        self.update_scroll_region()
        
        # Update position tracking
        self.position = (x, y)
    
    def fit_to_content(self, padding=50):
        """Fit all content in view with proper zoom and centering"""
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        
        # Get canvas size
        self.canvas.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready, try again
            self.canvas.after(50, lambda: self.fit_to_content(padding))
            return
        
        # Content bounds
        x1, y1, x2, y2 = bbox
        content_width = x2 - x1
        content_height = y2 - y1
        
        if content_width <= 0 or content_height <= 0:
            return
        
        # Reset to zoom 1.0 first to get accurate measurements
        if self.zoom != 1.0:
            self.canvas.scale("all", 0, 0, 1/self.zoom, 1/self.zoom)
            self.zoom = 1.0
        
        # Calculate zoom needed to fit content with padding
        scale_x = (canvas_width - padding * 2) / content_width
        scale_y = (canvas_height - padding * 2) / content_height
        new_zoom = min(scale_x, scale_y, 2.0)  # Cap at 2.0 to avoid too much zoom
        
        # Apply zoom from origin (0,0)
        if new_zoom != 1.0:
            self.canvas.scale("all", 0, 0, new_zoom, new_zoom)
            self.zoom = new_zoom
        
        # Get new bbox after scaling
        new_bbox = self.canvas.bbox("all")
        if new_bbox:
            # Calculate offset to center content
            content_center_x = (new_bbox[0] + new_bbox[2]) / 2
            content_center_y = (new_bbox[1] + new_bbox[3]) / 2
            canvas_center_x = canvas_width / 2
            canvas_center_y = canvas_height / 2
            
            # Move to center
            offset_x = canvas_center_x - content_center_x
            offset_y = canvas_center_y - content_center_y
            self.canvas.move("all", offset_x, offset_y)
        
        # Update scroll region with extra space for panning
        final_bbox = self.canvas.bbox("all")
        if final_bbox:
            extra = 2000  # Extra space for panning
            self.canvas.configure(scrollregion=(
                final_bbox[0] - extra,
                final_bbox[1] - extra,
                final_bbox[2] + extra,
                final_bbox[3] + extra
            ))
    
    def reset_view(self):
        """Reset zoom and position"""
        # Reset zoom
        self.canvas.scale("all", 0, 0, 1/self.zoom, 1/self.zoom)
        self.zoom = 1.0
        
        # Reset position
        self.position = (0, 0)
        self.update_scroll_region()