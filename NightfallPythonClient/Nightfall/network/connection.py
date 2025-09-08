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
                try:
                    raw_data = self.socket.recv(4096)
                    
                    if not raw_data:
                        # Connection closed by server
                        print("Server closed connection")
                        break
                    
                    # Handle telnet negotiation
                    data, raw_data = self.handle_telnet(raw_data)
                    
                    # Use CP437 encoding for proper box-drawing characters
                    if raw_data:  # Only decode if there's non-telnet data
                        try:
                            data = raw_data.decode('cp437')
                        except UnicodeDecodeError:
                            data = raw_data.decode('utf-8', errors='replace')
                    else:
                        data = ""
                    
                    if data:
                        # Debug: Show what we received
                        if self.login_state == 'waiting':
                            print(f"[Login Debug] Received while waiting: {repr(data[:200])}")
                        
                        # After initial connection data, we're ready for login
                        # The server sends driver info then waits for input
                        if self.login_state == 'waiting' and ("Gamedriver" in data or "LPmud" in data):
                            print("[Login] Server ready, sending username")
                            if self.user:
                                self.send(self.user)
                                self.login_state = 'password_next'
                            else:
                                self.login_state = 'username'
                                if self.on_login_prompt:
                                    self.on_login_prompt('username')
                        # Check for standard login prompts too
                        elif self.login_state == 'waiting' and ("Enter your name" in data or "login:" in data.lower() or "name:" in data.lower()):
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
                            # Check for successful login indicators - look for the actual game prompt
                            # The room description comes AFTER "Reincarnating old body..."
                            if "Reincarnating old body" in data or "HP:" in data or "Mana:" in data:
                                self.login_state = 'logged_in'
                                if self.on_login_success:
                                    self.on_login_success()
                        
                        # Always pass message to handler
                        if self.on_message:
                            self.on_message(data)
                except ConnectionResetError as e:
                    print(f"Connection lost: {e}")
                    break
                except Exception as e:
                    print(f"Error in receive_data: {e}")
                    break
                    
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            self.connected = False
    def handle_telnet(self, data):
        """Handle telnet negotiation and return cleaned data"""
        IAC = 255  # Interpret As Command
        WILL = 251
        WONT = 252
        DO = 253
        DONT = 254
        
        cleaned = bytearray()
        i = 0
        while i < len(data):
            if data[i] == IAC:
                if i + 2 < len(data):
                    command = data[i + 1]
                    option = data[i + 2]
                    
                    # Respond to telnet negotiation
                    if command == WILL:
                        # Server will do something - we don't want it
                        self.socket.sendall(bytes([IAC, DONT, option]))
                    elif command == DO:
                        # Server wants us to do something - we won't
                        self.socket.sendall(bytes([IAC, WONT, option]))
                    
                    i += 3
                else:
                    # Incomplete telnet command
                    break
            else:
                # Regular data
                cleaned.append(data[i])
                i += 1
        
        return "", bytes(cleaned)
    
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
