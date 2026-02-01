"""
Single Jump Mode - Measures bodyweight automatically and tracks a complete jump cycle.

States:
    IDLE -> WEIGHING -> READY -> PROPULSION -> IN_AIR -> LANDING -> READY
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
        
        # Weighing calibration
        self.weight_confirmed = False
        self.calibration_start_time = 0.0
        self.calibration_sum = 0.0
        self.calibration_count = 0
        self.static_weight_raw = 0.0
        
        # Block-averaging for stability detection
        self.block_sum = 0.0
        self.block_count = 0
        self.block_averages = []
        
        self.jumper_mass_kg = 0.0
        
        # Physics integration
        self.current_velocity = 0.0
        self.peak_power = 0.0
        self.last_takeoff_velocity = 0.0
        self.max_propulsion_force = 0.0
        self.sum_power = 0.0
        self.power_sample_count = 0
        
        # Timing
        self.integration_start_time = 0.0
        self.takeoff_time = 0.0
        self.landing_time = 0.0
        self.jump_start_y = 0.0
        
        self.propulsion_stability_start_time = 0.0
        self.phase_start_velocity = 0.0
        
        # Result emission (delayed to capture landing graph)
        self.pending_result_data = None
        self.result_emit_time = 0.0
        
        # Phase tracking (unweighting -> braking -> propulsion)
        self.min_velocity = 0.0
        self.min_velocity_time = 0.0
        self.zero_crossing_time = 0.0
        self.unweighting_start_time = 0.0  # When velocity first left ~0 going negative
        self.unweighting_detected = False  # Flag to detect unweighting start once
        
        # Saved phase times (captured at takeoff for result reporting)
        self.saved_phase_times = None
        
        # Protection timers
        self.landing_protection_end_time = 0.0
        self.low_weight_start_time = 0.0

    def reset_state(self):
        """Reset all state variables to initial values."""
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
        self.block_averages = []
        self.phase_start_velocity = 0.0
        self.pending_result_data = None
        self.result_emit_time = 0.0
        self.landing_protection_end_time = 0.0
        self.low_weight_start_time = 0.0
        self.min_velocity = 0.0
        self.min_velocity_time = 0.0
        self.zero_crossing_time = 0.0
        self.unweighting_start_time = 0.0
        self.unweighting_detected = False
        self.saved_phase_times = None

    def _reset_integration_accumulators(self):
        """Reset physics integration variables for a new phase."""
        self.current_velocity = 0.0
        self.peak_power = 0.0
        self.sum_power = 0.0
        self.power_sample_count = 0
        self.block_sum = 0
        self.block_count = 0
        self.block_averages = []
        self.propulsion_stability_start_time = 0.0
        self.min_velocity = 0.0
        self.min_velocity_time = 0.0
        self.zero_crossing_time = 0.0
        self.unweighting_start_time = 0.0
        self.unweighting_detected = False
        self.saved_phase_times = None

    def _try_emit_result(self, now, force=False):
        """
        Emit pending result if ready, or immediately if forced.
        Returns the result dict or None.
        """
        if self.pending_result_data is None:
            return None
            
        if not force and now < self.result_emit_time:
            return None
            
        engine = self.engine
        d = self.pending_result_data
        
        # Generate power curve with some context before the jump
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
            "avg_power_start_time": d["avg_power_start_time"],
            # Phase timing data
            "phase_times": d.get("phase_times"),
            "curve_start_time": d["graph_start_time_y"] - 600
        }
        
        self.pending_result_data = None
        return result

    def process_sample(self, raw, timestamp, micros, now, dt):
        """
        Main sample processing - handles state machine and physics integration.
        Returns dict with current state, weight, and optional result.
        """
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        # Convert raw reading to weight
        weight = raw - engine.zero_offset
        display_kg = weight / raw_per_kg
        result = None
        
        # --- STATE MACHINE ---
        
        # 1. IN_AIR state - waiting for landing
        if self.state == "IN_AIR":
            current_air_time = now - self.takeoff_time
            
            if weight >= AIR_THRESHOLD:
                # Landing detected
                if current_air_time >= MIN_AIR_TIME:
                    self._handle_landing(now, current_air_time, gravity)
                    
            elif current_air_time > MAX_AIR_TIME:
                # Timeout - jumped off platform
                self.state = "IDLE"
                self.weight_confirmed = False
                
            return self._make_response(display_kg, result)

        # 2. Takeoff detection (priority check)
        if weight < AIR_THRESHOLD and self.current_velocity > 0:
            if self.state in ["READY", "PROPULSION", "LANDING"]:
                # Save phase times before they get reset
                self.saved_phase_times = {
                    "unweighting_start": self.unweighting_start_time,
                    "min_velocity_time": self.min_velocity_time,
                    "zero_crossing_time": self.zero_crossing_time,
                    "takeoff_time": now
                }
                result = self._try_emit_result(now, force=True)
                self.last_takeoff_velocity = self.current_velocity
                self.takeoff_time = now
                self.state = "IN_AIR"
                return self._make_response(display_kg, result)

        # 3. IDLE reset when weight is low (stepped off platform)
        if weight < AIR_THRESHOLD and self.state not in ["PROPULSION", "LANDING", "IN_AIR"]:
            if self.weight_confirmed:
                self.weight_confirmed = False
                self.jumper_mass_kg = 0
            self.state = "IDLE"
            self.calibration_start_time = 0
            return self._make_response(display_kg, result)

        # 4. Active integration (PROPULSION or LANDING)
        if self.state in ["PROPULSION", "LANDING"]:
            result = self._process_integration_state(now, weight, display_kg, raw_per_kg, gravity, result)
        # 5. Weighing / Ready state 
        else:
            self._process_ready_state(now, weight, raw_per_kg)

        return self._make_response(display_kg, result)

    def _make_response(self, display_kg, result):
        """Create standard response dict."""
        return {
            "state": self.state,
            "kg": display_kg,
            "display_kg": display_kg,
            "result": result,
            "jumper_mass_kg": self.jumper_mass_kg,
            "velocity": self.current_velocity
        }

    def _handle_landing(self, now, current_air_time, gravity):
        """Process landing after flight phase."""
        self.landing_time = now
        
        # Calculate jump metrics from flight time
        t_sec = current_air_time / 1000.0
        height_flight = (gravity * t_sec * t_sec) / 8.0 * 100.0  # cm
        velocity_flight = gravity * (t_sec / 2.0)
        
        # Power formulas (Harman & Sayers)
        harman = max(0, (21.2 * height_flight) + (23.0 * self.jumper_mass_kg) - 1393)
        sayers = max(0, (60.7 * height_flight) + (45.3 * self.jumper_mass_kg) - 2055)
        
        # Height from impulse-momentum
        height_impulse = (self.last_takeoff_velocity**2) / (2 * gravity) * 100.0
        
        # Store result for delayed emission (to capture landing graph)
        self.pending_result_data = {
            "timestamp": self.landing_time,
            "flight_time": current_air_time,
            "height_flight": height_flight,
            "height_impulse": height_impulse,
            "peak_power": self.peak_power,
            "avg_power": self.sum_power / max(1, self.power_sample_count),
            "formula_peak_power": sayers,
            "formula_avg_power": harman,
            "velocity_takeoff": self.last_takeoff_velocity,
            "velocity_flight": velocity_flight,
            "max_force": self.max_propulsion_force / gravity,
            "jumper_weight": self.jumper_mass_kg,
            "avg_power_start_time": self.integration_start_time,
            "graph_start_velocity": self.phase_start_velocity,
            "graph_start_time_y": self.jump_start_y,
            "phase_times": self.saved_phase_times  # Phase timing data
        }
        self.result_emit_time = now + 600  # 600ms delay to capture landing
        
        # Prepare for potential rebound jump
        v_impact = -1.0 * velocity_flight
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

    def _process_integration_state(self, now, weight, display_kg, raw_per_kg, gravity, result):
        """Handle physics integration during PROPULSION or LANDING states."""
        
        # Check for pending result emission
        if self.state == "LANDING":
            res = self._try_emit_result(now)
            if res:
                result = res

        # Step-off detection (low weight + negative velocity = user stepped off)
        if weight < AIR_THRESHOLD and self.current_velocity < 0:
            if self.low_weight_start_time == 0:
                self.low_weight_start_time = now
            elif now - self.low_weight_start_time > 500:  # 500ms timeout
                self.state = "IDLE"
                self.weight_confirmed = False
                self.jumper_mass_kg = 0
                self.current_velocity = 0
                self._reset_integration_accumulators()
                return result
        else:
            self.low_weight_start_time = 0

        # Physics integration (within time limit)
        if self.jumper_mass_kg > 0 and now - self.integration_start_time <= MAX_PROPULSION_TIME_MS:
            self._integrate_sample(now, display_kg, raw_per_kg, gravity)
            result = self._check_stability_exit(now, display_kg, raw_per_kg, result)

        # Timeout - return to READY
        if now - self.integration_start_time > MAX_PROPULSION_TIME_MS:
            self.state = "READY"
            self._reset_integration_accumulators()
            
        return result

    def _integrate_sample(self, now, display_kg, raw_per_kg, gravity):
        """Perform physics integration for one sample and track phase transitions."""
        force_n = display_kg * gravity
        net_kg = display_kg - self.jumper_mass_kg
        net_force_n = net_kg * gravity
        acc = net_force_n / self.jumper_mass_kg
        
        # Store previous velocity before updating
        prev_vel = self.current_velocity
        
        self.current_velocity += acc * (1.0 / self.engine.config["frequency"])
        instant_power = force_n * self.current_velocity
        
        # --- Phase transition detection ---
        
        # Detect unweighting start: when velocity drops below -0.1 for the first time,
        # look back to find where velocity was ~0 (between 0 and -0.02)
        if not self.unweighting_detected and self.current_velocity < -0.1:
            self.unweighting_detected = True
            self.unweighting_start_time = self._find_unweighting_start()
        
        # Track minimum velocity (end of unweighting phase)
        if self.current_velocity < self.min_velocity:
            self.min_velocity = self.current_velocity
            self.min_velocity_time = now
        
        # Track zero crossing (start of propulsion phase)
        # Detected when velocity crosses from negative to positive
        if prev_vel < 0 and self.current_velocity >= 0 and self.zero_crossing_time == 0:
            self.zero_crossing_time = now
        
        if force_n > self.max_propulsion_force:
            self.max_propulsion_force = force_n
        
        # Only count positive power (pushing up)
        if self.current_velocity > 0:
            self.sum_power += instant_power
            self.power_sample_count += 1
        
        if instant_power > self.peak_power:
            self.peak_power = instant_power
    
    def _find_unweighting_start(self):
        """
        Look back through buffer to find where velocity was ~0 (between 0 and -0.02).
        This is the true start of the unweighting phase.
        """
        engine = self.engine
        gravity = engine.config["gravity"]
        
        # Look back up to 200 samples (~150ms)
        lookback_count = 200
        start_index = (engine.buf_idx - lookback_count) % engine.BUFFER_SIZE
        
        # Integrate forward from lookback, tracking velocity and timestamps
        v = 0.0
        last_u = engine.buffer[start_index][2]
        if last_u == 0:
            last_u = engine.buffer[start_index][0] * 1000
        
        last_zero_time = engine.buffer[start_index][0]  # Default to start
        
        steps = 0
        i = start_index
        while i != engine.buf_idx:
            b = engine.buffer[i]
            if b[0] == 0:
                i = (i + 1) % engine.BUFFER_SIZE
                steps += 1
                if steps > lookback_count:
                    break
                continue
            
            # Calculate dt
            iter_dt = 1.0 / engine.config["frequency"]
            if b[2] > 0 and last_u > 0:
                d = b[2] - last_u
                if d < 0:
                    d += 4294967295
                if 0 < d < 100000:
                    iter_dt = d / 1000000.0
            last_u = b[2]
            
            # Before integration, check if velocity is in ~0 range
            if -0.02 <= v <= 0.02:
                last_zero_time = b[0]
            
            # Integrate
            force_kg = b[1]
            net_kg = force_kg - self.jumper_mass_kg
            net_force_n = net_kg * gravity
            acc = net_force_n / self.jumper_mass_kg
            v += acc * iter_dt
            
            i = (i + 1) % engine.BUFFER_SIZE
            steps += 1
            if steps >= lookback_count:
                break
        
        return last_zero_time

    def _check_stability_exit(self, now, display_kg, raw_per_kg, result):
        """Check if weight has stabilized (jump complete, return to READY)."""
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
                
                # Stable if noise and drift are within tolerance
                if noise_kg <= STABILITY_TOLERANCE_KG * 2 and diff_bw <= STABILITY_TOLERANCE_KG * 4: 
                    self.jumper_mass_kg = avg_val
                    self.static_weight_raw = avg_val * raw_per_kg
                    res = self._try_emit_result(now, force=True)
                    if res:
                        result = res

                    self.state = "READY"
                    self._reset_integration_accumulators()
                    self.phase_start_velocity = 0.0
                    self.pending_result_data = None 
        
        return result

    def _process_ready_state(self, now, weight, raw_per_kg):
        """Handle WEIGHING calibration and READY trigger detection."""
        if not self.weight_confirmed:
            # WEIGHING state - calibrate bodyweight
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
            
            # Block averaging for noise detection
            self.block_sum += weight
            self.block_count += 1
            if self.block_count >= 25:
                self.block_averages.append(self.block_sum / 25.0)
                self.block_sum = 0
                self.block_count = 0
            
            # Check calibration after 300ms
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
            # READY state - detect movement to trigger propulsion
            diff = abs(weight - self.static_weight_raw)
            if diff > MOVEMENT_THRESHOLD:
                self.state = "PROPULSION"
                self.integration_start_time = now
                self.jump_start_y = now
                self._retroactive_propulsion_fix(now)
            else:
                self.state = "READY"
                self.phase_start_velocity = 0.0

    def _retroactive_propulsion_fix(self, now):
        """
        Rewind integration to ~77ms before trigger detection.
        This captures the full propulsion phase that started before we detected movement.
        """
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        lookback_count = 100  # ~77ms at 1300Hz
        start_index = (engine.buf_idx - lookback_count) % engine.BUFFER_SIZE
        
        start_pt = engine.buffer[start_index]
        self.integration_start_time = start_pt[0]
        self.jump_start_y = start_pt[0]
            
        # Reset accumulators
        self.current_velocity = 0
        self.peak_power = 0
        self.sum_power = 0
        self.power_sample_count = 0
        self.max_propulsion_force = 0
        
        # Forward integrate from lookback point
        last_buf_micros = engine.buffer[start_index][2]
        if last_buf_micros == 0:
            last_buf_micros = engine.buffer[start_index][0] * 1000
            
        steps = 0
        i = start_index
        while i != engine.buf_idx:
            b = engine.buffer[i]
            
            # Skip invalid buffer entries
            if b[0] == 0:
                i = (i + 1) % engine.BUFFER_SIZE
                steps += 1
                if steps > lookback_count:
                    break
                continue

            # Calculate dt from micros timestamps
            iter_dt = 1.0 / engine.config["frequency"]
            if b[2] > 0 and last_buf_micros > 0:
                d = b[2] - last_buf_micros
                if d < 0:
                    d += 4294967295  # Handle micros overflow
                if 0 < d < 100000:
                    iter_dt = d / 1000000.0
            last_buf_micros = b[2]
            
            # Integrate this sample
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
        
        self.phase_start_velocity = 0.0
