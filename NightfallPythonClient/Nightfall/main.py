# main.py
import os
import sys

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import and run install check
from install import main as install_dependencies
install_dependencies()

from gui.mainwindow import MainWindow
import tkinter as tk

def main():
    root = tk.Tk()
    app = MainWindow(root)
    
    def on_closing():
        # Save camera state before closing
        if hasattr(app, 'map_viewer') and app.map_viewer.displayed_zone_id:
            zone_key = f"{app.map_viewer.displayed_zone_id}_{app.map_viewer.current_level}"
            app.map_viewer.camera.save_zone_state(zone_key)
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
