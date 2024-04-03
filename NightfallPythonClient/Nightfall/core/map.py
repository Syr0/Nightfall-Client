#map.py
# map.py
import matplotlib.pyplot as plt

prev_x = None
prev_y = None

def setup_map_events(canvas, figure):
    def on_zoom(event):
        ax = figure.gca()
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()

        base_scale = 1.1

        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            return

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

        ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
        ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])

        canvas.draw_idle()

    def on_press(event):
        global prev_x, prev_y
        if event.button == 2:
            prev_x, prev_y = event.x, event.y

    def on_release(event):
        global prev_x, prev_y
        if event.button == 2:
            prev_x, prev_y = None, None

    def on_move(event):
        global prev_x, prev_y
        if prev_x is not None and prev_y is not None and event.button == 2:
            ax = figure.gca()
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            dx = (prev_x - event.x) * (xlim[1] - xlim[0]) / canvas.figure.get_figwidth() / canvas.figure.dpi
            dy = (prev_y - event.y) * (ylim[1] - ylim[0]) / canvas.figure.get_figheight() / canvas.figure.dpi  # Inverted dy
            ax.set_xlim([x + dx for x in xlim])
            ax.set_ylim([y + dy for y in ylim])
            canvas.draw_idle()
            prev_x, prev_y = event.x, event.y

    canvas.mpl_connect('scroll_event', on_zoom)
    canvas.mpl_connect('button_press_event', on_press)
    canvas.mpl_connect('button_release_event', on_release)
    canvas.mpl_connect('motion_notify_event', on_move)