# room_customization.py
import json
import os
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

class RoomCustomization:
    def __init__(self):
        self.customizations_file = os.path.join(os.path.dirname(__file__), '../data/room_customizations.json')
        self.customizations = self.load_customizations()
    
    def load_customizations(self):
        """Load room customizations from JSON file"""
        if os.path.exists(self.customizations_file):
            try:
                with open(self.customizations_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Customization] Error loading customizations: {e}")
        return {}
    
    def save_customizations(self):
        """Save room customizations to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.customizations_file), exist_ok=True)
            with open(self.customizations_file, 'w', encoding='utf-8') as f:
                json.dump(self.customizations, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[Customization] Error saving customizations: {e}")
            return False
    
    def get_room_customization(self, room_id):
        """Get customization for a specific room"""
        return self.customizations.get(str(room_id), {})
    
    def set_room_customization(self, room_id, note=None, color=None):
        """Set customization for a specific room"""
        room_id = str(room_id)
        if room_id not in self.customizations:
            self.customizations[room_id] = {}
        
        if note is not None:
            if note.strip():  # Only save non-empty notes
                self.customizations[room_id]['note'] = note
            elif 'note' in self.customizations[room_id]:
                del self.customizations[room_id]['note']
        
        if color is not None:
            if color:  # Only save valid colors
                self.customizations[room_id]['color'] = color
            elif 'color' in self.customizations[room_id]:
                del self.customizations[room_id]['color']
        
        # Remove room entry if no customizations remain
        if not self.customizations[room_id]:
            del self.customizations[room_id]
        
        return self.save_customizations()
    
    def clear_room_customization(self, room_id):
        """Clear all customizations for a room"""
        room_id = str(room_id)
        if room_id in self.customizations:
            del self.customizations[room_id]
            return self.save_customizations()
        return True


class RoomCustomizationDialog:
    def __init__(self, parent, room_id, current_note="", current_color=None):
        self.room_id = room_id
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Room {room_id} Customization")
        self.dialog.geometry("400x300")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Note section
        note_frame = ttk.LabelFrame(self.dialog, text="Room Note", padding=10)
        note_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.note_text = tk.Text(note_frame, height=6, width=40, wrap=tk.WORD)
        self.note_text.pack(fill=tk.BOTH, expand=True)
        if current_note:
            self.note_text.insert('1.0', current_note)
        
        # Color section
        color_frame = ttk.LabelFrame(self.dialog, text="Room Color", padding=10)
        color_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.color_var = tk.StringVar(value=current_color or "")
        self.color_preview = tk.Label(color_frame, text="    ", bg=current_color or "#808080", relief=tk.RAISED)
        self.color_preview.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(color_frame, text="Choose Color", command=self.choose_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(color_frame, text="Clear Color", command=self.clear_color).pack(side=tk.LEFT, padx=5)
        
        # Predefined colors
        colors_frame = ttk.Frame(color_frame)
        colors_frame.pack(side=tk.LEFT, padx=10)
        
        predefined_colors = [
            ("#FF0000", "Red"),
            ("#00FF00", "Green"),
            ("#0000FF", "Blue"),
            ("#FFFF00", "Yellow"),
            ("#FF00FF", "Magenta"),
            ("#00FFFF", "Cyan"),
            ("#FFA500", "Orange"),
            ("#800080", "Purple")
        ]
        
        for color, name in predefined_colors[:4]:
            btn = tk.Button(colors_frame, bg=color, width=3, height=1,
                          command=lambda c=color: self.set_color(c))
            btn.pack(side=tk.LEFT, padx=1)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        
        # Center dialog on parent
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def choose_color(self):
        """Open color chooser dialog"""
        color = colorchooser.askcolor(initialcolor=self.color_var.get() or "#808080")
        if color[1]:  # color[1] is the hex value
            self.set_color(color[1])
    
    def set_color(self, color):
        """Set the selected color"""
        self.color_var.set(color)
        self.color_preview.config(bg=color)
    
    def clear_color(self):
        """Clear the color selection"""
        self.color_var.set("")
        self.color_preview.config(bg="#808080")
    
    def clear_all(self):
        """Clear all customizations"""
        self.note_text.delete('1.0', tk.END)
        self.clear_color()
    
    def save(self):
        """Save and close dialog"""
        note = self.note_text.get('1.0', tk.END).strip()
        color = self.color_var.get()
        self.result = {'note': note, 'color': color}
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel and close dialog"""
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result