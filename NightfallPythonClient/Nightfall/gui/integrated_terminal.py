# integrated_terminal.py
import tkinter as tk

class IntegratedTerminal:
    """Terminal with integrated input handling - no separate input field"""
    
    def __init__(self, parent, theme_manager, connection, trigger_commands):
        self.parent = parent
        self.theme_manager = theme_manager
        self.connection = connection
        self.trigger_commands = trigger_commands
        
        # Create text widget
        theme = self.theme_manager.get_theme()
        self.text = tk.Text(parent, wrap=tk.WORD)
        self.apply_theme()
        self.text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Input handling
        self.input_start = None
        self.current_input = ""
        self.command_history = []
        self.history_index = -1
        self.login_mode = None
        self.entered_username = None
        self.awaiting_response = False
        self.last_command = None
        
        # Setup bindings
        self.setup_bindings()
        
        # Create color tags
        self.create_color_tags()
        
        # Start with prompt
        self.add_prompt()
        
    def setup_bindings(self):
        """Setup all key bindings for integrated terminal"""
        self.text.bind("<Return>", self.handle_return)
        self.text.bind("<BackSpace>", self.handle_backspace)
        self.text.bind("<Delete>", self.handle_delete)
        self.text.bind("<Key>", self.handle_key)
        self.text.bind("<Control-c>", self.handle_copy)
        self.text.bind("<Control-v>", self.handle_paste)
        self.text.bind("<Control-a>", self.select_input)
        self.text.bind("<Up>", self.history_up)
        self.text.bind("<Down>", self.history_down)
        self.text.bind("<Home>", self.go_to_input_start)
        self.text.bind("<End>", self.go_to_end)
        self.text.bind("<Left>", self.handle_left)
        self.text.bind("<Right>", self.handle_right)
        self.text.bind("<Control-Left>", self.word_left)
        self.text.bind("<Control-Right>", self.word_right)
        
    def apply_theme(self):
        """Apply current theme to terminal"""
        theme = self.theme_manager.get_theme()['console']
        config = theme.copy()
        if 'font' in config:
            self.text.config(font=config.pop('font'))
        self.text.config(**config)
        
    def create_color_tags(self):
        """Create ANSI color tags"""
        theme = self.theme_manager.get_theme()
        ansi_colors = theme['ansi_colors']
        
        for code, color in ansi_colors.items():
            if code != 'command':
                self.text.tag_configure(code, foreground=color)
        
        # Command color
        command_color = ansi_colors.get('command', '#FFA500')
        self.text.tag_configure('command', foreground=command_color)
        self.text.tag_configure('prompt', foreground=command_color, font=('Consolas', 10, 'bold'))
        
    def add_prompt(self):
        """Add a new prompt"""
        self.text.insert("end", "> ", 'prompt')
        self.input_start = self.text.index("end-1c")
        self.text.mark_set("input_start", self.input_start)
        self.text.mark_set("insert", "end")
        self.text.see("end")
        
    def handle_return(self, event):
        """Process return key - send command"""
        if not self.input_start:
            return "break"
            
        # Get input text
        input_text = self.text.get(self.input_start, "end-1c")
        
        if input_text.strip():
            # Add newline
            self.text.insert("end", "\n")
            
            # Handle based on mode
            if self.login_mode == 'username':
                self.entered_username = input_text
                self.connection.user = input_text
                self.connection.send(input_text)
                self.connection.login_state = 'password_next'
            elif self.login_mode == 'password':
                # Hide password in display
                self.text.delete(self.input_start, "end-1c")
                self.text.insert(self.input_start, "*" * len(input_text))
                self.text.insert("end", "\n")
                self.connection.password = input_text
                self.connection.send(input_text)
                self.connection.login_state = 'checking'
                if self.entered_username:
                    self.connection.save_credentials(self.entered_username, input_text)
            else:
                # Normal command
                cmd = input_text.split()[0] if input_text.split() else ""
                if any(t for t in self.trigger_commands if t.startswith(cmd)):
                    self.awaiting_response = True
                    self.last_command = cmd
                self.connection.send(input_text)
                self.command_history.append(input_text)
                self.history_index = -1
                
        self.input_start = None
        return "break"
        
    def handle_backspace(self, event):
        """Handle backspace - don't delete prompt"""
        if self.input_start:
            cursor = self.text.index("insert")
            if self.text.compare(cursor, "<=", self.input_start):
                return "break"
                
    def handle_delete(self, event):
        """Handle delete key"""
        if self.input_start:
            cursor = self.text.index("insert")
            if self.text.compare(cursor, "<", self.input_start):
                return "break"
                
    def handle_key(self, event):
        """Handle regular key press"""
        # Allow control combinations
        if event.state & 0x4:  # Control key
            return
            
        # Check if we're before the prompt
        if self.input_start:
            cursor = self.text.index("insert")
            if self.text.compare(cursor, "<", self.input_start):
                # Move to end if trying to type before prompt
                self.text.mark_set("insert", "end")
                
        # Allow printable characters
        if event.char and event.char.isprintable():
            return
            
        # Block other special keys except navigation
        if event.keysym not in ['Left', 'Right', 'Home', 'End']:
            return "break"
            
    def handle_left(self, event):
        """Handle left arrow"""
        if self.input_start:
            cursor = self.text.index("insert")
            if self.text.compare(cursor, "<=", self.input_start):
                return "break"
                
    def handle_right(self, event):
        """Handle right arrow"""
        return  # Allow normal behavior
        
    def word_left(self, event):
        """Move cursor one word left"""
        if self.input_start:
            # Find word boundary
            cursor = self.text.index("insert")
            if self.text.compare(cursor, ">", self.input_start):
                # Move to previous word
                self.text.mark_set("insert", f"{cursor} -1c wordstart")
                if self.text.compare("insert", "<", self.input_start):
                    self.text.mark_set("insert", self.input_start)
        return "break"
        
    def word_right(self, event):
        """Move cursor one word right"""
        self.text.mark_set("insert", "insert wordend")
        return "break"
        
    def handle_copy(self, event):
        """Copy selected text"""
        try:
            selected = self.text.get("sel.first", "sel.last")
            self.text.clipboard_clear()
            self.text.clipboard_append(selected)
        except tk.TclError:
            pass
        return "break"
        
    def handle_paste(self, event):
        """Paste text at cursor"""
        try:
            text = self.text.clipboard_get()
            if self.input_start:
                cursor = self.text.index("insert")
                if self.text.compare(cursor, ">=", self.input_start):
                    self.text.insert("insert", text)
        except:
            pass
        return "break"
        
    def select_input(self, event):
        """Select all input text"""
        if self.input_start:
            self.text.tag_remove("sel", "1.0", "end")
            self.text.tag_add("sel", self.input_start, "end-1c")
        return "break"
        
    def go_to_input_start(self, event):
        """Move cursor to start of input"""
        if self.input_start:
            self.text.mark_set("insert", self.input_start)
        return "break"
        
    def go_to_end(self, event):
        """Move cursor to end"""
        self.text.mark_set("insert", "end-1c")
        return "break"
        
    def history_up(self, event):
        """Navigate command history up"""
        if not self.command_history or not self.input_start:
            return "break"
            
        if self.history_index == -1:
            # Save current input
            self.current_input = self.text.get(self.input_start, "end-1c")
            
        self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        
        # Replace input with history
        self.text.delete(self.input_start, "end-1c")
        self.text.insert(self.input_start, self.command_history[-(self.history_index + 1)])
        self.text.mark_set("insert", "end-1c")
        
        return "break"
        
    def history_down(self, event):
        """Navigate command history down"""
        if not self.command_history or not self.input_start:
            return "break"
            
        self.history_index = max(self.history_index - 1, -1)
        
        self.text.delete(self.input_start, "end-1c")
        if self.history_index == -1:
            # Restore saved input
            self.text.insert(self.input_start, self.current_input)
        else:
            # Show history command
            self.text.insert(self.input_start, self.command_history[-(self.history_index + 1)])
            
        self.text.mark_set("insert", "end-1c")
        return "break"
        
    def append_output(self, text, color_tag=None):
        """Append output to terminal (before prompt)"""
        if self.input_start:
            # Insert before prompt
            insert_pos = self.text.index(f"{self.input_start} -2c")
            if color_tag:
                self.text.insert(insert_pos, text, color_tag)
            else:
                self.text.insert(insert_pos, text)
            # Update input start position
            self.input_start = self.text.index("input_start")
        else:
            # No prompt, insert at end
            if color_tag:
                self.text.insert("end", text, color_tag)
            else:
                self.text.insert("end", text)
                
        self.text.see("end")
        
    def set_login_mode(self, mode):
        """Set login mode"""
        self.login_mode = mode
        if mode == 'username':
            self.append_output("\n[Enter username]\n", 'command')
        elif mode == 'password':
            self.append_output("\n[Enter password]\n", 'command')
        self.add_prompt()
        
    def on_login_success(self):
        """Handle successful login"""
        self.login_mode = None
        self.append_output("\n[Login successful]\n", 'command')
        
    def focus(self):
        """Focus the terminal"""
        self.text.focus_set()