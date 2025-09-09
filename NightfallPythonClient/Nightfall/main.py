# main.py
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.system("python install.py")

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
            print("[APP] Saved camera state before closing")
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
