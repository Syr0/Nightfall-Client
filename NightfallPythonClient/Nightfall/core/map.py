#map.py
# map.py
import matplotlib.pyplot as plt

prev_x = None
prev_y = None

def setup_map_events(canvas, figure):
    def on_zoom(event):
        ax = figure.gca()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        zoom_scale = 1.1 if event.button == 'up' else (1 / 1.1)
        ax.set_xlim([x * zoom_scale for x in xlim])
        ax.set_ylim([y * zoom_scale for y in ylim])
        canvas.draw_idle()

    def on_press(event):
        global prev_x, prev_y
        if event.button == 2:  # Middle mouse button
            prev_x, prev_y = event.x, event.y

    def on_release(event):
        global prev_x, prev_y
        if event.button == 2:  # Middle mouse button
            prev_x, prev_y = None, None

    def on_move(event):
        global prev_x, prev_y
        if prev_x is not None and prev_y is not None and event.button == 2:
            ax = figure.gca()
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            dx = (prev_x - event.x) * (xlim[1] - xlim[0]) / canvas.figure.get_figwidth() / canvas.figure.dpi
            dy = (event.y - prev_y) * (ylim[1] - ylim[0]) / canvas.figure.get_figheight() / canvas.figure.dpi
            ax.set_xlim([x + dx for x in xlim])
            ax.set_ylim([y + dy for y in ylim])
            canvas.draw_idle()
            prev_x, prev_y = event.x, event.y

    canvas.mpl_connect('scroll_event', on_zoom)
    canvas.mpl_connect('button_press_event', on_press)
    canvas.mpl_connect('button_release_event', on_release)
    canvas.mpl_connect('motion_notify_event', on_move)
