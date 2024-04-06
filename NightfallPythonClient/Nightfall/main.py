# main.py
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.system("python install.py")

from gui.mainwindow import MainWindow
import tkinter as tk

def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
