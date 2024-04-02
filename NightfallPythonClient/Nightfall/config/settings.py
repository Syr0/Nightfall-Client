#settings.py
from configparser import ConfigParser
import os

config_file_path = os.path.join(os.path.dirname(__file__), 'settings.ini')

def save_config(settings):
    config = ConfigParser()
    config.read_dict(settings)
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)  # Ensure directory exists
    with open(config_file_path, 'w') as configfile:
        config.write(configfile)

def load_config():
    if not os.path.exists(config_file_path):
        print("Configuration file not found.")
        exit(1)
    config = ConfigParser()
    config.read(config_file_path)
    return config
