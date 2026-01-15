import numpy as np
import time
from modes import SingleJumpMode, JumpEstimationMode

# Constants
GRAVITY = 9.81
BUFFER_SIZE = 10000  # ~8-10 seconds at 1200Hz

class PhysicsEngine:
    def __init__(self, config=None):
        self.config = {
            "gravity": GRAVITY,
            "raw_per_kg": 12560.0,
            "frequency": 1280,
        }
        if config:
            self.config.update(config)

        # Buffers - Fixed Size NumPy Array
        # Columns: 0=MsgTimestamp(ms), 1=Weight(kg), 2=PrevMicros
        self.buffer = np.zeros((BUFFER_SIZE, 3), dtype=np.float64)
        self.buf_idx = 0
        self.buf_full = False
        self.BUFFER_SIZE = BUFFER_SIZE # Access for modes

        self.last_micros = 0
        self.logic_time = 0.0
        
        # Tare Logic
        self.zero_offset = 0.0
        self.tare_start_time = 0.0
        self.tare_sum = 0.0
        self.tare_count = 0
        self.is_taring = False
        
        # Modes
        self.modes = {
            "Single Jump": SingleJumpMode(self),
            "Jump Estimation": JumpEstimationMode(self)
        }
        self.active_mode = self.modes["Single Jump"]

    def set_mode(self, mode_name):
        if mode_name in self.modes:
            self.active_mode = self.modes[mode_name]
            self.reset_state()
            print(f"Switched to mode: {mode_name}")
        else:
            print(f"Mode {mode_name} not found")

    def reset_state(self):
        self.logic_time = 0.0
        self.last_micros = 0
        self.tare_sum = 0
        self.tare_count = 0
        self.is_taring = False
        self.active_mode.reset_state()

    def reset(self):
        self.reset_state()
        self.buffer.fill(0)
        self.buf_idx = 0
        self.buf_full = False

    def set_zero(self, offset):
        self.zero_offset = offset
        self.reset_state()

    def set_frequency(self, hz):
        """Update the sampling frequency."""
        if hz > 0:
            self.config["frequency"] = hz
            print(f"Physics frequency updated to {hz} Hz")

    def start_tare(self):
        self.is_taring = True
        self.tare_start_time = 0
        self.tare_sum = 0
        self.tare_count = 0

    def calculate_tare_logic(self, raw, now):
        if self.tare_start_time == 0:
            self.tare_start_time = now
            self.tare_sum = 0
            self.tare_count = 0
        
        self.tare_sum += raw
        self.tare_count += 1
        
        if now - self.tare_start_time >= 600:
            if self.tare_count > 0:
                self.zero_offset = self.tare_sum / self.tare_count
            self.is_taring = False
            self.reset_state()

    def add_to_buffer(self, t, w, u):
        self.buffer[self.buf_idx] = [t, w, u]
        self.buf_idx = (self.buf_idx + 1) % BUFFER_SIZE
        if self.buf_idx == 0:
            self.buf_full = True
            
    # Proxy properties for backward compatibility / easy access if needed
    @property
    def state(self):
        return self.active_mode.state
        
    @property
    def jumper_mass_kg(self):
        # We assume active mode has this
        return getattr(self.active_mode, 'jumper_mass_kg', 0.0)

    def get_buffer_view_time_window(self, end_time, duration_ms):
        """ Efficiently returns a view of the buffer for the last `duration_ms` """
        limit = BUFFER_SIZE if self.buf_full else self.buf_idx
        
        if self.buf_full:
            p1 = self.buffer[self.buf_idx:BUFFER_SIZE]
            p2 = self.buffer[0:self.buf_idx]
            ordered = np.concatenate((p1, p2))
        else:
            ordered = self.buffer[0:self.buf_idx]
            
        start_time = end_time - duration_ms
        mask = ordered[:, 0] >= start_time
        return ordered[mask]

    def process_sample(self, raw, timestamp, micros=0):
        # DT Calculation
        dt = 1.0 / self.config["frequency"]
        
        if micros > 0 and self.last_micros > 0:
            diff = micros - self.last_micros
            if diff < 0:
                diff += 4294967295  # wrap uint32
            
            if 0 < diff < 100000:
                dt = diff / 1000000.0
        
        # Update Logic Time
        if micros > 0:
            if self.last_micros > 0:
                diff = micros - self.last_micros
                if diff < 0:
                    diff += 4294967295
                
                if 0 < diff < 1000000:
                    self.logic_time += (diff / 1000.0)
                else:
                    self.logic_time += (1000.0 / self.config["frequency"])
            else:
                self.logic_time = timestamp
            
            self.last_micros = micros
        else:
            if self.logic_time == 0:
                self.logic_time = timestamp
            else:
                self.logic_time += (1000.0 / self.config["frequency"])
                
        now = self.logic_time
        
        # Tare Logic Intercept
        if self.is_taring:
            self.calculate_tare_logic(raw, now)
            display_kg = (raw - self.zero_offset) / self.config["raw_per_kg"]
            return {
                "state": "TARING",
                "kg": display_kg,
                "display_kg": display_kg,
                "result": None
            }
            
        # Delegate to Mode
        result_dict = self.active_mode.process_sample(raw, timestamp, micros, now, dt)
        
        # ADD TO BUFFER
        self.add_to_buffer(now, result_dict["display_kg"], micros)
        
        return result_dict

    def generate_power_curve(self, start_time, integration_start_time, jumper_mass_kg, start_velocity=0.0):
        # View of buffer sorted chronologically
        if self.buf_full:
             p1 = self.buffer[self.buf_idx:BUFFER_SIZE]
             p2 = self.buffer[0:self.buf_idx]
             ordered = np.concatenate((p1, p2))
        else:
             ordered = self.buffer[0:self.buf_idx]
             
        # Filter for relevant
        mask = ordered[:, 0] >= start_time
        relevant = ordered[mask]
        
        v = 0.0 # Accumulator for Delta V
        # Actual velocity at any point is start_velocity + v
        
        last_u = relevant[0][2] if len(relevant) > 0 else 0
        
        curve = []
        
        # AIR_THRESHOLD = 90000 
        
        for i in range(len(relevant)):
            sample = relevant[i]
            t = sample[0]
            w = sample[1]
            u = sample[2]
            
            dt = 1.0 / self.config["frequency"]
            if u > 0 and last_u > 0:
                d = u - last_u
                if d < 0: d += 4294967295
                if 0 < d < 100000:
                    dt = d / 1000000.0
            last_u = u
            
            force_kg = w
            p = 0.0
            force_n = force_kg * self.config["gravity"]
            
            # Helper for actual velocity
            current_v = 0.0
            
            if t >= integration_start_time:
                effective_force_kg = force_kg
                
                # Check AIR_THRESHOLD logic for consistency?
                if effective_force_kg * self.config["raw_per_kg"] < 90000:
                    effective_force_kg = 0 
                
                force_n = effective_force_kg * self.config["gravity"]
                net_kg = effective_force_kg - jumper_mass_kg
                net_force_n = net_kg * self.config["gravity"]
                acc = net_force_n / jumper_mass_kg
                
                v += acc * dt
                current_v = start_velocity + v
                p = force_n * current_v
                
            curve.append({
                "t": t,
                "v": w,      # Disp KG
                "f": force_n,
                "p": p,
                "vel": current_v 
            })
            
        return curve
