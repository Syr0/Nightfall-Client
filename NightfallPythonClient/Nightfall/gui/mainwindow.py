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

        self.config = load_config()
        self.load_ansi_colors()

        self.command_color = self.config.get('ANSIColors', 'OwnCommandsColor', fallback='#FFA500')

        self.initialize_window()
        self.load_trigger_commands()
        self.setup_bindings()
        self.setup_ui()
        self.setup_toolbar()

        self.auto_walker = AutoWalker(self.map_viewer)
        self.connection = MUDConnection(self.handle_message, self.on_login_success)
        self.connection.connect()
    def initialize_window(self):
        self.root.title("MUD Client with map")
        self.root.geometry("1200x600")

    def load_trigger_commands(self):
        commands_str = self.config.get('TriggerCommands', 'commands',
                                       fallback="l,look,n,w,s,e,north,west,east,south,up,down,u,d,enter,leave")
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
        initial_commands = self.config.get('InitialCommands', 'commands').split(',')
        for command in initial_commands:
            self.connection.send(command.strip())

    def load_ansi_colors(self):
        self.ansi_colors = {}
        if self.config.has_section('ANSIColors'):
            for code, color in self.config['ANSIColors'].items():
                self.ansi_colors[code] = color
    def create_color_tags(self):
        for code, color in self.ansi_colors.items():
            self.text_area.tag_configure(code, foreground=color)
        self.text_area.tag_configure('command', foreground=self.command_color)

    def send_input(self, event):
        input_text = self.input_area.get().strip()
        if input_text:
            if any(cmd for cmd in self.trigger_commands if cmd.startswith(input_text.split()[0])):
                self.awaiting_response_for_command = True
            self.connection.send(input_text)

            self.text_area.config(state='normal')
            self.text_area.insert(tk.END, f"> {input_text}\n", 'command')
            self.text_area.config(state='disabled')
            self.text_area.see(tk.END)
            self.command_history.append(input_text)
            self.command_history_index = -1
        self.input_area.delete(0, tk.END)

    def ANSI_Color_Text(self, message):
        current_color = None
        buffer = ""
        i = 0
        while i < len(message):
            if message[i] == '\x1b' and message[i + 1:i + 2] == '[':
                end_idx = message.find('m', i)
                color_code = message[i + 2:end_idx]
                if color_code == '0':
                    if buffer:
                        self.append_to_buffer(buffer, current_color)
                        buffer = ""
                    current_color = None
                elif color_code in self.ansi_colors:
                    if buffer:
                        self.append_to_buffer(buffer, current_color)
                        buffer = ""
                    current_color = color_code
                i = end_idx
            else:
                buffer += message[i]
            i += 1

        if buffer:
            self.append_to_buffer(buffer, current_color)
        self.schedule_update()

    def append_to_buffer(self, text, color_tag=None):
        self.update_buffer.append((text, color_tag))

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
        self.ANSI_Color_Text(message)
        if self.awaiting_response_for_command:
            self.auto_walker.analyze_response(message)
            self.awaiting_response_for_command = False

    def on_login_success(self):
        initial_commands = self.config.get('InitialCommands', 'commands').split(',')
        for command in initial_commands:
            self.connection.send(command.strip())

    def setup_console_ui(self, console_frame):
        bg_color = self.config.get('Font', 'background_color')
        font_color = self.config.get('Font', 'color')
        self.text_area = tk.Text(console_frame, wrap=tk.WORD, state='disabled', bg=bg_color, fg=font_color)
        self.text_area.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.create_color_tags()
        self.input_area = tk.Entry(console_frame)
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
        self.update_pos_toggle_btn = tk.Button(self.toolbar, text="Enable Tracking", bg="lightgrey",
                                               command=self.toggle_update_position, width=15, height=1)
        self.update_pos_toggle_btn.pack(side=tk.LEFT, padx=2, pady=2)
        self.toolbar.pack(side=tk.TOP, fill=tk.X, before=self.map_viewer.this)

    def toggle_update_position(self):
        self.update_position_active = not self.update_position_active
        self.auto_walker.toggle_active()
        if self.auto_walker.is_active():
            self.update_pos_toggle_btn.config(bg="green")
            self.connection.send(self.room_reload_command)
        else:
            self.update_pos_toggle_btn.config(bg="lightgrey")

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
