"""
Jump Estimation Mode - User inputs bodyweight manually, results based on impulse.
"""
from .base import (
    PhysicsMode, 
    AIR_THRESHOLD, 
    STABILITY_TOLERANCE_KG,
    GRAVITY
)


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
        self.manual_mass_kg = 75.0  # Default
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
                 
                 curve = engine.generate_power_curve(
                     self.jump_start_y, 
                     self.integration_start_time, 
                     self.manual_mass_kg, 
                     start_velocity=self.manual_start_velocity
                 )
                 
                 avg_p = 0
                 if self.power_sample_count > 0:
                        avg_p = self.sum_power / self.power_sample_count
                        
                 result = {
                    "timestamp": now,
                    "flight_time": flight_time_estimated_ms,  # Estimated from Impulse
                    "height_flight": None,
                    "height_impulse": h_impulse,
                    "peak_power": self.peak_power,
                    "avg_power": avg_p,
                    "formula_peak_power": None,
                    "formula_avg_power": None,
                    "velocity_takeoff": self.last_takeoff_velocity,
                    "velocity_flight": None,
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
                 if force_n > self.max_propulsion_force:
                     self.max_propulsion_force = force_n
                 
                 # Power accumulation
                 if (self.current_velocity + self.manual_start_velocity) > 0:
                     self.sum_power += instant_power
                     self.power_sample_count += 1
                 if instant_power > self.peak_power:
                     self.peak_power = instant_power

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
        if curr_idx < 0:
            curr_idx = engine.BUFFER_SIZE - 1
        
        best_start_index = curr_idx
        min_diff = 9999.0
        
        scan_count = 0
        limit = min(engine.buffer.shape[0], 600)
        
        while scan_count < limit:
            scan_idx = (engine.buf_idx - 1 - scan_count) % engine.BUFFER_SIZE
            pt = engine.buffer[scan_idx]
            
            if now - pt[0] > 600:
                break
            
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
                if d < 0:
                    d += 4294967295
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
            if steps > engine.BUFFER_SIZE:
                break
            
        self.integration_start_time = engine.buffer[start_index][0]
        self.jump_start_y = self.integration_start_time
