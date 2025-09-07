#mainwindow.py
import tkinter as tk
from tkinter import ttk
from network.connection import MUDConnection
from config.settings import load_config
from map.map import MapViewer
from core.positionfinder import AutoWalker

class MainWindow:
    def __init__(self, root):
        self.update_position_active = None
        self.root = root
        self.update_buffer = []
        self.update_pending = False
        self.command_history = []
        self.command_history_index = -1
        self.awaiting_response_for_command = False
        self.ansi_colors = {}
        self.login_mode = None  # 'username' or 'password'
        self.entered_username = None

        self.config = load_config()
        self.load_ansi_colors()

        self.command_color = self.config.get('ANSIColors', 'OwnCommandsColor', fallback='#FFA500')

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
    def initialize_window(self):
        self.root.title("MUD Client with map")
        self.root.geometry("1200x600")

    def load_trigger_commands(self):
        commands_str = self.config.get('TriggerCommands', 'commands',
                                       fallback="l,look,n,w,s,e,ne,nw,se,sw,northwest,northeast,southeast,southwest,north,west,east,south,up,down,u,d,enter,leave,Your feet try to run away with you ...")
        self.trigger_commands = [cmd.strip() for cmd in commands_str.split(',')]
        self.room_reload_command = self.config.get('TriggerCommands', 'RoomReload', fallback='look')

    def setup_ui(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        console_frame = ttk.Frame(pane, width=400)
        self.setup_console_ui(console_frame)
        pane.add(console_frame, weight=1)

        map_frame = ttk.Frame(pane, width=600)
        self.map_viewer = MapViewer(map_frame, pane, self.root)
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

    def on_login_success(self):
        self.login_mode = None
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, "\n[Login successful]\n", 'command')
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)
        
        # Save credentials if they were entered manually
        if self.entered_username and not self.connection.user:
            # Get password from input if it was just entered
            self.connection.save_credentials(self.entered_username, self.connection.password or '')
        
        # Send look command after a longer delay to ensure login is complete
        def send_look():
            print("[Login] Sending automatic 'look' command")
            self.awaiting_response_for_command = True
            self.last_command = 'look'
            self.connection.send('look')
        
        # Wait 2 seconds for login to fully complete
        self.root.after(2000, send_look)
        
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
            self.text_area.config(state='normal')
            self.text_area.insert(tk.END, "\n[Enter username]\n", 'command')
            self.text_area.config(state='disabled')
        elif prompt_type == 'password':
            self.text_area.config(state='normal')
            self.text_area.insert(tk.END, "\n[Enter password]\n", 'command')
            self.text_area.config(state='disabled')
        self.text_area.see(tk.END)
        self.input_area.focus_set()

    def load_ansi_colors(self):
        # Standard ANSI color codes
        self.ansi_colors = {
            '30': '#000000',  # Black
            '31': '#CC0000',  # Red
            '32': '#00CC00',  # Green  
            '33': '#CCCC00',  # Yellow
            '34': '#0000CC',  # Blue
            '35': '#CC00CC',  # Magenta
            '36': '#00CCCC',  # Cyan
            '37': '#CCCCCC',  # White
            '90': '#555555',  # Bright Black
            '91': '#FF0000',  # Bright Red
            '92': '#00FF00',  # Bright Green
            '93': '#FFFF00',  # Bright Yellow
            '94': '#0000FF',  # Bright Blue
            '95': '#FF00FF',  # Bright Magenta
            '96': '#00FFFF',  # Bright Cyan
            '97': '#FFFFFF',  # Bright White
        }
        # Add custom colors from config
        if self.config.has_section('ANSIColors'):
            for code, color in self.config['ANSIColors'].items():
                if code != 'owncommandscolor':
                    self.ansi_colors[code] = color
    def create_color_tags(self):
        for code, color in self.ansi_colors.items():
            self.text_area.tag_configure(code, foreground=color)
        self.text_area.tag_configure('command', foreground=self.command_color)
        # Create default highlight tag
        self.text_area.tag_configure('highlight_default', foreground='#AAAAAA')

    def send_input(self, event):
        input_text = self.input_area.get().strip()
        if input_text:
            # Handle login mode
            if self.login_mode == 'username':
                self.entered_username = input_text
                self.connection.user = input_text
                self.connection.send(input_text)
                self.connection.login_state = 'password_next'
                self.text_area.config(state='normal')
                self.text_area.insert(tk.END, f"> {input_text}\n", 'command')
                self.text_area.config(state='disabled')
            elif self.login_mode == 'password':
                self.connection.password = input_text
                self.connection.send(input_text)
                self.connection.login_state = 'checking'
                self.text_area.config(state='normal')
                self.text_area.insert(tk.END, "> ***\n", 'command')  # Hide password
                self.text_area.config(state='disabled')
                # Save credentials after entering them
                if self.entered_username:
                    self.connection.save_credentials(self.entered_username, input_text)
            else:
                # Normal command mode
                if any(cmd for cmd in self.trigger_commands if cmd.startswith(input_text.split()[0])):
                    self.awaiting_response_for_command = True
                    self.last_command = input_text.split()[0]  # Store the command
                self.connection.send(input_text)
                self.text_area.config(state='normal')
                self.text_area.insert(tk.END, f"> {input_text}\n", 'command')
                self.text_area.config(state='disabled')
                self.command_history.append(input_text)
                self.command_history_index = -1
            
            self.text_area.see(tk.END)
        self.input_area.delete(0, tk.END)

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
        if self.highlight_info and self.highlight_info.get('ranges'):
            # Check if this text segment overlaps with any highlight ranges
            highlighted_parts = []
            current_idx = 0
            
            for range_start, range_end in self.highlight_info['ranges']:
                if range_end <= start_pos or range_start >= end_pos:
                    continue  # No overlap
                
                # Calculate overlap
                overlap_start = max(0, range_start - start_pos)
                overlap_end = min(len(text), range_end - start_pos)
                
                if overlap_start > current_idx:
                    # Add non-highlighted part before this range
                    highlighted_parts.append((text[current_idx:overlap_start], color_tag, False))
                
                # Add highlighted part
                highlighted_parts.append((text[overlap_start:overlap_end], color_tag, True))
                current_idx = overlap_end
            
            # Add remaining non-highlighted text
            if current_idx < len(text):
                highlighted_parts.append((text[current_idx:], color_tag, False))
            
            # Add all parts to buffer
            for part_text, part_color, is_highlighted in highlighted_parts:
                if is_highlighted:
                    # Use a lighter version of the color for highlighting
                    highlight_tag = self._get_highlight_tag(part_color)
                    self.update_buffer.append((part_text, highlight_tag))
                else:
                    self.update_buffer.append((part_text, part_color))
        else:
            # No highlighting, add normally
            self.update_buffer.append((text, color_tag))
    
    def _get_highlight_tag(self, base_color):
        """Get or create a lighter version of a color tag for highlighting"""
        if not base_color:
            return 'highlight_default'
        
        highlight_tag = f'highlight_{base_color}'
        
        # Create the highlight tag if it doesn't exist
        if highlight_tag not in self.ansi_colors:
            # Get base color or use white as default
            base = self.ansi_colors.get(base_color, '#FFFFFF')
            
            # Make color lighter by blending with white
            if base.startswith('#'):
                r = int(base[1:3], 16)
                g = int(base[3:5], 16)
                b = int(base[5:7], 16)
                
                # Blend with white (increase each component by 30%)
                r = min(255, r + int((255 - r) * 0.3))
                g = min(255, g + int((255 - g) * 0.3))
                b = min(255, b + int((255 - b) * 0.3))
                
                lighter = f'#{r:02x}{g:02x}{b:02x}'
            else:
                lighter = '#AAAAAA'  # Default light grey
            
            self.ansi_colors[highlight_tag] = lighter
            # Configure the tag in text area
            self.text_area.tag_configure(highlight_tag, foreground=lighter)
        
        return highlight_tag
    
    def apply_description_highlighting(self, highlight_info):
        """Apply highlighting information from position finder"""
        # Only apply if similarity is high enough (already filtered in positionfinder)
        if highlight_info and highlight_info.get('similarity', 0) >= 0.9:
            self.highlight_info = highlight_info
            print(f"[Highlight] Applying highlight with {highlight_info['similarity']:.1%} similarity")
        else:
            self.highlight_info = None  # Clear highlighting for poor matches

    def schedule_update(self):
        if not self.update_pending:
            self.update_pending = True
            self.root.after(100, self.update_text_area)

    def update_text_area(self):
        self.text_area.config(state='normal')
        for text, color_tag in self.update_buffer:
            if color_tag and color_tag in self.ansi_colors:
                self.text_area.insert(tk.END, text, color_tag)
            else:
                self.text_area.insert(tk.END, text)
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)
        self.update_buffer = []
        self.update_pending = False

    def handle_message(self, message):
        # Store raw message for highlighting
        self.last_message = message
        self.ANSI_Color_Text(message)
        # Always analyze for position if tracking is active
        if self.awaiting_response_for_command and self.auto_walker.is_active():
            # Check if this was a look command and message is long enough to be a room description
            is_look = hasattr(self, 'last_command') and self.last_command in ['l', 'look']
            # Only process if it's a real room description (not login messages)
            if len(message) > 150 or 'There' in message and 'exit' in message:
                # Give the response analyzer the full message for better matching
                self.root.after(100, lambda: self.auto_walker.analyze_response(message, is_look))
                self.awaiting_response_for_command = False
            elif is_look:
                print(f"[Position] Ignoring short response ({len(message)} chars) - not a room description")

    def setup_console_ui(self, console_frame):
        bg_color = self.config.get('Font', 'background_color', fallback='#000000')  # Black as fallback
        font_color = self.config.get('Font', 'color', fallback='#FFFFFF')  # White as fallback
        # Use Consolas font for better Unicode/box-drawing support
        self.text_area = tk.Text(console_frame, wrap=tk.WORD, state='disabled', 
                                bg=bg_color, fg=font_color, font=('Consolas', 10))
        self.text_area.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.create_color_tags()
        self.input_area = tk.Entry(console_frame, font=('Consolas', 10))
        self.input_area.pack(fill=tk.X, side=tk.BOTTOM)
        self.input_area.bind("<Return>", self.send_input)
        self.text_area.bind("<1>", lambda event: self.input_area.focus())
        self.text_area.bind("<Control-c>", self.copy_text)
        self.input_area.bind("<Up>", self.cycle_command_history_up)
        self.input_area.bind("<Down>", self.cycle_command_history_down)

    def setup_zone_ui(self, zone_frame):
        self.zone_listbox = tk.Listbox(zone_frame, height=10)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.zone_listbox.bind('<<ListboxSelect>>', self.map_viewer.on_zone_select)

    def setup_toolbar(self):
        bg_color = self.config.get('Visuals', 'BackgroundColor', fallback='white')
        self.toolbar = tk.Frame(self.map_viewer.this.master, bd=1, relief=tk.RAISED, bg=bg_color)

        # Only level controls, tracking is always on
        self.level_up_btn = tk.Button(self.toolbar, text="Level Up", command=self.level_up, width=10, height=1)
        self.level_up_btn.pack(side=tk.LEFT, padx=2, pady=2)
        self.level_down_btn = tk.Button(self.toolbar, text="Level Down", command=self.level_down, width=10, height=1)
        self.level_down_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.toolbar.pack(side=tk.TOP, fill=tk.X, before=self.map_viewer.this)

    def level_up(self):
        self.map_viewer.change_level(1)

    def level_down(self):
        self.map_viewer.change_level(-1)

    # Tracking is always on, no toggle needed

    def cycle_command_history_up(self, event):
        if self.command_history:
            if self.command_history_index == -1:
                self.current_input = self.input_area.get()
            self.command_history_index += 1
            if self.command_history_index >= len(self.command_history):
                self.command_history_index = len(self.command_history) - 1
            command = self.command_history[-self.command_history_index - 1]
            self.input_area.delete(0, tk.END)
            self.input_area.insert(0, command)
        return "break"

    def cycle_command_history_down(self, event):
        if self.command_history:
            self.command_history_index -= 1
            if self.command_history_index < -1:
                self.command_history_index = -1
                self.input_area.delete(0, tk.END)
                if self.command_history_index == -1:
                    self.input_area.insert(0, self.current_input)
                return "break"
            command = self.command_history[-self.command_history_index - 1]
            self.input_area.delete(0, tk.END)
            self.input_area.insert(0, command)
        return "break"
