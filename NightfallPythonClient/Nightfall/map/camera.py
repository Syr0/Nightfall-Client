class Camera:
    def __init__(self, canvas, initial_position=(0, 0), initial_zoom=1.0):
        self.canvas = canvas
        self.position = initial_position
        self.zoom = initial_zoom
        self.start_pan_pos = None

        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.on_pan)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

        self.apply_current_zoom()

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.start_pan_pos = (event.x, event.y)

    def on_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        dx = (self.start_pan_pos[0] - event.x) / self.zoom
        dy = (self.start_pan_pos[1] - event.y) / self.zoom
        self.position = (self.position[0] + dx, self.position[1] + dy)
        self.start_pan_pos = (event.x, event.y)

    def on_zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        factor = 1.001 ** event.delta
        new_zoom = self.zoom * factor

        relative_factor = new_zoom / self.zoom
        self.zoom = new_zoom
        self.canvas.scale("all", x, y, relative_factor, relative_factor)
        self.update_scroll_region()

    def update_scroll_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def apply_current_zoom(self):
        self.canvas.scale("all", 0, 0, self.zoom, self.zoom)
        self.update_scroll_region()

    def log_current_position(self):
        pass