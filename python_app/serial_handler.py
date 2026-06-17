import serial
import serial.tools.list_ports
import threading
import json
import time
from queue import Empty, Full, Queue

class SerialHandler:
    def __init__(self, physics_engine):
        self.physics = physics_engine
        self.serial_port = None
        self.running = False
        self.thread = None
        self.connected = False
        self.port_name = ""
        self.on_jump_callback = None
        self.message_queue = Queue(maxsize=20000)
        self.dropped_messages = 0
        self.dropped_samples = 0
        self.last_sequence = None

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
            self.physics.set_zero(0)
            self.physics.reset()
            self._clear_queue()
            self.last_sequence = None
            self.dropped_messages = 0
            self.dropped_samples = 0
            
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
        self._clear_queue()
        print("Disconnected")

    def _clear_queue(self):
        while True:
            try:
                self.message_queue.get_nowait()
            except Empty:
                break

    def _enqueue_message(self, message):
        try:
            self.message_queue.put_nowait(message)
        except Full:
            try:
                self.message_queue.get_nowait()
            except Empty:
                pass
            self.dropped_messages += 1
            try:
                self.message_queue.put_nowait(message)
            except Full:
                self.dropped_messages += 1

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
                    self._enqueue_message(("sample", data))
                    
                elif "event" in data:
                    self._enqueue_message(("event", data))
                        
            except json.JSONDecodeError:
                pass

    def process_pending(self, max_messages=None):
        """
        Drain queued serial messages on the caller thread.

        The read thread only parses bytes and enqueues dictionaries; physics,
        database callbacks, and UI state changes happen here from the main loop.
        """
        processed = 0
        while max_messages is None or processed < max_messages:
            try:
                message_type, data = self.message_queue.get_nowait()
            except Empty:
                break

            if message_type == "sample":
                self._process_sample_message(data)
            elif message_type == "event":
                self._process_event_message(data)
            processed += 1
        return processed

    def _process_sample_message(self, data):
        missing_samples = self._missing_samples_from_sequence(data.get("seq"))
        if missing_samples:
            self.dropped_samples += missing_samples
            print(f"Serial sample gap detected: {missing_samples} missing")

        res = self.physics.process_sample(data["w"], missing_samples=missing_samples)
        if res["result"] and self.on_jump_callback:
            self.on_jump_callback(res["result"])

    def _missing_samples_from_sequence(self, sequence):
        if sequence is None:
            return 0

        sequence = int(sequence)
        if self.last_sequence is None:
            self.last_sequence = sequence
            return 0

        expected = (self.last_sequence + 1) & 0xFFFFFFFF
        self.last_sequence = sequence
        if sequence == expected:
            return 0

        gap = (sequence - expected) & 0xFFFFFFFF
        if gap > 100000:
            # Treat huge gaps as reset/wrap ambiguity rather than real dropout.
            return 0
        return gap

    def _process_event_message(self, data):
        evt = data["event"]
        if evt == "rate" and "hz" in data:
            self.physics.set_frequency(data["hz"])
            print(f"Frequency set to {data['hz']} Hz")
        elif evt == "zero":
            self.physics.set_zero(0)
            print("Device Auto-Zeroed")
        elif evt == "tare_start":
            print("Tare started")
        elif evt == "tare_retry":
            print(f"Tare retry (noise: {data.get('noise', '?')})")
        elif evt == "resetting":
            print("Device resetting...")

    def send_command(self, cmd_name):
        """Send a command to the ESP32."""
        if self.connected and self.serial_port and self.serial_port.is_open:
            try:
                cmd = json.dumps({"cmd": cmd_name}) + "\n"
                self.serial_port.write(cmd.encode('utf-8'))
                return True
            except Exception as e:
                print(f"Send command error: {e}")
                return False
        return False

    def send_tare(self):
        """Request ESP32 to re-zero the scale."""
        return self.send_command("tare")

    def send_reset(self):
        """Request ESP32 to restart."""
        return self.send_command("reset")
