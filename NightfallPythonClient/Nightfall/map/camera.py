#camera.py
import tkinter as tk

class Camera:
    def __init__(self, canvas, initial_position=(0, 0), initial_zoom=1.0, initial_level=0):
        self.canvas = canvas
        self.x, self.y = initial_position
        self.zoom = initial_zoom
        self.level = initial_level
        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.on_pan)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.x, self.y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def on_zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        factor = 1.001 ** event.delta
        self.zoom *= factor
        self.canvas.scale("all", x, y, factor, factor)

    def reset_camera(self, bounds):
        self.x, self.y = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
        self.zoom = 1.0
        self.canvas.scale("all", self.x, self.y, self.zoom, self.zoom)
