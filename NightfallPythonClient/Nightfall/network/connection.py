#connection.py
import socket
import time
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
        self.line_buffer = ""  # Buffer for incomplete lines
        self.last_data_time = None  # Track when we last received data

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.socket.settimeout(0.05)  # 50ms timeout for recv
        self.connected = True
        Thread(target=self.receive_data, daemon=True).start()

    def send(self, data):
        if self.connected:
            self.socket.sendall(f"{data}\r\n".encode())
    
    def send_raw(self, raw_bytes):
        """Send raw bytes directly without any encoding or line ending"""
        if self.connected:
            self.socket.sendall(raw_bytes)

    def receive_data(self):
        try:
            while self.connected:
                try:
                    # Try to receive data with timeout
                    try:
                        raw_data = self.socket.recv(4096)
                        print(f"[NETWORK CHUNK] Received {len(raw_data)} bytes")
                    except socket.timeout:
                        # Timeout - check if we have buffered data to send
                        if self.line_buffer and self.last_data_time:
                            # For logged in state, only flush on timeout if it's been a LONG time (1 second)
                            # This prevents incomplete data from being sent
                            timeout_threshold = 1.0 if self.login_state == 'logged_in' else 0.05
                            
                            if time.time() - self.last_data_time > timeout_threshold:
                                # Send buffered data after timeout
                                print(f"[NETWORK TIMEOUT] Flushing buffer after {timeout_threshold}s timeout ({len(self.line_buffer)} chars)")
                                if self.on_message:
                                    self.on_message(self.line_buffer)
                                self.line_buffer = ""
                                self.last_data_time = None
                        continue
                    
                    if not raw_data:
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
                        # Debug: Show exactly what we got
                        print(f"[NETWORK DATA] Decoded text ({len(data)} chars):")
                        # Show hex for non-printable chars
                        debug_str = ""
                        for c in data[:200]:  # First 200 chars
                            if c == '\x1b':
                                debug_str += "\\x1b"
                            elif c == '\n':
                                debug_str += "\\n"
                            elif c == '\r':
                                debug_str += "\\r"
                            elif ord(c) < 32 or ord(c) > 126:
                                debug_str += f"\\x{ord(c):02x}"
                            else:
                                debug_str += c
                        print(f"  {debug_str}")
                        
                        # Check for split ANSI sequences
                        if '\x1b[' in data:
                            import re
                            incomplete_at_end = re.search(r'\x1b\[[0-9;]*$', data)
                            if incomplete_at_end:
                                print(f"[NETWORK WARNING] Data ends with incomplete ANSI: {incomplete_at_end.group()}")
                        
                        # Add new data to buffer
                        self.line_buffer += data
                        print(f"[NETWORK BUFFER] Buffer now has {len(self.line_buffer)} chars")
                        
                        # Track time for timeout
                        current_time = time.time()
                        self.last_data_time = current_time
                        
                        # Check for login prompts IMMEDIATELY (don't wait for complete response)
                        if self.login_state == 'waiting':
                            if "Gamedriver" in self.line_buffer or "LPmud" in self.line_buffer:
                                if self.user:
                                    self.send(self.user)
                                    self.login_state = 'password_next'
                                else:
                                    self.login_state = 'username'
                                    if self.on_login_prompt:
                                        self.on_login_prompt('username')
                            elif "Enter your name" in self.line_buffer or "login:" in self.line_buffer.lower() or "name:" in self.line_buffer.lower():
                                if self.user:
                                    self.send(self.user)
                                    self.login_state = 'password_next'
                                else:
                                    self.login_state = 'username'
                                    if self.on_login_prompt:
                                        self.on_login_prompt('username')
                        elif self.login_state == 'password_next' and "password:" in self.line_buffer.lower():
                            if self.password:
                                self.send(self.password)
                                self.login_state = 'checking'
                            else:
                                self.login_state = 'password'
                                if self.on_login_prompt:
                                    self.on_login_prompt('password')
                        elif self.login_state in ['checking', 'password']:
                            if "Reincarnating old body" in self.line_buffer or "HP:" in self.line_buffer or "Mana:" in self.line_buffer:
                                self.login_state = 'logged_in'
                                if self.on_login_success:
                                    self.on_login_success()
                        
                        # Check for clear completion signals
                        # CRITICAL: Only send data when we see the prompt "> " to ensure we have complete response
                        if self.login_state == 'logged_in':
                            # ONLY send when we see the prompt - this ensures complete data
                            is_complete = self.line_buffer.endswith('> ')
                        else:
                            # During login, send on prompts
                            is_complete = (self.line_buffer.endswith(': ') or
                                         self.line_buffer.endswith(':\n'))
                        
                        if is_complete:
                            # Process the complete buffer
                            complete_data = self.line_buffer
                            self.line_buffer = ""
                            
                            print(f"[NETWORK COMPLETE] Sending {len(complete_data)} chars to display")
                            
                            # Debug: Check for split items
                            if "Hartwa" in complete_data or "map o" in complete_data:
                                lines = complete_data.split('\n')
                                for i, line in enumerate(lines):
                                    if "Hartwa" in line or "map o" in line:
                                        print(f"[NETWORK PROBLEM] Line {i}: '{line}'")
                                        # Show hex of this line
                                        hex_str = ""
                                        for c in line:
                                            if c == '\x1b':
                                                hex_str += "\\x1b"
                                            elif ord(c) < 32 or ord(c) > 126:
                                                hex_str += f"\\x{ord(c):02x}"
                                            else:
                                                hex_str += c
                                        print(f"  Hex: {hex_str}")
                            
                            # Send complete data to display
                            if self.on_message:
                                self.on_message(complete_data)
                        elif len(self.line_buffer) > 8192:
                            # Safety: if buffer gets too large, flush it anyway
                            if self.on_message:
                                self.on_message(self.line_buffer)
                            self.line_buffer = ""
                except ConnectionResetError as e:
                    break
                except Exception as e:
                    break
                    
        except Exception as e:
            pass
        finally:
            self.connected = False
    def handle_telnet(self, data):
        IAC = 255
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
                    
                    if command == WILL:
                        self.socket.sendall(bytes([IAC, DONT, option]))
                    elif command == DO:
                        self.socket.sendall(bytes([IAC, WONT, option]))
                    
                    i += 3
                else:
                    break
            else:
                cleaned.append(data[i])
                i += 1
        
        return "", bytes(cleaned)
    
    def close(self):
        if self.connected:
            self.send(self.quit_command)
            self.socket.close()
            self.connected = False
    
    def save_credentials(self, username, password):
        self.config.set('Credentials', 'User', username)
        self.config.set('Credentials', 'Pass', password)
        config_dict = {section: dict(self.config[section]) for section in self.config.sections()}
        save_config(config_dict)
