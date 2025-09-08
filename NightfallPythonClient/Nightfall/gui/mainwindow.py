#mainwindow.py with integrated terminal
import tkinter as tk
from tkinter import ttk
from network.connection import MUDConnection
from config.settings import load_config
from map.map import MapViewer
from core.positionfinder import AutoWalker
from gui.themes import ThemeManager

class MainWindow:
    def __init__(self, root):
        self.update_position_active = None
        self.root = root
        self.update_buffer = []
        self.update_pending = False
        self.command_history = []
        self.command_history_index = -1
        self.saved_input = ""
        self.awaiting_response_for_command = False
        self.ansi_colors = {}
        self.login_mode = None  # 'username' or 'password'
        self.entered_username = None
        self.input_start = None  # Track where input starts in terminal

        self.config = load_config()
        self.theme_manager = ThemeManager()
        self.load_ansi_colors()

        self.command_color = self.theme_manager.get_theme()['ansi_colors'].get('command', '#FFA500')

        self.initialize_window()
        self.load_trigger_commands()
        self.setup_bindings()
        self.setup_ui()
        self.setup_toolbar()

        self.auto_walker = AutoWalker(self.map_viewer)
        self.auto_walker.toggle_active()  # Always enable tracking
        self.map_viewer.parent = self  # Set reference for callbacks
        self.highlight_info = None  # Store current highlight information
        self.connection = MUDConnection(self.handle_message, self.on_login_success, self.on_login_prompt)
        self.connection.connect()
        
        # Show initial prompt
        self.text_area.insert(tk.END, "Connecting to nightfall.org:4242...\n", 'command')
        self.show_prompt()
        
    def initialize_window(self):
        self.root.title("Nightfall MUD Client")
        self.root.geometry("1400x800")
        # Apply theme to root window
        theme = self.theme_manager.get_theme()
        if 'console' in theme:
            self.root.configure(bg=theme['console']['bg'])

    def load_trigger_commands(self):
        commands_str = self.config.get('TriggerCommands', 'commands',
                                       fallback="l,look,n,w,s,e,ne,nw,se,sw,northwest,northeast,southeast,southwest,north,west,east,south,up,down,u,d,enter,leave,Your feet try to run away with you ...")
        self.trigger_commands = [cmd.strip() for cmd in commands_str.split(',')]
        self.room_reload_command = self.config.get('TriggerCommands', 'RoomReload', fallback='look')

    def setup_ui(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        # Use tk.Frame instead of ttk.Frame for theme support
        console_frame = tk.Frame(pane, width=400)
        self.setup_console_ui(console_frame)
        pane.add(console_frame, weight=1)

        # Use tk.Frame for map as well
        theme = self.theme_manager.get_theme()
        map_frame = tk.Frame(pane, width=600, bg=theme['map']['bg'])
        self.map_viewer = MapViewer(map_frame, pane, self.root, self.theme_manager)
        pane.add(map_frame, weight=2)
        self.map_viewer.this.pack(fill=tk.BOTH, expand=True)

    def setup_bindings(self):
        self.root.bind("<Control-c>", lambda event: self.copy_text(event))

    def copy_text(self, event=None):
        try:
            selected_text = self.text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass
        return "break"

    def on_login_success(self):
        self.login_mode = None
        
        # Save credentials if they were entered manually
        if self.entered_username and not self.connection.user:
            # Get password from input if it was just entered
            self.connection.save_credentials(self.entered_username, self.connection.password or '')
        
        # Send look command after login
        def send_look():
            self.awaiting_response_for_command = True
            self.last_command = 'l'
            self.connection.send('l')
        
        # Small delay to let login messages pass
        self.root.after(1000, send_look)
        
        # Execute initial commands if configured
        if self.config.has_option('InitialCommands', 'commands'):
            commands = self.config.get('InitialCommands', 'commands').split(',')
            for cmd in commands:
                if cmd.strip():
                    self.connection.send(cmd.strip())
    
    def on_login_prompt(self, prompt_type):
        """Handle login prompts from the connection"""
        self.login_mode = prompt_type
        if prompt_type == 'username':
            self.text_area.insert(tk.END, "\n[Enter username]\n", 'command')
        elif prompt_type == 'password':
            self.text_area.insert(tk.END, "\n[Enter password]\n", 'command')
        self.text_area.see(tk.END)
        self.show_prompt()

    def load_ansi_colors(self):
        # Get ANSI colors from theme
        theme = self.theme_manager.get_theme()
        self.ansi_colors = theme['ansi_colors'].copy()
        
        # Remove non-ANSI entries
        if 'command' in self.ansi_colors:
            del self.ansi_colors['command']

    def create_color_tags(self):
        for code, color in self.ansi_colors.items():
            self.text_area.tag_configure(code, foreground=color)
        self.text_area.tag_configure('command', foreground=self.command_color)
        # Create default highlight tag
        self.text_area.tag_configure('highlight_default', foreground='#AAAAAA')

    def show_prompt(self):
        """Add command prompt to terminal"""
        self.text_area.insert(tk.END, "> ", 'command')
        self.input_start = self.text_area.index("end-1c")
        self.text_area.mark_set("input_start", self.input_start)
        self.text_area.see(tk.END)

    def handle_return(self, event):
        """Handle Enter key in terminal"""
        if not self.input_start:
            self.show_prompt()
            return "break"
        
        # Get the input text
        input_text = self.text_area.get(self.input_start, "end-1c").strip()
        
        if input_text:
            self.text_area.insert(tk.END, "\n")
            
            # Handle login mode
            if self.login_mode == 'username':
                self.entered_username = input_text
                self.connection.user = input_text
                self.connection.send(input_text)
                self.connection.login_state = 'password_next'
            elif self.login_mode == 'password':
                # Hide password
                self.text_area.delete(self.input_start, "end-1c")
                self.text_area.insert(self.input_start, "*" * len(input_text))
                self.text_area.insert(tk.END, "\n")
                self.connection.password = input_text
                self.connection.send(input_text)
                self.connection.login_state = 'checking'
                # Save credentials after entering them
                if self.entered_username:
                    self.connection.save_credentials(self.entered_username, input_text)
            else:
                # Normal command mode
                first_word = input_text.split()[0] if input_text.split() else ""
                if first_word and any(cmd == first_word for cmd in self.trigger_commands):
                    self.awaiting_response_for_command = True
                    self.last_command = first_word
                self.connection.send(input_text)
                self.command_history.append(input_text)
                self.command_history_index = -1
            
            self.text_area.see(tk.END)
            self.input_start = None
        
        return "break"

    def handle_key(self, event):
        """Handle regular typing in terminal"""
        # Allow Control combinations
        if event.state & 0x4:  # Control key
            return
        
        # Ensure cursor is after prompt
        if self.input_start:
            cursor = self.text_area.index("insert")
            if self.text_area.compare(cursor, "<", self.input_start):
                self.text_area.mark_set("insert", "end")
        
        # Let printable characters through
        if event.char and event.char.isprintable():
            return
        
        # Block special keys except navigation
        if event.keysym not in ['Left', 'Right', 'Home', 'End']:
            return "break"

    def handle_backspace(self, event):
        """Don't allow deleting before prompt"""
        if self.input_start:
            cursor = self.text_area.index("insert")
            if self.text_area.compare(cursor, "<=", self.input_start):
                return "break"

    def paste_text(self, event):
        """Paste text at cursor"""
        try:
            text = self.root.clipboard_get()
            if self.input_start:
                self.text_area.insert("insert", text)
        except:
            pass
        return "break"

    def ANSI_Color_Text(self, message):
        current_color = None
        buffer = ""
        i = 0
        char_position = 0  # Track position without ANSI codes
        
        while i < len(message):
            if i < len(message) - 1 and message[i] == '\x1b' and message[i + 1] == '[':
                # Found ANSI escape sequence
                end_idx = message.find('m', i)
                if end_idx != -1:
                    # Parse color codes (can be multiple separated by semicolons)
                    codes = message[i + 2:end_idx].split(';')
                    for code in codes:
                        if code == '0' or code == '':
                            # Reset
                            if buffer:
                                self.append_to_buffer_with_highlight(buffer, current_color, char_position - len(buffer), char_position)
                                buffer = ""
                            current_color = None
                        elif code in self.ansi_colors:
                            if buffer:
                                self.append_to_buffer_with_highlight(buffer, current_color, char_position - len(buffer), char_position)
                                buffer = ""
                            current_color = code
                    i = end_idx + 1
                else:
                    buffer += message[i]
                    char_position += 1
                    i += 1
            else:
                buffer += message[i]
                char_position += 1
                i += 1

        if buffer:
            self.append_to_buffer_with_highlight(buffer, current_color, char_position - len(buffer), char_position)
        self.schedule_update()

    def append_to_buffer(self, text, color_tag=None):
        self.update_buffer.append((text, color_tag))
    
    def append_to_buffer_with_highlight(self, text, color_tag, start_pos, end_pos):
        """Append text with potential highlighting based on match ranges"""
        self.update_buffer.append((text, color_tag))
    
    def apply_description_highlighting(self, highlight_info):
        """Apply highlighting information from position finder"""
        # Only apply if similarity is high enough (already filtered in positionfinder)
        if highlight_info and highlight_info.get('similarity', 0) >= 0.9:
            self.highlight_info = highlight_info
        else:
            self.highlight_info = None  # Clear highlighting for poor matches

    def schedule_update(self):
        if not self.update_pending:
            self.update_pending = True
            self.root.after(100, self.update_text_area)

    def update_text_area(self):
        # Insert before prompt if exists
        if self.input_start:
            # Get current input
            current_input = self.text_area.get(self.input_start, "end-1c")
            # Delete from start of prompt to end
            self.text_area.delete(f"{self.input_start}-2c", "end")
            
            # Insert buffered text
            for text, color_tag in self.update_buffer:
                if color_tag and color_tag in self.ansi_colors:
                    self.text_area.insert("end", text, color_tag)
                else:
                    self.text_area.insert("end", text)
            
            # Re-add prompt and input
            self.show_prompt()
            self.text_area.insert("end", current_input)
        else:
            # No prompt, just append
            for text, color_tag in self.update_buffer:
                if color_tag and color_tag in self.ansi_colors:
                    self.text_area.insert("end", text, color_tag)
                else:
                    self.text_area.insert("end", text)
        
        self.text_area.see("end")
        self.update_buffer = []
        self.update_pending = False

    def handle_message(self, message):
        # Store raw message for highlighting
        self.last_message = message
        self.ANSI_Color_Text(message)
        
        # Add prompt after message
        if not self.input_start:
            self.text_area.insert("end", "\n")
            self.show_prompt()
        
        # Analyze for position if tracking is active
        if self.awaiting_response_for_command and self.auto_walker.is_active():
            # Clean message of prompts
            clean_message = message.replace("> ", "").strip()
            
            # Check if this was a look command
            is_look = hasattr(self, 'last_command') and self.last_command in ['l', 'look']
            
            # Process if it looks like a room description
            if len(clean_message) > 80:
                self.root.after(100, lambda: self.auto_walker.analyze_response(clean_message, is_look))
                self.awaiting_response_for_command = False

    def setup_console_ui(self, console_frame):
        theme = self.theme_manager.get_theme()
        
        # Create styled frame
        console_frame.configure(bg=theme['console']['bg'])
        
        # Create text area - NOT DISABLED! We type directly in it
        self.text_area = tk.Text(console_frame, wrap=tk.WORD, insertwidth=2)
        self.theme_manager.apply_theme_to_widget(self.text_area, 'console')
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.create_color_tags()
        
        # Bind terminal input keys
        self.text_area.bind("<Return>", self.handle_return)
        self.text_area.bind("<Key>", self.handle_key)
        self.text_area.bind("<BackSpace>", self.handle_backspace)
        self.text_area.bind("<Control-c>", self.copy_text)
        self.text_area.bind("<Control-v>", self.paste_text)
        self.text_area.bind("<Up>", self.cycle_command_history_up)
        self.text_area.bind("<Down>", self.cycle_command_history_down)
        self.text_area.bind("<Home>", lambda e: self.text_area.mark_set("insert", self.input_start) if self.input_start else None)
        self.text_area.bind("<End>", lambda e: self.text_area.mark_set("insert", "end-1c") or "break")
        
        # Focus on terminal
        self.text_area.focus_set()

    def setup_zone_ui(self, zone_frame):
        self.zone_listbox = tk.Listbox(zone_frame, height=10)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.zone_listbox.bind('<<ListboxSelect>>', self.map_viewer.on_zone_select)

    def setup_toolbar(self):
        theme = self.theme_manager.get_theme()['toolbar']
        self.toolbar = tk.Frame(self.map_viewer.this.master, bd=0, bg=theme['bg'])

        # Style buttons
        button_style = {
            'bg': theme['button_bg'],
            'fg': theme['button_fg'],
            'activebackground': theme['button_active'],
            'activeforeground': theme['fg'],
            'relief': theme['relief'],
            'bd': 1,
            'font': ('Segoe UI', 10),
            'cursor': 'hand2'
        }
        
        # Level controls
        self.level_up_btn = tk.Button(self.toolbar, text="▲ Level Up", command=self.level_up, width=12, **button_style)
        self.level_up_btn.pack(side=tk.LEFT, padx=3, pady=5)
        self.level_down_btn = tk.Button(self.toolbar, text="▼ Level Down", command=self.level_down, width=12, **button_style)
        self.level_down_btn.pack(side=tk.LEFT, padx=3, pady=5)
        
        # Add theme switcher (no label)
        self.theme_selector = ttk.Combobox(self.toolbar, values=[name for _, name in self.theme_manager.get_theme_names()], 
                                          width=15, state='readonly')
        self.theme_selector.set(self.theme_manager.get_theme()['name'])
        self.theme_selector.pack(side=tk.RIGHT, padx=5, pady=5)
        self.theme_selector.bind('<<ComboboxSelected>>', self.change_theme)

        self.toolbar.pack(side=tk.TOP, fill=tk.X, before=self.map_viewer.this)

    def level_up(self):
        self.map_viewer.change_level(1)

    def level_down(self):
        self.map_viewer.change_level(-1)

    def cycle_command_history_up(self, event):
        if self.command_history and self.input_start:
            if self.command_history_index == -1:
                # Save current input
                self.saved_input = self.text_area.get(self.input_start, "end-1c")
            
            self.command_history_index = min(self.command_history_index + 1, len(self.command_history) - 1)
            
            # Replace input with history
            self.text_area.delete(self.input_start, "end-1c")
            self.text_area.insert(self.input_start, self.command_history[-(self.command_history_index + 1)])
        return "break"

    def change_theme(self, event):
        """Change the application theme"""
        selected = self.theme_selector.get()
        for key, name in self.theme_manager.get_theme_names():
            if name == selected:
                self.theme_manager.set_theme(key)
                # Refresh UI with new theme
                self.apply_theme()
                break
    
    def apply_theme(self):
        """Apply current theme to all UI elements"""
        theme = self.theme_manager.get_theme()
        
        # Update console
        self.theme_manager.apply_theme_to_widget(self.text_area, 'console')
        
        # Update toolbar
        toolbar_theme = theme['toolbar']
        self.toolbar.config(bg=toolbar_theme['bg'])
        
        button_style = {
            'bg': toolbar_theme['button_bg'],
            'fg': toolbar_theme['button_fg'],
            'activebackground': toolbar_theme['button_active'],
            'activeforeground': toolbar_theme['fg'],
        }
        
        self.level_up_btn.config(**button_style)
        self.level_down_btn.config(**button_style)
        
        # Update ANSI colors
        self.load_ansi_colors()
        self.create_color_tags()
        
        # Update map if exists
        if hasattr(self, 'map_viewer'):
            self.map_viewer.apply_theme(theme['map'])
    
    def cycle_command_history_down(self, event):
        if self.command_history and self.input_start:
            self.command_history_index = max(self.command_history_index - 1, -1)
            
            self.text_area.delete(self.input_start, "end-1c")
            if self.command_history_index == -1:
                # Restore saved input
                self.text_area.insert(self.input_start, self.saved_input)
            else:
                # Show history command
                self.text_area.insert(self.input_start, self.command_history[-(self.command_history_index + 1)])
        return "break"