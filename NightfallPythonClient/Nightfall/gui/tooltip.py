#tooltip.py
import tkinter as tk


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
        y = self.widget.winfo_rooty() + event_y + 20

        if not self.tip_window:
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.config(bg='black')


            frame = tk.Frame(tw, background="#FF00FF", borderwidth=2)
            frame.pack()

            label = tk.Label(frame, text=tip_text, justify=tk.CENTER,
                             background="#2e2e2e", relief=tk.FLAT, borderwidth=4,
                             font=("Consolas", "10", "normal"), fg="#ffffff")
            label.pack()

            tw.update_idletasks()
            width = tw.winfo_width()
            height = tw.winfo_height()

            screen_width = self.widget.winfo_screenwidth()
            x_centered = max(x - width // 2, 0)
            x_centered = min(x_centered, screen_width - width)

            tw.wm_geometry("+%d+%d" % (x_centered, y))
        else:

            for child in self.tip_window.winfo_children():
                for grandchild in child.winfo_children():
                    if isinstance(grandchild, tk.Label):
                        grandchild.config(text=tip_text)

    def hide_tip(self):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None

