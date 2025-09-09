# themes.py
import json
import os

class ThemeManager:
    def __init__(self):
        self.current_theme = "paper"  # Default theme
        self.themes = {
            "monokai": {
                "name": "Monokai",
                "console": {
                    "bg": "#272822",
                    "fg": "#F8F8F2",
                    "insertbackground": "#F8F8F2",
                    "selectbackground": "#49483E",
                    "font": ("Consolas", 10),  # Monospace font
                },
                "input": {
                    "bg": "#3E3D32",
                    "fg": "#F8F8F2",
                    "insertbackground": "#F8F8F2",
                    "font": ("Consolas", 10),  # Monospace font
                    "relief": "flat",
                    "bd": 0,
                },
                "map": {
                    "bg": "#272822",
                    "room_color": "#66D9EF",
                    "room_highlight": "#F92672",
                    "connection_color": "#75715E",
                    "zone_note_color": "#A6E22E",
                    "position_indicator": "#3E3D32",  # No alpha in tkinter
                    "position_outline": "#49483E",
                },
                "toolbar": {
                    "bg": "#3E3D32",
                    "fg": "#F8F8F2",
                    "button_bg": "#49483E",
                    "button_fg": "#F8F8F2",
                    "button_active": "#75715E",
                    "relief": "flat",
                },
                "ansi_colors": {
                    "command": "#FD971F",  # Orange for commands
                }
            },
            "dark": {
                "name": "Dark Mode",
                "console": {
                    "bg": "#1E1E1E",
                    "fg": "#D4D4D4",
                    "insertbackground": "#D4D4D4",
                    "selectbackground": "#264F78",
                    "font": ("Consolas", 10),  # Monospace font
                },
                "input": {
                    "bg": "#2D2D30",
                    "fg": "#CCCCCC",
                    "insertbackground": "#CCCCCC",
                    "font": ("Consolas", 10),  # Monospace font
                    "relief": "flat",
                    "bd": 1,
                },
                "map": {
                    "bg": "#252526",
                    "room_color": "#569CD6",
                    "room_highlight": "#C586C0",
                    "connection_color": "#808080",
                    "zone_note_color": "#4EC9B0",
                    "position_indicator": "#3C3C3C",  # No alpha
                    "position_outline": "#5A5A5A",
                },
                "toolbar": {
                    "bg": "#2D2D30",
                    "fg": "#CCCCCC",
                    "button_bg": "#3C3C3C",
                    "button_fg": "#CCCCCC",
                    "button_active": "#094771",
                    "relief": "flat",
                },
                "ansi_colors": {
                    "command": "#CE9178",  # Orange for commands
                }
            },
            "paper": {
                "name": "Paper (Retro)",
                "console": {
                    "bg": "#FAF8F5",
                    "fg": "#3A3A3A",
                    "insertbackground": "#3A3A3A",
                    "selectbackground": "#E8E4DC",
                    "font": ("Courier New", 10),  # Monospace font
                },
                "input": {
                    "bg": "#FFFFFF",
                    "fg": "#2C2C2C",
                    "insertbackground": "#2C2C2C",
                    "font": ("Courier New", 10),  # Monospace font
                    "relief": "groove",
                    "bd": 2,
                },
                "map": {
                    "bg": "#F5F2ED",
                    "room_color": "#4A90E2",
                    "room_highlight": "#E74C3C",
                    "connection_color": "#95A5A6",
                    "zone_note_color": "#27AE60",
                    "position_indicator": "#ECE9E4",  # No alpha
                    "position_outline": "#D5D1C9",
                },
                "toolbar": {
                    "bg": "#E8E4DC",
                    "fg": "#2C2C2C",
                    "button_bg": "#FFFFFF",
                    "button_fg": "#2C2C2C",
                    "button_active": "#D5D1C9",
                    "relief": "raised",
                },
                "ansi_colors": {
                    "command": "#E67E22",  # Orange for commands
                }
            },
            "neon": {
                "name": "Neon Cyberpunk",
                "console": {
                    "bg": "#0A0E27",
                    "fg": "#00FFF0",
                    "insertbackground": "#FF00FF",
                    "selectbackground": "#FF0066",  # No alpha
                    "font": ("Consolas", 10),  # Monospace font
                },
                "input": {
                    "bg": "#1A1E3A",
                    "fg": "#00FF88",
                    "insertbackground": "#FF00FF",
                    "font": ("Consolas", 10),  # Monospace font
                    "relief": "flat",
                    "bd": 2,
                },
                "map": {
                    "bg": "#0D0221",
                    "room_color": "#00FFFF",
                    "room_highlight": "#FF00FF",
                    "connection_color": "#FF0066",  # No alpha
                    "zone_note_color": "#FFFF00",
                    "position_indicator": "#FF00FF",  # No alpha
                    "position_outline": "#00FFFF",
                },
                "toolbar": {
                    "bg": "#1A1E3A",
                    "fg": "#00FFF0",
                    "button_bg": "#2A2E5A",
                    "button_fg": "#00FF88",
                    "button_active": "#FF0066",  # No alpha
                    "relief": "flat",
                },
                "ansi_colors": {
                    "command": "#FF8800",  # Orange for commands
                }
            }
        }
        self.load_theme_preference()
    
    def load_theme_preference(self):
        """Load saved theme preference"""
        pref_file = os.path.join(os.path.dirname(__file__), '../data/theme_preference.json')
        if os.path.exists(pref_file):
            try:
                with open(pref_file, 'r') as f:
                    data = json.load(f)
                    saved_theme = data.get('theme', 'paper')
                    if saved_theme in self.themes:
                        self.current_theme = saved_theme
            except:
                pass
    
    def save_theme_preference(self):
        """Save current theme preference"""
        pref_file = os.path.join(os.path.dirname(__file__), '../data/theme_preference.json')
        os.makedirs(os.path.dirname(pref_file), exist_ok=True)
        with open(pref_file, 'w') as f:
            json.dump({'theme': self.current_theme}, f)
    
    def get_theme(self):
        """Get current theme"""
        return self.themes[self.current_theme]
    
    def set_theme(self, theme_name):
        """Set current theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.save_theme_preference()
            return True
        return False
    
    def get_theme_names(self):
        """Get list of available themes"""
        return [(key, theme["name"]) for key, theme in self.themes.items()]
    
    def apply_theme_to_widget(self, widget, widget_type):
        """Apply theme to a specific widget"""
        # For console, only apply background and font - NEVER touch text colors
        if widget_type == 'console':
            theme = self.get_theme()
            if 'console' in theme:
                console_theme = theme['console']
                # Only apply background and font settings
                if 'bg' in console_theme:
                    widget.config(bg=console_theme['bg'])
                if 'font' in console_theme:
                    widget.config(font=console_theme['font'])
                # DO NOT apply fg color - server controls all text colors
            return
            
        theme = self.get_theme()
        if widget_type in theme:
            config = theme[widget_type].copy()
            # Remove non-config keys
            if 'font' in config:
                widget.config(font=config.pop('font'))
            if 'relief' in config:
                relief = config.pop('relief')
                if hasattr(widget, 'config'):
                    try:
                        widget.config(relief=relief)
                    except:
                        pass
            if 'bd' in config:
                bd = config.pop('bd')
                if hasattr(widget, 'config'):
                    try:
                        widget.config(bd=bd)
                    except:
                        pass
            # Apply remaining config
            if hasattr(widget, 'config'):
                try:
                    widget.config(**config)
                except Exception as e:
                    print(f"[Theme] Could not apply all theme settings to {widget_type}: {e}")