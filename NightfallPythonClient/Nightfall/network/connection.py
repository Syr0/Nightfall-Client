#connection.py
import socket
from threading import Thread
from config.settings import load_config, save_config

class MUDConnection:
    def __init__(self, on_message=None, on_login_success=None, on_login_prompt=None):
        self.config = load_config()
        self.host = self.config.get('Network', 'host')
        self.port = self.config.getint('Network', 'port')
        self.quit_command = self.config.get('Network', 'quit_command')
        self.user = self.config.get('Credentials', 'User', fallback='')
        self.password = self.config.get('Credentials', 'Pass', fallback='')
        self.on_message = on_message
        self.on_login_success = on_login_success
        self.on_login_prompt = on_login_prompt
        self.socket = None
        self.connected = False
        self.login_state = 'waiting'  # 'waiting', 'username', 'password', 'logged_in'

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.connected = True
        Thread(target=self.receive_data, daemon=True).start()

    def send(self, data):
        if self.connected:
            self.socket.sendall(f"{data}\r\n".encode())

    def receive_data(self):
        try:
            while self.connected:
                raw_data = self.socket.recv(4096)
                # Use CP437 encoding for proper box-drawing characters
                try:
                    data = raw_data.decode('cp437')
                except UnicodeDecodeError:
                    data = raw_data.decode('utf-8', errors='replace')
                
                if data:
                    # Check for login prompts
                    if self.login_state == 'waiting' and "Enter your name," in data:
                        if self.user:  # Auto-login if credentials exist
                            self.send(self.user)
                            self.login_state = 'password_next'
                        else:  # Manual login
                            self.login_state = 'username'
                            if self.on_login_prompt:
                                self.on_login_prompt('username')
                    elif self.login_state == 'password_next' and "password:" in data.lower():
                        if self.password:
                            self.send(self.password)
                            self.login_state = 'checking'
                        else:
                            self.login_state = 'password'
                            if self.on_login_prompt:
                                self.on_login_prompt('password')
                    elif self.login_state in ['checking', 'password']:
                        # Check for successful login indicators
                        if any(indicator in data for indicator in ['Welcome', 'Mana:', 'HP:', 'Last login']):
                            self.login_state = 'logged_in'
                            if self.on_login_success:
                                self.on_login_success()
                    
                    # Always pass message to handler
                    if self.on_message:
                        self.on_message(data)
        except Exception as e:
            print(f"Connection error: {e}")
            self.connected = False
    def close(self):
        if self.connected:
            self.send(self.quit_command)
            self.socket.close()
            self.connected = False
    
    def save_credentials(self, username, password):
        """Save login credentials to config"""
        self.config.set('Credentials', 'User', username)
        self.config.set('Credentials', 'Pass', password)
        config_dict = {section: dict(self.config[section]) for section in self.config.sections()}
        save_config(config_dict)
