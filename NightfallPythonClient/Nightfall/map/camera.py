#camera.py
class Camera:
    def __init__(self, canvas, initial_position=(0, 0), initial_zoom=1.0):
        self.canvas = canvas
        self.position = initial_position
        self.zoom = initial_zoom
        self.start_pan_pos = None

        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.on_pan)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.start_pan_pos = (event.x, event.y)

    def on_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        dx = event.x - self.start_pan_pos[0]
        dy = event.y - self.start_pan_pos[1]
        self.position = (self.position[0] + dx, self.position[1] + dy)
        self.start_pan_pos = (event.x, event.y)

    def on_zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        factor = 1.001 ** event.delta
        self.zoom *= factor
        self.canvas.scale("all", x, y, factor, factor)
        self.update_scroll_region()

    def update_scroll_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def reset_camera(self, bounds):
        self.position = (0, 0)
        self.zoom = 1.0
        self.canvas.scale("all", 0, 0, self.zoom, self.zoom)
        self.canvas.configure(scrollregion=bounds)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def apply_current_zoom(self):
        self.canvas.scale("all", 0, 0, self.zoom, self.zoom)
        self.update_scroll_region()
        # Ensure the position is updated to reflect current zoom and pan state
        self.canvas.xview_moveto(self.position[0] / self.canvas.winfo_width())
        self.canvas.yview_moveto(self.position[1] / self.canvas.winfo_height())
