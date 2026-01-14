import serial
import serial.tools.list_ports
import threading
import json
import time

class SerialHandler:
    def __init__(self, physics_engine):
        self.physics = physics_engine
        self.serial_port = None
        self.running = False
        self.thread = None
        self.connected = False
        self.port_name = ""
        self.on_jump_callback = None

    def list_ports(self):
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port_name, baud_rate=921600):
        if self.connected:
            self.disconnect()
        
        try:
            print(f"Attempting to connect to {port_name} at {baud_rate}...")
            # Robust connection sequence for Windows
            self.serial_port = serial.Serial()
            self.serial_port.port = port_name
            self.serial_port.baudrate = baud_rate
            self.serial_port.timeout = 1
            # Disable flow control explicitly properties
            self.serial_port.setDTR(False)
            self.serial_port.setRTS(False)
            
            self.serial_port.open()
            
            self.connected = True
            self.port_name = port_name
            self.running = True
            self.physics.reset()
            
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            print(f"Connected to {port_name}")
            return True
        except Exception as e:
            print(f"Failed to connect to {port_name}: {e}")
            return False

    def disconnect(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            
        self.connected = False
        self.serial_port = None
        print("Disconnected")

    def _read_loop(self):
        buffer = ""
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                # Read chunks to avoid blocking too long on readline
                if self.serial_port.in_waiting:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    if '\n' in buffer:
                        lines = buffer.split('\n')
                        # Process all complete lines
                        for line in lines[:-1]:
                            self._process_line(line.strip())
                        
                        # Keep the remainder
                        buffer = lines[-1]
                else:
                    time.sleep(0.001) # Yield slightly
            except Exception as e:
                print(f"Read error: {e}")
                self.running = False
                self.connected = False

    def _process_line(self, line):
        if not line: return
        
        # Check for JSON start
        if line.startswith('{'):
            try:
                data = json.loads(line)
                
                # Handling message types
                if "w" in data:
                    w = data["w"]
                    t = data.get("t", 0)
                    # Timestamp in ms for logic
                    now = time.time() * 1000 
                    res = self.physics.process_sample(w, now, t)
                    
                    if res["result"] and self.on_jump_callback:
                        self.on_jump_callback(res["result"])
                    
                elif "event" in data:
                    evt = data["event"]
                    if evt == "rate" and "hz" in data:
                        self.physics.set_frequency(data["hz"])
                        print(f"Frequency set to {data['hz']} Hz")
                    elif evt == "zero":
                        print("Device Auto-Zeroed")
                        
            except json.JSONDecodeError:
                pass
