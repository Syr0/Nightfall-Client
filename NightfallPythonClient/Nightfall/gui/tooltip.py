#tooltip.py
import tkinter as tk

# In tooltip.py
class ToolTip(object):
    def __init__(self, widget):
        self.widget = widget
        self.tip_window = None
        self.id = None
        self.x = self.y = 0

    def show_tip(self, tip_text, event_x, event_y):
        if self.tip_window or not tip_text:
            return
        x = self.widget.winfo_rootx() + event_x
        y = self.widget.winfo_rooty() + event_y
        x += 20
        y += 20
        if not self.tip_window:
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry("+%d+%d" % (x, y))
            label = tk.Label(tw, text=tip_text, justify=tk.LEFT,
                             background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                             font=("tahoma", "8", "normal"))
            label.pack(ipadx=1)
        else:
            self.tip_window.wm_geometry("+%d+%d" % (x, y))

    def hide_tip(self):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None

