"""
Single Jump Mode - Measures bodyweight automatically and tracks a complete jump cycle.
"""
from .base import (
    PhysicsMode, 
    AIR_THRESHOLD, 
    MOVEMENT_THRESHOLD, 
    STABILITY_TOLERANCE_KG,
    MAX_PROPULSION_TIME_MS,
    MIN_AIR_TIME,
    MAX_AIR_TIME
)


class SingleJumpMode(PhysicsMode):
    def __init__(self, engine):
        super().__init__(engine)
        self.state = "IDLE"
        
        # State variables specific to Single Jump
        self.weight_confirmed = False
        self.calibration_start_time = 0.0
        self.calibration_sum = 0.0
        self.calibration_count = 0
        self.static_weight_raw = 0.0
        
        # Block-averaging for stability
        self.block_sum = 0.0
        self.block_count = 0
        self.block_averages = []
        
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
        
        self.phase_start_velocity = 0.0
        self.pending_result_data = None
        self.result_emit_time = 0.0

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
        self.block_sum = 0.0
        self.block_count = 0
        self.block_count = 0
        self.block_averages = []
        self.phase_start_velocity = 0.0
        self.pending_result_data = None
        self.result_emit_time = 0.0

    def process_sample(self, raw, timestamp, micros, now, dt):
        engine = self.engine
        
        # 1. Raw to Net
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        weight = raw - engine.zero_offset
        
        display_kg = weight / raw_per_kg
        result = None
        
        # --- STATE MACHINE ---
        if self.state == "IN_AIR":
            current_air_time = now - self.takeoff_time
            
            if weight >= AIR_THRESHOLD:  # Landing
                if current_air_time >= MIN_AIR_TIME:
                    self.landing_time = now
                    
                    # --- 1. CALCULATE CORE STATS (Snapshot) ---
                    t_sec = current_air_time / 1000.0
                    h = (gravity * t_sec * t_sec) / 8.0 * 100.0
                    v_flight = gravity * (t_sec / 2.0)
                    
                    harman = (21.2 * h) + (23.0 * self.jumper_mass_kg) - 1393
                    harman = max(0, harman)
                    
                    sayers = (60.7 * h) + (45.3 * self.jumper_mass_kg) - 2055
                    sayers = max(0, sayers)
                    
                    h_impulse = (self.last_takeoff_velocity**2) / (2 * gravity) * 100.0
                    
                    # Prepare data for delayed emission
                    # Note: We store the 'start_velocity' of the jump that just finished
                    # so we can render its graph correctly later.
                    self.pending_result_data = {
                        "timestamp": self.landing_time,
                        "flight_time": current_air_time,
                        "height_flight": h,
                        "height_impulse": h_impulse,
                        "peak_power": self.peak_power,
                        "avg_power": self.sum_power / max(1, self.power_sample_count),
                        "formula_peak_power": sayers,
                        "formula_avg_power": harman,
                        "velocity_takeoff": self.last_takeoff_velocity,
                        "velocity_flight": v_flight,
                        "max_force": self.max_propulsion_force / gravity,
                        "jumper_weight": self.jumper_mass_kg,
                        "avg_power_start_time": self.integration_start_time,
                        # IMPORTANT: Store the start velocity used for THIS jump phase
                        "graph_start_velocity": self.phase_start_velocity,
                        "graph_start_time_y": self.jump_start_y
                    }
                    self.result_emit_time = now + 300 # Wait 300ms to capture landing
                    
                    # --- 2. PREPARE FOR REBOUND (Continuity) ---
                    # Impact logic
                    v_impact = -1.0 * v_flight
                    
                    self.current_velocity = v_impact
                    
                    # Reset Accumulators for the NEXT phase
                    self.peak_power = 0
                    self.sum_power = 0
                    self.power_sample_count = 0
                    self.max_propulsion_force = 0
                    
                    # Transition
                    self.state = "LANDING"
                    self.integration_start_time = now
                    self.jump_start_y = now # Mark start of new cycle
                    
                    # Reset stability counters for LANDING exit
                    self.block_sum = 0
                    self.block_count = 0
                    self.block_averages = []
                    
                    # The NEXT jump starts with this velocity
                    self.phase_start_velocity = v_impact
                    
                else:
                    self.state = "READY"
            elif current_air_time > MAX_AIR_TIME:
                self.state = "IDLE"
                self.weight_confirmed = False
                
        elif weight < AIR_THRESHOLD:
            # Handle delayed result emission if we takeoff before 300ms (Rebound)
            if self.pending_result_data is not None:
                # Force emit result now because we are leaving the ground
                d = self.pending_result_data
                t_start = d["graph_start_time_y"] - 1000
                curve = engine.generate_power_curve(
                    t_start, 
                    d["avg_power_start_time"], 
                    d["jumper_weight"],
                    start_velocity=d["graph_start_velocity"]
                )
                
                result = {
                    "timestamp": d["timestamp"],
                    "flight_time": d["flight_time"],
                    "height_flight": d["height_flight"],
                    "height_impulse": d["height_impulse"],
                    "peak_power": d["peak_power"],
                    "avg_power": d["avg_power"],
                    "formula_peak_power": d["formula_peak_power"],
                    "formula_avg_power": d["formula_avg_power"],
                    "velocity_takeoff": d["velocity_takeoff"],
                    "velocity_flight": d["velocity_flight"],
                    "max_force": d["max_force"],
                    "jumper_weight": d["jumper_weight"],
                    "force_curve": curve,
                    "avg_power_start_time": d["avg_power_start_time"]
                }
                self.pending_result_data = None


            if self.state in ["READY", "PROPULSION", "LANDING"]:
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
                    self.block_sum = 0
                    self.block_count = 0
                    self.block_averages = []
                
                self.calibration_sum += weight
                self.calibration_count += 1
                
                # Block accumulation
                self.block_sum += weight
                self.block_count += 1
                if self.block_count >= 30:
                    self.block_averages.append(self.block_sum / 30.0)
                    self.block_sum = 0
                    self.block_count = 0
                
                if now - self.calibration_start_time >= 300:
                    if len(self.block_averages) > 0:
                        b_min = min(self.block_averages)
                        b_max = max(self.block_averages)
                        noise_kg = (b_max - b_min) / raw_per_kg
                        
                        if noise_kg <= STABILITY_TOLERANCE_KG:
                            self.static_weight_raw = self.calibration_sum / self.calibration_count
                            self.jumper_mass_kg = self.static_weight_raw / raw_per_kg
                            self.weight_confirmed = True
                            self.state = "READY"
                    
                    self.calibration_start_time = 0
            else:
                # READY or PROPULSION or LANDING
                
                # Check for pending result emission
                if self.state == "LANDING" and self.pending_result_data is not None:
                   if now >= self.result_emit_time:
                       d = self.pending_result_data
                       t_start = d["graph_start_time_y"] - 1000
                       # Graph includes landing phase now
                       curve = engine.generate_power_curve(
                           t_start, 
                           d["avg_power_start_time"], 
                           d["jumper_weight"],
                           start_velocity=d["graph_start_velocity"]
                        )
                       
                       result = {
                           "timestamp": d["timestamp"],
                           "flight_time": d["flight_time"],
                           "height_flight": d["height_flight"],
                           "height_impulse": d["height_impulse"],
                           "peak_power": d["peak_power"],
                           "avg_power": d["avg_power"],
                           "formula_peak_power": d["formula_peak_power"],
                           "formula_avg_power": d["formula_avg_power"],
                           "velocity_takeoff": d["velocity_takeoff"],
                           "velocity_flight": d["velocity_flight"],
                           "max_force": d["max_force"],
                           "jumper_weight": d["jumper_weight"],
                           "force_curve": curve,
                           "avg_power_start_time": d["avg_power_start_time"]
                       }
                       self.pending_result_data = None
                
                if self.state not in ["PROPULSION", "LANDING"]:
                    diff = abs(weight - self.static_weight_raw)
                    if diff > MOVEMENT_THRESHOLD:
                        self.state = "PROPULSION"
                        self.integration_start_time = now
                        self.jump_start_y = now
                        
                        # Retroactive Fix
                        self._retroactive_propulsion_fix(now)
                    else:
                        self.state = "READY"
                        self.phase_start_velocity = 0.0 # Reset velocity if we settle
                        
                else:
                    # IN PROPULSION or LANDING
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
                            

                        # Exit Condition (PROPULSION)
                        diff_mass = abs(display_kg - self.jumper_mass_kg)
                        if self.state == "PROPULSION":
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
                            
                        # LANDING Exit Stability Check
                        if self.state == "LANDING":
                            self.block_sum += display_kg
                            self.block_count += 1
                            
                            if self.block_count >= 30:
                                avg = self.block_sum / 30.0
                                self.block_averages.append(avg)
                                self.block_sum = 0
                                self.block_count = 0
                                
                                # We need 10 blocks (300 samples)
                                if len(self.block_averages) >= 10:
                                    # Keep only last 10
                                    self.block_averages = self.block_averages[-10:]
                                    
                                    b_min = min(self.block_averages)
                                    b_max = max(self.block_averages)
                                    noise_kg = b_max - b_min
                                    
                                    # Check stability and bodyweight
                                    # Using slightly looser tolerance for bodyweight check in dynamic phase ??
                                    # User said "around current bodyweight"
                                    # STABILITY_TOLERANCE_KG is 0.5kg usually
                                    
                                    avg_val = sum(self.block_averages) / len(self.block_averages)
                                    diff_bw = abs(avg_val - self.jumper_mass_kg)
                                    
                                    if noise_kg <= STABILITY_TOLERANCE_KG and diff_bw <= STABILITY_TOLERANCE_KG * 4: 
                                        # *4 tolerance (2kg) because landing might be slightly noisy/off but stable enough to exit
                                        # Or strict tolerance? User said "around current bodyweight".
                                        # Let's stick to provided tolerance or slightly larger.
                                        # Let's use 2.0kg for bodyweight proximity to be safe, but keep noise strict.
                                        
                                        self.state = "READY"
                                        self.current_velocity = 0
                                        self.peak_power = 0
                                        self.sum_power = 0
                                        self.power_sample_count = 0
                                        self.phase_start_velocity = 0.0
                                        self.pending_result_data = None # Stop any pending emission if we settled

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
            "jumper_mass_kg": self.jumper_mass_kg,
            "velocity": self.current_velocity
        }

    def _retroactive_propulsion_fix(self, now):
        """Re-calcs velocity from buffer start based on movement threshold"""
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        curr_idx = engine.buf_idx - 1
        if curr_idx < 0:
            curr_idx = engine.BUFFER_SIZE - 1
        
        # Search for the best start point (closest to bodyweight)
        best_start_index = curr_idx
        min_diff = 9999.0
        
        scan_count = 0
        limit = min(engine.buffer.shape[0], 600)
        
        while scan_count < limit:
            scan_idx = (engine.buf_idx - 1 - scan_count) % engine.BUFFER_SIZE
            pt = engine.buffer[scan_idx]
            
            if now - pt[0] > 600:
                break  # Look back window (ms)
                
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
                if d < 0:
                    d += 4294967295
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
            if steps > engine.BUFFER_SIZE:
                break
            
        self.integration_start_time = engine.buffer[start_index][0]
        self.jump_start_y = self.integration_start_time
        
        # Retroactive fix assumes static start, so velocity is 0
        self.phase_start_velocity = 0.0
