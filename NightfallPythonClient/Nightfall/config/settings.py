#settings.py
from configparser import ConfigParser
import os

config_file_path = os.path.join(os.path.dirname(__file__), 'settings.ini')

def save_config(settings):
    config = ConfigParser()
    config.read_dict(settings)
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
    with open(config_file_path, 'w') as configfile:
        config.write(configfile)

def load_config():
    config = ConfigParser()
    if not os.path.exists(config_file_path):
        print("Configuration file not found. Creating default settings.")
        default_settings = {
            'Visuals': {
                'PlayerMarkerColor': 'red',
                'BackgroundColor': 'white',
                'RoomDistance': '5',
                'RoomColor': 'blue',
                'DirectedGraph': 'True',
                'ZoneLeavingColor': '#FFA500'
            },
            'General': {
                'DefaultZone': '1'
            },
            'Credentials': {
                'User': '',
                'Pass': ''
            },
            'Font': {
                'background_color': '#000000',  # Black
                'color': '#FFFFFF'             # White
            },
            'ANSIColors': {
                'OwnCommandsColor': '#FFA500'  # Example: add default ANSI colors if needed
            },
            'TriggerCommands': {
                'commands': 'l,look,n,w,s,e,ne,nw,se,sw,northwest,northeast,southeast,southwest,north,west,east,south,up,down,u,d,enter,leave',
                'RoomReload': 'look'
            },
            'Network': {
                'host': 'nightfall.org',
                'port': '4242',
                'quit_command': 'quit'
            }
        }
        save_config(default_settings)
        print("Default configuration created. Please update settings.ini with your username and password under [Credentials].")
        config.read_dict(default_settings)
    else:
        config.read(config_file_path)
    return config