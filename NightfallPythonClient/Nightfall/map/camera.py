#change the code. Ensure the resizing of the window does not alter the results. when changeing the levels, the camera is still the same. but the map shown is not the same. make the code more robust against accidential changes on offsets of the map. ensure the drawing always happens with the same roomid (the lowest) on the same position (0,0) with the same zoom factor (1). Apply the camera view after the map was drawn. draw all levels on seperate and switch between them, but ensure they are all correctly offsetted to 0,0. changeing the level should only show other data, but not cause a map-redrawing. that is just a task for the camera

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
        dx = (self.start_pan_pos[0] - event.x) / self.zoom
        dy = (self.start_pan_pos[1] - event.y) / self.zoom
        self.position = (self.position[0] + dx, self.position[1] + dy)
        self.start_pan_pos = (event.x, event.y)

    def on_zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        factor = 1.001 ** event.delta
        self.zoom *= factor
        self.canvas.scale("all", x, y, factor, factor)
        self.position = ((self.position[0] - x) * factor + x, (self.position[1] - y) * factor + y)
        self.update_scroll_region()

    def update_scroll_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def apply_current_zoom(self):
        self.canvas.scale("all", 0, 0, self.zoom, self.zoom)
        self.update_scroll_region()
        bbox = self.canvas.bbox("all") or (0, 0, 0, 0)
        scrollregion_width = bbox[2] - bbox[0]
        scrollregion_height = bbox[3] - bbox[1]
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        x_center_ratio = (self.position[0] - canvas_width / 2) / scrollregion_width
        y_center_ratio = (self.position[1] - canvas_height / 2) / scrollregion_height
        self.canvas.xview_moveto(x_center_ratio)
        self.canvas.yview_moveto(y_center_ratio)

    def log_current_position(self):
        print(f"Camera Position (Center): X = {self.position[0]}, Y = {self.position[1]}")