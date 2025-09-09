import asyncio
import time
from asyncio import StreamReader, StreamWriter
from typing import Optional, Callable
from config.settings import load_config, save_config


# Telnet protocol constants
IAC = 255
WILL = 251
WONT = 252
DO = 253
DONT = 254

def process_telnet(data: bytes, writer: Optional[StreamWriter] = None) -> bytes:
    """Remove telnet commands and respond to negotiations"""
    cleaned = bytearray()
    i = 0
    
    while i < len(data):
        if data[i] == IAC:
            if i + 2 < len(data):
                command = data[i + 1]
                option = data[i + 2]
                
                # Respond to telnet negotiations if writer provided
                if writer:
                    if command == WILL:
                        writer.write(bytes([IAC, DONT, option]))
                    elif command == DO:
                        writer.write(bytes([IAC, WONT, option]))
                
                i += 3
            else:
                break
        else:
            cleaned.append(data[i])
            i += 1
    
    return bytes(cleaned)


class MUDStreamProtocol:
    """Handles MUD-specific stream processing with proper buffering"""
    
    def __init__(self, on_message: Callable, on_login_success: Callable, on_login_prompt: Callable):
        self.on_message = on_message
        self.on_login_success = on_login_success
        self.on_login_prompt = on_login_prompt
        
        self.buffer = ""
        self.login_state = 'waiting'
        self.last_data_time = None
        self.incomplete_ansi = ""
        self.MAX_BUFFER_SIZE = 100000  # 100KB max buffer size
        
    def process_data(self, data: bytes, writer: StreamWriter, user: str, password: str) -> None:
        """Process incoming data chunk"""
        # Handle telnet negotiation
        data = process_telnet(data, writer)
        
        if not data:
            return
            
        # Decode with CP437 for box-drawing characters
        try:
            text = data.decode('cp437')
        except UnicodeDecodeError:
            text = data.decode('utf-8', errors='replace')
        
        # Handle incomplete ANSI sequences from previous chunk
        if self.incomplete_ansi:
            text = self.incomplete_ansi + text
            self.incomplete_ansi = ""
        
        # Check for incomplete ANSI at end
        import re
        incomplete_match = re.search(r'\x1b\[[0-9;]*$', text)
        if incomplete_match:
            self.incomplete_ansi = incomplete_match.group()
            text = text[:incomplete_match.start()]
        
        # Add to buffer with size limit
        self.buffer += text
        self.last_data_time = time.time()
        
        # Force flush if buffer is getting too large to prevent memory issues
        if len(self.buffer) > self.MAX_BUFFER_SIZE:
            print(f"[WARNING] Buffer exceeded {self.MAX_BUFFER_SIZE} bytes, force flushing")
            self._flush_buffer()
        
        # Handle login BEFORE flushing buffer
        self.handle_login(writer, user, password)
        
        # Check for complete messages based on state
        self._check_for_complete_messages()
    
    def _check_for_complete_messages(self):
        """Check if we have complete messages to send"""
        # Only check the last few characters to avoid scanning entire buffer
        buffer_len = len(self.buffer)
        if buffer_len < 2:
            return
            
        if self.login_state == 'logged_in':
            # Wait for prompt to ensure complete data
            # Only check last 2 characters for efficiency
            if buffer_len >= 2 and self.buffer[-2:] == '> ':
                self._flush_buffer()
        else:
            # During login, flush on prompts
            # Check last 2-3 characters only
            if buffer_len >= 2:
                last_chars = self.buffer[-3:] if buffer_len >= 3 else self.buffer
                if last_chars.endswith(': ') or last_chars.endswith(':\n'):
                    self._flush_buffer()
    
    def check_timeout(self):
        """Check if we should flush due to timeout"""
        if self.buffer and self.last_data_time:
            threshold = 1.0 if self.login_state == 'logged_in' else 0.05
            if time.time() - self.last_data_time > threshold:
                self._flush_buffer()
    
    def _flush_buffer(self):
        """Send buffered data to callback"""
        if self.buffer and self.on_message:
            self.on_message(self.buffer)
            self.buffer = ""
            self.last_data_time = None
    
    def handle_login(self, writer: StreamWriter, user: str, password: str):
        """Handle automatic login"""
        buffer_lower = self.buffer.lower()
        
        if self.login_state == 'waiting':
            # Check for various login prompts
            if any(x.lower() in buffer_lower for x in ["gamedriver", "lpmud", "enter your name", "login:", "name:", "username:"]):
                if user:
                    print(f"[AUTO-LOGIN] Detected login prompt, sending username")
                    writer.write(f"{user}\r\n".encode())
                    self.login_state = 'password_next'
                else:
                    self.login_state = 'username'
                    if self.on_login_prompt:
                        self.on_login_prompt('username')
                        
        elif self.login_state == 'password_next':
            # Look for password prompt
            if "password:" in buffer_lower:
                if password:
                    print(f"[AUTO-LOGIN] Detected password prompt, sending credentials")
                    writer.write(f"{password}\r\n".encode())
                    self.login_state = 'checking'
                else:
                    self.login_state = 'password'
                    if self.on_login_prompt:
                        self.on_login_prompt('password')
                    
        elif self.login_state in ['checking', 'password']:
            # Check for successful login indicators
            if any(x.lower() in buffer_lower for x in ["reincarnating", "hp:", "mana:", "exits:", "obvious exits"]):
                print(f"[AUTO-LOGIN] Login successful!")
                self.login_state = 'logged_in'
                if self.on_login_success:
                    self.on_login_success()


