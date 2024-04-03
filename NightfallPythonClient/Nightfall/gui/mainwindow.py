#mainwindow.py
import tkinter as tk
from tkinter import ttk
from network.connection import MUDConnection
from config.settings import load_config
from core.map import MapViewer

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.initialize_window()
        self.update_buffer = []
        self.update_pending = False
        self.config = load_config()
        self.setup_ui()
        self.setup_bindings()
        self.connection = MUDConnection(self.display_message, self.on_login_success)
        self.connection.connect()
        self.map_viewer = None

    def initialize_window(self):
        self.root.title("MUD Client with Map")
        self.root.geometry("1200x600")

    def setup_ui(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        console_frame = ttk.Frame(pane, width=400)
        self.setup_console_ui(console_frame)
        pane.add(console_frame, weight=1)

        map_frame = ttk.Frame(pane, width=600)
        self.map_viewer = MapViewer(map_frame, pane)
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
        colors = {}
        if self.config.has_section('ANSIColors'):
            for code in self.config['ANSIColors']:
                colors[code] = self.config.get('ANSIColors', code)
        return colors

    def create_color_tags(self):
        for code, color in self.ansi_colors.items():
            self.text_area.tag_configure(code, foreground=color)

    def send_input(self, event):
        input_text = self.input_area.get()
        self.connection.send(input_text)
        self.input_area.delete(0, tk.END)

    def debug_ansi_codes(self, text):
        print(" ".join(f"{ord(c):02x}" for c in text))

    def ANSI_Color_Text(self, message):
        self.ansi_colors = self.load_ansi_colors()
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

    def display_message(self, message):
        self.ANSI_Color_Text(message)

    def on_login_success(self):
        initial_commands = self.config.get('InitialCommands', 'commands').split(',')
        for command in initial_commands:
            self.connection.send(command.strip())

    def setup_console_ui(self, console_frame):
        bg_color = self.config.get('Font', 'background_color')
        font_color = self.config.get('Font', 'color')
        self.text_area = tk.Text(console_frame, wrap=tk.WORD, state='disabled', bg=bg_color, fg=font_color)
        self.text_area.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.ansi_colors = self.load_ansi_colors()
        self.create_color_tags()
        self.input_area = tk.Entry(console_frame)
        self.input_area.pack(fill=tk.X, side=tk.BOTTOM)
        self.input_area.bind("<Return>", self.send_input)
        self.text_area.bind("<1>", lambda event: self.input_area.focus())
        self.text_area.bind("<Control-c>", self.copy_text)

    def setup_zone_ui(self, zone_frame):
        self.zone_listbox = tk.Listbox(zone_frame, height=10)
        self.zone_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.populate_zones()
        self.zone_listbox.bind('<<ListboxSelect>>', self.map_viewer.on_zone_select)
