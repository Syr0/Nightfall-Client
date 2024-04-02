#mainwindow.py
import tkinter as tk
from tkinter.font import Font
from tkfontchooser import askfont
from network.connection import MUDConnection
from config.settings import load_config, save_config
import re

class MainWindow:
    def __init__(self, root):
        self.config = load_config()
        self.root = root
        self.root.title("MUD Client")
        self.root.geometry("800x600")

        
        font_name = self.config.get('Font', 'name')
        font_size = self.config.getint('Font', 'size')
        font_color = self.config.get('Font', 'color')
        bg_color = self.config.get('Font', 'background_color')
        self.current_font = Font(family=font_name, size=font_size)

        
        self.text_area = tk.Text(root, bg=bg_color, fg=font_color, font=self.current_font, cursor="xterm")
        self.text_area.tag_configure("red", foreground="#ff0000")
        self.text_area.tag_configure("green", foreground="#00ff00")

        
        font_name = self.config.get('Font', 'name')
        font_size = self.config.getint('Font', 'size')
        font_color = self.config.get('Font', 'color')
        bg_color = self.config.get('Font', 'background_color')
        self.current_font = Font(family=font_name, size=font_size)

        
        self.text_area = tk.Text(root, bg=bg_color, fg=font_color, font=self.current_font, cursor="xterm")
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.bind("<Key>", self.on_key_press)
        self.text_area.tag_configure("input", background=bg_color, foreground=font_color)

        
        self.toolbar = tk.Frame(root, height=20)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.font_button = tk.Button(self.toolbar, text="F", command=self.choose_font, width=2, height=1)
        self.font_button.pack(side=tk.LEFT, padx=2, pady=2)

        self.connection = MUDConnection(self.display_message)
        self.connection.connect()

    def display_message(self, message):
        message = message.replace('\x1b[31m', '<red>').replace('\x1b[32m', '<green>').replace('\x1b[0m',
                                                                                           '</color>')  # Reset color to default
        parts = re.split('(<[^>]+>|</color>)', message)
        apply_color = None
        for part in parts:
            if part == '<red>' or part == '<green>':
                apply_color = part[1:-1]
            elif part == '</color>':
                apply_color = None
            else:
                if apply_color:
                    self.text_area.insert(tk.END, part, apply_color)
                else:
                    self.text_area.insert(tk.END, part)
        self.text_area.see(tk.END)

    def choose_font(self):
        font = askfont(self.root)
        if font:
            
            self.current_font.config(**font)
            
            self.config.set('Font', 'name', font['family'])
            self.config.set('Font', 'size', str(font['size']))
            save_config(self.config)
            self.text_area.config(font=self.current_font)

    def on_key_press(self, event):
        
        if event.char.isprintable():
            pass
        return "break"  