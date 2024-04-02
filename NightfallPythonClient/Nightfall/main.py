#main.py
import tkinter as tk
from gui.mainwindow import MainWindow

def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
