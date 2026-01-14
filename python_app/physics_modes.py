import numpy as np

# Constants - logic specific
AIR_THRESHOLD = 100000
MOVEMENT_THRESHOLD = 26000
STABILITY_TOLERANCE_KG = 1.9
MAX_PROPULSION_TIME_MS = 100000
MIN_AIR_TIME = 150
MAX_AIR_TIME = 1500
GRAVITY = 9.81

class PhysicsMode:
    def __init__(self, engine):
        self.engine = engine
        self.state = "IDLE"

    def process_sample(self, raw, timestamp, micros, now, dt):
        """
        Process a single sample.
        Returns a dict with state, metrics, etc. same as original process_sample return.
        """
        raise NotImplementedError

    def reset_state(self):
        self.state = "IDLE"

class SingleJumpMode(PhysicsMode):
    def __init__(self, engine):
        super().__init__(engine)
        self.state = "IDLE"
        
        # State variables specific to Single Jump
        self.weight_confirmed = False
        self.calibration_start_time = 0.0
        self.calibration_sum = 0.0
        self.calibration_count = 0
        self.calibration_min = 20000000.0
        self.calibration_max = -20000000.0
        self.static_weight_raw = 0.0
        
        self.jumper_mass_kg = 0.0
        
        # Jump State
        self.current_velocity = 0.0
        self.peak_power = 0.0
        self.last_takeoff_velocity = 0.0
        self.max_propulsion_force = 0.0
        self.sum_power = 0.0
        self.power_sample_count = 0
        
        self.integration_start_time = 0.0
        self.takeoff_time = 0.0
        self.landing_time = 0.0
        self.jump_start_y = 0.0
        
        self.propulsion_stability_start_time = 0.0

    def reset_state(self):
        self.state = "IDLE"
        self.weight_confirmed = False
        self.calibration_start_time = 0.0
        self.jumper_mass_kg = 0.0
        self.current_velocity = 0.0
        self.peak_power = 0.0
        self.max_propulsion_force = 0.0
        self.sum_power = 0.0
        self.power_sample_count = 0
        self.propulsion_stability_start_time = 0.0

    def process_sample(self, raw, timestamp, micros, now, dt):
        engine = self.engine
        
        # 1. Raw to Net
        # Access engine config
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        weight = raw - engine.zero_offset
        if weight < -10000: # Simple noise clamp for sanity
            weight = -weight
        
        display_kg = weight / raw_per_kg
        result = None
        
        # --- STATE MACHINE ---
        if self.state == "IN_AIR":
            current_air_time = now - self.takeoff_time
            
            if weight >= AIR_THRESHOLD: # Landing
                if current_air_time >= MIN_AIR_TIME:
                    self.landing_time = now
                    self.state = "COOLDOWN"
                else:
                    self.state = "READY"
            elif current_air_time > MAX_AIR_TIME:
                self.state = "IDLE"
                self.weight_confirmed = False

        elif self.state == "COOLDOWN":
            if now - self.landing_time >= 1000:
                self.state = "RESULT"
                # FINAL CALC
                current_air_time = self.landing_time - self.takeoff_time
                avg_p = 0
                if self.power_sample_count > 0:
                    avg_p = self.sum_power / self.power_sample_count
                
                t_sec = current_air_time / 1000.0
                h = (gravity * t_sec * t_sec) / 8.0 * 100.0
                v_flight = gravity * (t_sec / 2.0)
                
                harman = (21.2 * h) + (23.0 * self.jumper_mass_kg) - 1393
                harman = max(0, harman)
                
                sayers = (60.7 * h) + (45.3 * self.jumper_mass_kg) - 2055
                sayers = max(0, sayers)
                
                h_impulse = (self.last_takeoff_velocity**2) / (2 * gravity) * 100.0
                
                t_start = self.jump_start_y - 1000
                curve = engine.generate_power_curve(t_start, self.integration_start_time, self.jumper_mass_kg)
                
                result = {
                    "timestamp": self.landing_time,
                    "flight_time": current_air_time,
                    "height_flight": h,
                    "height_impulse": h_impulse,
                    "peak_power": self.peak_power,
                    "avg_power": avg_p,
                    "formula_peak_power": sayers,
                    "formula_avg_power": harman,
                    "velocity_takeoff": self.last_takeoff_velocity,
                    "velocity_flight": v_flight,
                    "max_force": self.max_propulsion_force / gravity,
                    "jumper_weight": self.jumper_mass_kg,
                    "force_curve": curve,
                    "avg_power_start_time": self.integration_start_time
                }
                
        elif weight < AIR_THRESHOLD:
            if self.state == "READY" or self.state == "PROPULSION":
                # TAKEOFF
                self.last_takeoff_velocity = self.current_velocity
                self.takeoff_time = now
                self.state = "IN_AIR"
            else:
                if self.weight_confirmed:
                    self.weight_confirmed = False
                    self.jumper_mass_kg = 0
                self.state = "IDLE"
                self.calibration_start_time = 0
        
        else:
            # Weight > Air Threshold
            if not self.weight_confirmed:
                self.state = "WEIGHING"
                if self.calibration_start_time == 0:
                    self.calibration_start_time = now
                    self.calibration_sum = 0
                    self.calibration_count = 0
                    self.calibration_min = 20000000
                    self.calibration_max = -20000000
                
                self.calibration_sum += weight
                self.calibration_count += 1
                self.calibration_min = min(self.calibration_min, weight)
                self.calibration_max = max(self.calibration_max, weight)
                
                if now - self.calibration_start_time >= 500:
                    noise_raw = self.calibration_max - self.calibration_min
                    noise_kg = noise_raw / raw_per_kg
                    
                    if noise_kg <= STABILITY_TOLERANCE_KG:
                        if self.calibration_count > 0:
                            self.static_weight_raw = self.calibration_sum / self.calibration_count
                            self.jumper_mass_kg = self.static_weight_raw / raw_per_kg
                            self.weight_confirmed = True
                            self.state = "READY"
                        self.calibration_start_time = 0
                    else:
                        self.calibration_start_time = 0
            else:
                # READY or PROPULSION
                if self.state != "PROPULSION":
                    diff = abs(weight - self.static_weight_raw)
                    if diff > MOVEMENT_THRESHOLD:
                        self.state = "PROPULSION"
                        self.integration_start_time = now
                        self.jump_start_y = now
                        
                        # Retroactive Fix
                        self._retroactive_propulsion_fix(now)
                    else:
                        self.state = "READY"
                        
                else:
                    # IN PROPULSION
                    if self.jumper_mass_kg > 0 and now - self.integration_start_time <= MAX_PROPULSION_TIME_MS:
                        force_n = (raw / raw_per_kg) * gravity
                        net_kg = display_kg - self.jumper_mass_kg
                        net_force_n = net_kg * gravity
                        acc = net_force_n / self.jumper_mass_kg
                        
                        self.current_velocity += acc * dt
                        instant_power = force_n * self.current_velocity
                        
                        if force_n > self.max_propulsion_force:
                            self.max_propulsion_force = force_n
                        
                        if self.current_velocity > 0:
                            self.sum_power += instant_power
                            self.power_sample_count += 1
                        
                        if instant_power > self.peak_power:
                            self.peak_power = instant_power
                            
                        # Exit Condition
                        diff_mass = abs(display_kg - self.jumper_mass_kg)
                        if diff_mass < STABILITY_TOLERANCE_KG:
                            if self.propulsion_stability_start_time == 0:
                                self.propulsion_stability_start_time = now
                            elif now - self.propulsion_stability_start_time > 250:
                                self.state = "READY"
                                self.current_velocity = 0
                                self.peak_power = 0
                                self.sum_power = 0
                                self.power_sample_count = 0
                                self.propulsion_stability_start_time = 0
                        else:
                            self.propulsion_stability_start_time = 0

                    if now - self.integration_start_time > 5000:
                         self.state = "READY"
                         self.current_velocity = 0
                         self.peak_power = 0
                         self.sum_power = 0
                         self.power_sample_count = 0

        return {
            "state": self.state,
            "kg": display_kg,
            "display_kg": display_kg,
            "result": result,
            # Pass through for easy access
            "jumper_mass_kg": self.jumper_mass_kg,
            "velocity": self.current_velocity
        }

    def _retroactive_propulsion_fix(self, now):
        """Re-calcs velocity from buffer start based on movement threshold"""
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        curr_idx = engine.buf_idx - 1
        if curr_idx < 0: curr_idx = engine.BUFFER_SIZE - 1
        
        # Search for the best start point (closest to bodyweight)
        # instead of failing if accurate threshold isn't met
        best_start_index = curr_idx
        min_diff = 9999.0
        
        scan_count = 0
        limit = min(engine.buffer.shape[0], 600)
        
        while scan_count < limit:
            scan_idx = (engine.buf_idx - 1 - scan_count) % engine.BUFFER_SIZE
            pt = engine.buffer[scan_idx]
            
            if now - pt[0] > 600: break # Look back window (ms)
                
            diff_kg = abs(pt[1] - self.jumper_mass_kg)
            
            # If we find a very good match, stop early
            if diff_kg < 0.5:
                best_start_index = scan_idx
                break
            
            # Keep track of the "most stable" point found
            if diff_kg < min_diff:
                min_diff = diff_kg
                best_start_index = scan_idx
            
            scan_count += 1
            
        # Use the best point found
        start_index = best_start_index
        
        # Update official start times for graph generation later
        if start_index != curr_idx:
             start_pt = engine.buffer[start_index]
             self.integration_start_time = start_pt[0]
             self.jump_start_y = start_pt[0]
            
        self.current_velocity = 0
        self.peak_power = 0
        self.sum_power = 0
        self.power_sample_count = 0
        self.max_propulsion_force = 0
        
        # Forward integrate from the new start point
        last_buf_micros = engine.buffer[start_index][2]
        if last_buf_micros == 0:
            last_buf_micros = engine.buffer[start_index][0] * 1000
            
        steps = 0
        i = start_index
        while i != engine.buf_idx:
            b = engine.buffer[i]
            iter_dt = 1.0 / engine.config["frequency"]
            if b[2] > 0 and last_buf_micros > 0:
                d = b[2] - last_buf_micros
                if d < 0: d += 4294967295
                if 0 < d < 100000:
                    iter_dt = d / 1000000.0
            last_buf_micros = b[2]
            
            force_kg = b[1]
            net_kg = force_kg - self.jumper_mass_kg
            net_force_n = net_kg * gravity
            acc = net_force_n / self.jumper_mass_kg
            
            self.current_velocity += acc * iter_dt
            
            force_n = force_kg * gravity
            instant_power = force_n * self.current_velocity
            
            if self.current_velocity > 0:
                self.sum_power += instant_power
                self.power_sample_count += 1
            
            if force_n > self.max_propulsion_force:
                self.max_propulsion_force = force_n
            if instant_power > self.peak_power:
                self.peak_power = instant_power
                
            i = (i + 1) % engine.BUFFER_SIZE
            steps += 1
            if steps > engine.BUFFER_SIZE: break
            
        self.integration_start_time = engine.buffer[start_index][0]
        self.jump_start_y = self.integration_start_time