class AsyncMUDConnection:
    """Asynchronous MUD connection that won't block the GUI"""
    
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
        
        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None
        self.protocol: Optional[MUDStreamProtocol] = None
        self.connected = False
        self.receive_task = None
        self.timeout_task = None
        
    async def connect(self):
        """Establish connection to MUD server"""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        self.connected = True
        
        # Create protocol handler
        self.protocol = MUDStreamProtocol(
            self.on_message, 
            self.on_login_success, 
            self.on_login_prompt
        )
        
        # Start receive and timeout tasks
        self.receive_task = asyncio.create_task(self._receive_loop())
        self.timeout_task = asyncio.create_task(self._timeout_checker())
        
    async def _receive_loop(self):
        """Main receive loop - processes incoming data"""
        try:
            while self.connected:
                # Read available data (up to 4KB at a time)
                data = await self.reader.read(4096)
                
                if not data:
                    break
                
                # Process the data (including login handling)
                self.protocol.process_data(data, self.writer, self.user, self.password)
                
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            self.connected = False
    
    async def _timeout_checker(self):
        """Periodic checker for timeout flushes"""
        try:
            while self.connected:
                await asyncio.sleep(0.05)  # Check every 50ms
                if self.protocol:
                    self.protocol.check_timeout()
        except asyncio.CancelledError:
            pass
    
    async def send(self, data: str):
        """Send data to server"""
        if self.connected and self.writer:
            self.writer.write(f"{data}\r\n".encode())
            await self.writer.drain()
    
    async def send_raw(self, raw_bytes: bytes):
        """Send raw bytes to server"""
        if self.connected and self.writer:
            self.writer.write(raw_bytes)
            await self.writer.drain()
    
    async def close(self):
        """Close the connection"""
        if self.connected:
            # Send quit command
            await self.send(self.quit_command)
            
            # Cancel tasks
            if self.receive_task:
                self.receive_task.cancel()
            if self.timeout_task:
                self.timeout_task.cancel()
            
            # Close connection
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            
            self.connected = False
    
    def save_credentials(self, username: str, password: str):
        """Save login credentials"""
        self.config.set('Credentials', 'User', username)
        self.config.set('Credentials', 'Pass', password)
        config_dict = {section: dict(self.config[section]) for section in self.config.sections()}
        save_config(config_dict)


class MUDConnectionWrapper:
    """Wrapper to integrate async connection with tkinter GUI"""
    
    def __init__(self, on_message=None, on_login_success=None, on_login_prompt=None):
        self.async_conn = AsyncMUDConnection(on_message, on_login_success, on_login_prompt)
        self.loop = None
        self.thread = None
        
        # Expose properties
        self.user = self.async_conn.user
        self.password = self.async_conn.password
        self.login_state = 'waiting'
        
    def connect(self):
        """Start async connection in background thread"""
        import threading
        
        def run_async_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.async_conn.connect())
            # Keep loop running for send/receive
            self.loop.run_forever()
        
        self.thread = threading.Thread(target=run_async_loop, daemon=True)
        self.thread.start()
        
        # Wait a bit for connection
        time.sleep(0.1)
        
    def send(self, data: str):
        """Queue send operation"""
        if self.loop and self.async_conn.connected:
            asyncio.run_coroutine_threadsafe(
                self.async_conn.send(data), 
                self.loop
            )
    
    def send_raw(self, raw_bytes: bytes):
        """Queue raw send operation"""
        if self.loop and self.async_conn.connected:
            asyncio.run_coroutine_threadsafe(
                self.async_conn.send_raw(raw_bytes),
                self.loop
            )
    
    def close(self):
        """Close connection and stop async loop"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.async_conn.close(),
                self.loop
            )
            self.loop.call_soon_threadsafe(self.loop.stop)
            
    def save_credentials(self, username: str, password: str):
        """Save credentials"""
        self.async_conn.save_credentials(username, password)
        
    @property
    def connected(self):
        return self.async_conn.connected