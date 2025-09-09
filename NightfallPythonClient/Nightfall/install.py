import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def check_tkinter():
    try:
        import tkinter
    except ImportError:
        print(
            "tkinter is not installed. Please ensure it's installed. On Debian-based systems, try: 'sudo apt-get install python3-tk'")
        sys.exit(1)

def main():
    check_tkinter()

    packages = ["python-Levenshtein"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            install(package)

if __name__ == "__main__":
    main()
