from modes import SingleJumpMode, JumpEstimationMode, ContactTimeMode, ContinuousJumpMode
from modes.base import GRAVITY
from signal_processing import SampleBuffer, SignalConditioner

# Constants
BUFFER_SIZE = 10000  # ~8s

class PhysicsEngine:
    def __init__(self, config=None):
        self.config = {
            "gravity": GRAVITY,
            "raw_per_kg": 12822.594604545637,
            "frequency": 1288,
        }
        if config:
            self.config.update(config)

        self.signal = SignalConditioner(self.config)
        self.current_sample = None
        self.sample_buffer = SampleBuffer(BUFFER_SIZE)
        self.buffer = self.sample_buffer.data  # Compatibility for existing modes
        self.BUFFER_SIZE = BUFFER_SIZE # Access for modes

        self.logic_time = 0.0
        
        # Tare Logic
        self.tare_start_time = 0.0
        self.tare_sum = 0.0
        self.tare_count = 0
        self.is_taring = False
        
        # Calibration Logic
        self.is_calibrating = False
        self.calib_weight_kg = 0.0
        self.calib_start_time = 0.0
        self.calib_sum = 0.0
        self.calib_count = 0
        
        # Modes
        self.modes = {
            "Single Jump": SingleJumpMode(self),
            "Box Drop": SingleJumpMode(self),
            "Box Drop Jump": SingleJumpMode(self),
            "Push Up": SingleJumpMode(self),
            "Squat": SingleJumpMode(self),
            "Deadlift": SingleJumpMode(self),
            "Power Clean": SingleJumpMode(self),
            "Jump Estimation": JumpEstimationMode(self),
            "Contact Time": ContactTimeMode(self),
            "Continuous Jump": ContinuousJumpMode(self)
        }
        self.active_mode = self.modes["Single Jump"]
        self.active_mode_name = "Single Jump"
        self.on_calib_callback = None

    @property
    def zero_offset(self):
        return self.signal.zero_offset

    @zero_offset.setter
    def zero_offset(self, value):
        self.signal.set_zero(value)

    @property
    def buf_idx(self):
        return self.sample_buffer.idx

    @property
    def buf_full(self):
        return self.sample_buffer.full

    def set_mode(self, mode_name):
        if mode_name in self.modes:
            self.active_mode = self.modes[mode_name]
            self.active_mode_name = mode_name
            self.reset_state()
            print(f"Switched to mode: {mode_name}")
        else:
            print(f"Mode {mode_name} not found")

    def reset_state(self):
        self.logic_time = 0.0
        self.current_sample = None
        self.tare_sum = 0
        self.tare_count = 0
        self.is_taring = False
        self.is_calibrating = False
        self.calib_sum = 0
        self.calib_count = 0
        self.active_mode.reset_state()

    def reset(self):
        self.reset_state()
        self.sample_buffer.clear()

    def set_zero(self, offset):
        self.signal.set_zero(offset)
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
        
        if now - self.tare_start_time >= 200:
            if self.tare_count > 0:
                self.signal.set_zero(self.tare_sum / self.tare_count)
            self.is_taring = False
            # Clear buffer to avoid visual artifacts from old timestamps
            self.sample_buffer.clear()
            self.reset_state()

    def start_calibrate(self, known_weight_kg):
        self.is_calibrating = True
        self.calib_weight_kg = known_weight_kg
        self.calib_start_time = 0
        self.calib_sum = 0
        self.calib_count = 0
        print(f"Calibration started for {known_weight_kg}kg")

    def calculate_calibration_logic(self, raw, now):
        if self.calib_start_time == 0:
            self.calib_start_time = now
            self.calib_sum = 0
            self.calib_count = 0
        
        self.calib_sum += raw
        self.calib_count += 1
        
        if now - self.calib_start_time >= 300: # 500ms for more stability
            if self.calib_count > 0 and self.calib_weight_kg > 0:
                avg_raw = self.calib_sum / self.calib_count
                diff_raw = avg_raw - self.zero_offset
                if diff_raw > 0:
                    self.config["raw_per_kg"] = diff_raw / self.calib_weight_kg
                    print(f"Calibration complete. New raw_per_kg: {self.config['raw_per_kg']}")
                    if self.on_calib_callback:
                        self.on_calib_callback(self.config["raw_per_kg"])
            self.is_calibrating = False
            self.reset_state()

    def add_to_buffer(self, t, w):
        """Add a sample to the circular buffer."""
        self.sample_buffer.add(t, w)

    def get_buffer_average(self, count):
        """Get average weight from the last 'count' samples."""
        return self.sample_buffer.average_kg(count)
            
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
        return self.sample_buffer.window(end_time, duration_ms)

    def sample_raw_delta(self, raw):
        if self.current_sample is not None and self.current_sample.raw == raw:
            return self.current_sample.raw_delta
        return self.signal.raw_delta(raw)

    def sample_kg(self, raw):
        if self.current_sample is not None and self.current_sample.raw == raw:
            if self.config.get("use_filtered_for_measurement", False):
                return self.current_sample.filtered_kg
            return self.current_sample.kg
        return self.signal.raw_to_kg(raw)

    def process_sample(self, raw, missing_samples=0):
        """Process a single raw sample from the device.
        
        Uses fixed 1/frequency for dt - ADC has stable crystal timing.
        """
        # Fixed DT from frequency (ADC timing is deterministic)  
        dt = 1.0 / self.config["frequency"]
        dt_ms = 1000.0 / self.config["frequency"]
        
        # Update logic time with fixed increment
        if missing_samples > 0:
            self.logic_time += missing_samples * dt_ms
        self.logic_time += dt_ms
        now = self.logic_time
        
        # Tare Logic Intercept
        if self.is_taring:
            self.calculate_tare_logic(raw, now)
            display_kg = self.signal.raw_to_kg(raw)
            return {
                "state": "TARING",
                "kg": display_kg,
                "display_kg": display_kg,
                "result": None
            }
            
        # Calibration Logic Intercept
        if self.is_calibrating:
            self.calculate_calibration_logic(raw, now)
            display_kg = self.signal.raw_to_kg(raw)
            return {
                "state": "CALIBRATING",
                "kg": display_kg,
                "display_kg": display_kg,
                "result": None
            }
        
        processed = self.signal.process(raw)
        self.current_sample = processed

        # Delegate to Mode
        result_dict = self.active_mode.process_sample(raw, now, dt)
        
        # Add processed display force to buffer. Measurement filtering can be
        # enabled in SignalConditioner without changing mode state machines.
        self.add_to_buffer(now, result_dict.get("display_kg", processed.filtered_kg))
        
        return result_dict

    def generate_power_curve(self, start_time, integration_start_time, jumper_mass_kg, start_velocity=0.0):
        relevant = self.sample_buffer.slice_time_range(start_time)
        
        v = 0.0  # Accumulator for Delta V
        # Actual velocity at any point is start_velocity + v
        
        # Fixed dt from frequency
        dt = 1.0 / self.config["frequency"]
        
        curve = []
        
        for i in range(len(relevant)):
            sample = relevant[i]
            t = sample[0]
            w = sample[1]
            
            force_kg = w
            p = 0.0
            force_n = force_kg * self.config["gravity"]
            
            current_v = 0.0
            
            if t >= integration_start_time:
                effective_force_kg = force_kg

                # Ensure non-negative force (sensor noise/drift can cause <0, leading to positive Power)
                effective_force_kg = max(0.0, effective_force_kg) 
                
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
