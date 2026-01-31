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
        self.landing_protection_end_time = 0.0  # Bounce protection
        self.low_weight_start_time = 0.0  # Step-off detection timer

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
        self.result_emit_time = 0.0
        self.landing_protection_end_time = 0.0
        self.low_weight_start_time = 0.0

    def _reset_integration_accumulators(self):
        self.current_velocity = 0.0
        self.peak_power = 0.0
        self.sum_power = 0.0
        self.power_sample_count = 0
        self.block_sum = 0
        self.block_count = 0
        self.block_averages = []
        self.propulsion_stability_start_time = 0.0
        self.block_averages = []
        self.propulsion_stability_start_time = 0.0


    def _try_emit_result(self, now, force=False):
        """
        Emits the pending result if the time has come, or if forced.
        """
        if self.pending_result_data is None:
            return None
            
        if not force and now < self.result_emit_time:
            return None
            
        engine = self.engine
        d = self.pending_result_data
        
        # Determine graph window. 
        # If we are forcing (e.g. early exit), we want to capture up to NOW.
        # But generally we want a bit of context.
        t_start = d["graph_start_time_y"] - 600
        
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
        return result

    def process_sample(self, raw, timestamp, micros, now, dt):
        engine = self.engine
        
        # 1. Raw to Net
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        weight = raw - engine.zero_offset
        
        display_kg = weight / raw_per_kg
        result = None
        
        # --- STATE MACHINE AND PHYSICS INTEGRATION ---
        
        # 1. Handle IN_AIR State (Flight Phase)
        if self.state == "IN_AIR":
            current_air_time = now - self.takeoff_time
            
            if weight >= AIR_THRESHOLD:  # Landing
                if current_air_time >= MIN_AIR_TIME:
                    self.landing_time = now
                    
                    # --- CALCULATE CORE STATS (Snapshot) ---
                    t_sec = current_air_time / 1000.0
                    h = (gravity * t_sec * t_sec) / 8.0 * 100.0
                    v_flight = gravity * (t_sec / 2.0)
                    
                    harman = (21.2 * h) + (23.0 * self.jumper_mass_kg) - 1393
                    harman = max(0, harman)
                    
                    sayers = (60.7 * h) + (45.3 * self.jumper_mass_kg) - 2055
                    sayers = max(0, sayers)
                    
                    h_impulse = (self.last_takeoff_velocity**2) / (2 * gravity) * 100.0
                    
                    # Prepare data for delayed emission
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
                        "graph_start_velocity": self.phase_start_velocity,
                        "graph_start_time_y": self.jump_start_y
                    }
                    self.result_emit_time = now + 600 # Wait 600ms to capture landing
                    
                    # --- PREPARE FOR REBOUND ---
                    v_impact = -1.0 * v_flight
                    self.current_velocity = v_impact
                    
                    self.peak_power = 0
                    self.sum_power = 0
                    self.power_sample_count = 0
                    self.max_propulsion_force = 0
                    
                    self.state = "LANDING"
                    self.integration_start_time = now
                    self.jump_start_y = now 
                    
                    self.block_sum = 0
                    self.block_count = 0
                    self.block_averages = []
                    
                    self.phase_start_velocity = v_impact
                    
                # else:
                #     # Ignore short spikes (board bounce) < MIN_AIR_TIME.
                #     # We interpret high weight shortly after takeoff as vibration/bounce, 
                #     # not a true landing. Stay in IN_AIR.
                #     pass
                        
            elif current_air_time > MAX_AIR_TIME:
                self.state = "IDLE"
                self.weight_confirmed = False
            return {
                "state": self.state, "kg": display_kg, "display_kg": display_kg,
                "result": result, "jumper_mass_kg": self.jumper_mass_kg, "velocity": self.current_velocity
            }

        # 2. Check for Takeoff (Priority Mechanism)
        # Transition to IN_AIR if weight is low AND we have positive velocity.
        if weight < AIR_THRESHOLD and self.current_velocity > 0:
             if self.state in ["READY", "PROPULSION", "LANDING"]:
                result = self._try_emit_result(now, force=True)
                self.last_takeoff_velocity = self.current_velocity
                self.takeoff_time = now
                self.state = "IN_AIR"
                return {
                    "state": self.state, "kg": display_kg, "display_kg": display_kg,
                    "result": result, "jumper_mass_kg": self.jumper_mass_kg, "velocity": self.current_velocity
                }

        # 3. Handle IDLE Reset when weight is low and we are NOT integrating
        if weight < AIR_THRESHOLD and self.state not in ["PROPULSION", "LANDING", "IN_AIR"]:
            if self.weight_confirmed:
                self.weight_confirmed = False
                self.jumper_mass_kg = 0
            self.state = "IDLE"
            self.calibration_start_time = 0
            return {
                "state": self.state, "kg": display_kg, "display_kg": display_kg,
                "result": result, "jumper_mass_kg": self.jumper_mass_kg, "velocity": self.current_velocity
            }


        # 4. Active Integration (PROPULSION or LANDING)
        # This block runs regardless of weight (handling unweighting dips) as long as we haven't taken off
        if self.state in ["PROPULSION", "LANDING"]:
             # Check for pending result emission if in LANDING
             if self.state == "LANDING":
                 res = self._try_emit_result(now)
                 if res: result = res

             # --- STEP-OFF DETECTION ---
             # If user steps off (weight=0) while velocity < 0 (free fall from physics pov), return to IDLE
             if weight < AIR_THRESHOLD and self.current_velocity < 0:
                 if self.low_weight_start_time == 0:
                     self.low_weight_start_time = now
                 elif now - self.low_weight_start_time > 500: # 0.5s timeout
                     self.state = "IDLE"
                     self.weight_confirmed = False
                     self.jumper_mass_kg = 0
                     self.current_velocity = 0
                     self._reset_integration_accumulators()
                     return {
                        "state": self.state, "kg": display_kg, "display_kg": display_kg,
                        "result": result, "jumper_mass_kg": 0, "velocity": 0
                     }
             else:
                 self.low_weight_start_time = 0

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

                 # --- STABILITY EXIT LOGIC ---
                 self.block_sum += display_kg
                 self.block_count += 1
                 
                 if self.block_count >= 20:
                     avg = self.block_sum / 20.0
                     self.block_averages.append(avg)
                     self.block_sum = 0
                     self.block_count = 0
                     
                     if len(self.block_averages) >= 10:
                         self.block_averages = self.block_averages[-10:]
                         b_min = min(self.block_averages)
                         b_max = max(self.block_averages)
                         noise_kg = b_max - b_min
                         avg_val = sum(self.block_averages) / len(self.block_averages)
                         diff_bw = abs(avg_val - self.jumper_mass_kg)
                         
                         if noise_kg <= STABILITY_TOLERANCE_KG*2 and diff_bw <= STABILITY_TOLERANCE_KG*4: 
                             self.jumper_mass_kg = avg_val
                             self.static_weight_raw = avg_val * raw_per_kg
                             res = self._try_emit_result(now, force=True)
                             if res: result = res

                             self.state = "READY"
                             self._reset_integration_accumulators()
                             self.phase_start_velocity = 0.0
                             self.pending_result_data = None 

             if now - self.integration_start_time > MAX_PROPULSION_TIME_MS:
                  self.state = "READY"
                  self._reset_integration_accumulators()
                  
        # 5. Calibration / Trigger Logic (When NOT integrating)
        # This implies we are in READY/WEIGHING and weight >= AIR_THRESHOLD 
        # (since lower weight handled by IDLE Reset)
        else:
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
                 
                 self.block_sum += weight
                 self.block_count += 1
                 if self.block_count >= 25:
                     self.block_averages.append(self.block_sum / 25.0)
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
                 # READY state - Check Trigger
                 diff = abs(weight - self.static_weight_raw)
                 if diff > MOVEMENT_THRESHOLD:
                     self.state = "PROPULSION"
                     self.integration_start_time = now
                     self.jump_start_y = now
                     self._retroactive_propulsion_fix(now)
                 else:
                     self.state = "READY"
                     self.phase_start_velocity = 0.0 # Reset velocity if settled

        return {
            "state": self.state,
            "kg": display_kg,
            "display_kg": display_kg,
            "result": result,
            "jumper_mass_kg": self.jumper_mass_kg,
            "velocity": self.current_velocity
        }

    def _retroactive_propulsion_fix(self, now):
        """
        Simple retroactive logic: Start integration 100 samples (~77ms) before the trigger.
        Assumes the user was static at that point.
        """
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        # Fixed lookback of 100 samples
        lookback_count = 100
        start_index = (engine.buf_idx - lookback_count) % engine.BUFFER_SIZE
        
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
            
            # Skip empty/invalid points if near start of execution
            if b[0] == 0:
                 i = (i + 1) % engine.BUFFER_SIZE
                 steps += 1
                 if steps > lookback_count: break
                 continue

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
            if steps >= lookback_count:
                break
        
        # Retroactive fix assumes static start, so phase velocity is 0
        self.phase_start_velocity = 0.0