class JumpEstimationMode(PhysicsMode):
    """
    Mode: "Jump Estimation"
    - Does NOT measure weight automatically (User inputs it manually).
    - Starts in READY/IDLE.
    - If user jumps (weight < threshold), trigger IN_AIR (logic state, though no flight time measured).
    - Results based on IMPULSE.
    """

    def __init__(self, engine):
        super().__init__(engine)
        self.manual_mass_kg = 75.0 # Default
        self.manual_start_velocity = 0.0
        self.state = "READY"
        
        # Physics Vars
        self.current_velocity = 0.0
        self.peak_power = 0.0
        self.max_propulsion_force = 0.0
        self.sum_power = 0.0
        self.power_sample_count = 0
        
        self.integration_start_time = 0.0
        self.jump_start_y = 0.0
        self.last_takeoff_velocity = 0.0
        self.static_weight_raw = 0.0
        
    @property
    def jumper_mass_kg(self):
        return self.manual_mass_kg

    def set_mass(self, mass_kg):
        self.manual_mass_kg = mass_kg
        self.static_weight_raw = mass_kg * self.engine.config["raw_per_kg"]
        
    def set_start_velocity(self, vel):
        self.manual_start_velocity = vel
    
    def process_sample(self, raw, timestamp, micros, now, dt):
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        if self.static_weight_raw == 0 and self.manual_mass_kg > 0:
             self.static_weight_raw = self.manual_mass_kg * raw_per_kg
             
        weight = raw - engine.zero_offset
        display_kg = weight / raw_per_kg
        
        result = None
        
        if self.state == "IDLE":
             self.state = "READY"
        
        if weight < AIR_THRESHOLD:
            # IN AIR
            if self.state == "PROPULSION":
                 # TAKEOFF!
                 # Add start velocity
                 self.last_takeoff_velocity = self.current_velocity + self.manual_start_velocity
                 
                 # Calculate Impulse Height immediately
                 h_impulse = (self.last_takeoff_velocity**2) / (2 * gravity) * 1000.0
                 
                 # Calculate Flight Time from Impulse
                 # t = 2 * v / g
                 flight_time_estimated_ms = (2 * self.last_takeoff_velocity / gravity) * 1000.0
                 
                 curve = engine.generate_power_curve(self.jump_start_y, self.integration_start_time, self.manual_mass_kg, start_velocity=self.manual_start_velocity)
                 
                 avg_p = 0
                 if self.power_sample_count > 0:
                        avg_p = self.sum_power / self.power_sample_count
                        
                 result = {
                    "timestamp": now,
                    "flight_time": flight_time_estimated_ms, # Estimated from Impulse
                    "height_flight": None, # Removed as per request
                    "height_impulse": h_impulse,
                    "peak_power": self.peak_power,
                    "avg_power": avg_p,
                    "formula_peak_power": None,
                    "formula_avg_power": None,
                    "velocity_takeoff": self.last_takeoff_velocity,
                    "velocity_flight": None, # Removed as per request
                    "max_force": self.max_propulsion_force / gravity,
                    "jumper_weight": self.manual_mass_kg,
                    "force_curve": curve,
                    "avg_power_start_time": self.integration_start_time
                 }
                 
                 self.state = "IN_AIR" 
            
            elif self.state == "READY":
                 self.state = "READY"

        elif weight >= AIR_THRESHOLD:
            # ON GROUND
            if self.state == "IN_AIR":
                 self.state = "READY" 
            
            elif self.state == "PROPULSION":
                 if now - self.integration_start_time > 5000:
                    self.state = "READY"
                 
                 force_n = (raw / raw_per_kg) * gravity
                 net_kg = display_kg - self.manual_mass_kg
                 net_force_n = net_kg * gravity
                 
                 acc = net_force_n / self.manual_mass_kg
                 self.current_velocity += acc * dt
                 
                 instant_power = force_n * (self.current_velocity + self.manual_start_velocity)
                 if force_n > self.max_propulsion_force: self.max_propulsion_force = force_n
                 
                 # Power accumulation - should we include start velocity in power? Yes, P = F * v
                 if (self.current_velocity + self.manual_start_velocity) > 0:
                     self.sum_power += instant_power
                     self.power_sample_count += 1
                 if instant_power > self.peak_power: self.peak_power = instant_power

            else:
                 # READY
                 if abs(display_kg - self.manual_mass_kg) > STABILITY_TOLERANCE_KG * 2: 
                      self.state = "PROPULSION"
                      self.integration_start_time = now
                      self.jump_start_y = now
                      
                      self.current_velocity = 0
                      self.peak_power = 0
                      self.sum_power = 0
                      self.power_sample_count = 0
                      self.max_propulsion_force = 0
                      
                      self._retroactive_propulsion_fix(now)

        return {
            "state": self.state,
            "kg": display_kg,
            "display_kg": display_kg,
            "result": result,
            "jumper_mass_kg": self.manual_mass_kg,
            "velocity": self.current_velocity
        }
        
    def _retroactive_propulsion_fix(self, now):
        """Re-calcs velocity from buffer start based on movement threshold"""
        engine = self.engine
        gravity = engine.config["gravity"]
        
        curr_idx = engine.buf_idx - 1
        if curr_idx < 0: curr_idx = engine.BUFFER_SIZE - 1
        
        best_start_index = curr_idx
        min_diff = 9999.0
        
        scan_count = 0
        limit = min(engine.buffer.shape[0], 600)
        
        while scan_count < limit:
            scan_idx = (engine.buf_idx - 1 - scan_count) % engine.BUFFER_SIZE
            pt = engine.buffer[scan_idx]
            
            if now - pt[0] > 600: break
            
            diff_kg = abs(pt[1] - self.manual_mass_kg)
            
            if diff_kg < 2.0: 
                best_start_index = scan_idx
                break
            
            if diff_kg < min_diff:
                min_diff = diff_kg
                best_start_index = scan_idx

            scan_count += 1

        # Use the best point found
        start_index = best_start_index
        
        # Update official start times
        if start_index != curr_idx:
             start_pt = engine.buffer[start_index]
             self.integration_start_time = start_pt[0]
             self.jump_start_y = start_pt[0]
            
        self.current_velocity = 0
        self.peak_power = 0
        self.sum_power = 0
        self.power_sample_count = 0
        self.max_propulsion_force = 0
        
        last_buf_micros = engine.buffer[start_index][2]
        if last_buf_micros == 0:
            last_buf_micros = engine.buffer[start_index][0] * 1000
            
        steps = 0
        i = start_index
        while i != engine.buf_idx:
            b = engine.buffer[i]
            iter_dt = 1.0 / engine.config["frequency"]
            if b[2] > 0 and last_buf_micros > 0:
                d = b[2] - last_buf_micros
                if d < 0: d += 4294967295
                if 0 < d < 100000:
                    iter_dt = d / 1000000.0
            last_buf_micros = b[2]
            
            force_kg = b[1]
            net_kg = force_kg - self.manual_mass_kg
            net_force_n = net_kg * gravity
            acc = net_force_n / self.manual_mass_kg
            
            self.current_velocity += acc * iter_dt
            
            force_n = force_kg * gravity
            instant_power = force_n * (self.current_velocity + self.manual_start_velocity)
            
            if (self.current_velocity + self.manual_start_velocity) > 0:
                self.sum_power += instant_power
                self.power_sample_count += 1
            
            if force_n > self.max_propulsion_force:
                self.max_propulsion_force = force_n
            if instant_power > self.peak_power:
                self.peak_power = instant_power
                
            i = (i + 1) % engine.BUFFER_SIZE
            steps += 1
            if steps > engine.BUFFER_SIZE: break
            
        self.integration_start_time = engine.buffer[start_index][0]
        self.jump_start_y = self.integration_start_time
