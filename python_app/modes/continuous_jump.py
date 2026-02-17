"""
Continuous Jump Mode - Chains multiple jumps, collecting per-jump metrics.

States:
    IDLE -> WEIGHING -> READY -> PROPULSION -> IN_AIR -> LANDING -> (loop) -> step-off -> RESULT

On step-off, emits one aggregated result with all individual jumps.
"""
from .base import (
    PhysicsMode, 
    AIR_THRESHOLD, 
    MOVEMENT_THRESHOLD, 
    STABILITY_TOLERANCE_KG,
    MAX_PROPULSION_TIME_MS,
    MIN_AIR_TIME,
    MAX_AIR_TIME,
)


class ContinuousJumpMode(PhysicsMode):
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
        self.last_takeoff_velocity = 0.0
        
        # Timing
        self.integration_start_time = 0.0
        self.takeoff_time = 0.0
        self.landing_time = 0.0
        self.jump_start_y = 0.0
        
        # Step-off detection
        self.low_weight_start_time = 0.0
        
        # Auto-tare
        self.idle_start_time = 0.0
        
        # --- Continuous-specific ---
        self.completed_jumps = []
        self.sequence_start_time = 0.0
        self.contact_start_time = 0.0
        self.current_jump_peak_power = 0.0
        self.current_jump_sum_power = 0.0
        self.current_jump_power_count = 0
        self.current_jump_max_force = 0.0

    def reset_state(self):
        """Reset all state variables."""
        self.state = "IDLE"
        self.weight_confirmed = False
        self.calibration_start_time = 0.0
        self.jumper_mass_kg = 0.0
        self.current_velocity = 0.0
        self.block_sum = 0.0
        self.block_count = 0
        self.block_averages = []
        self.low_weight_start_time = 0.0
        self.completed_jumps = []
        self.sequence_start_time = 0.0
        self.contact_start_time = 0.0
        self.idle_start_time = 0.0
        self._reset_jump_accumulators()

    def _reset_jump_accumulators(self):
        """Reset per-jump physics accumulators."""
        self.current_jump_peak_power = 0.0
        self.current_jump_sum_power = 0.0
        self.current_jump_power_count = 0
        self.current_jump_max_force = 0.0

    def process_sample(self, raw, now, dt):
        """Main sample processing."""
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        gravity = engine.config["gravity"]
        
        weight = raw - engine.zero_offset
        display_kg = weight / raw_per_kg
        result = None
        
        # --- STATE MACHINE ---
        
        # 1. IN_AIR - waiting for landing
        if self.state == "IN_AIR":
            current_air_time = now - self.takeoff_time
            
            if weight >= AIR_THRESHOLD:
                if current_air_time >= MIN_AIR_TIME:
                    self._handle_landing(now, current_air_time, gravity)
                    
            elif current_air_time > MAX_AIR_TIME:
                result = self._finalize_sequence(now, gravity)
                self.state = "IDLE"
                self.weight_confirmed = False
                
            return self._make_response(display_kg, result)

        # 2. Takeoff detection
        if weight < AIR_THRESHOLD and self.current_velocity > 0:
            if self.state in ["READY", "PROPULSION", "LANDING"]:
                # Record contact time for the previous jump
                if self.state == "LANDING" and len(self.completed_jumps) > 0:
                    contact_time = now - self.contact_start_time
                    self.completed_jumps[-1]["contact_time"] = contact_time
                
                self.last_takeoff_velocity = self.current_velocity
                self.takeoff_time = now
                self.state = "IN_AIR"
                return self._make_response(display_kg, result)

        # 3. IDLE when weight is low (stepped off)
        if weight < AIR_THRESHOLD and self.state not in ["PROPULSION", "LANDING", "IN_AIR"]:
            if len(self.completed_jumps) > 0:
                result = self._finalize_sequence(now, gravity)
            
            if self.weight_confirmed:
                self.weight_confirmed = False
                self.jumper_mass_kg = 0
            self.state = "IDLE"
            self.calibration_start_time = 0
            
            # Auto-tare
            if self.idle_start_time == 0:
                self.idle_start_time = now
            elif now - self.idle_start_time > 1000:
                avg_val = self.engine.get_buffer_average(150)
                if abs(avg_val) > 0.2:
                    self.engine.start_tare()
                self.idle_start_time = now
            return self._make_response(display_kg, result)

        # 4. Active integration (PROPULSION or LANDING)
        if self.state in ["PROPULSION", "LANDING"]:
            result = self._process_integration(now, weight, display_kg, raw_per_kg, gravity, result)
        # 5. Weighing / Ready
        else:
            self._process_ready_state(now, weight, raw_per_kg)

        return self._make_response(display_kg, result)

    def _make_response(self, display_kg, result):
        return {
            "state": self.state,
            "kg": display_kg,
            "display_kg": display_kg,
            "result": result,
            "jumper_mass_kg": self.jumper_mass_kg,
            "velocity": self.current_velocity,
            "jump_count": len(self.completed_jumps),
            "completed_jumps": self.completed_jumps
        }

    def _handle_landing(self, now, current_air_time, gravity):
        """Process landing after flight phase."""
        self.landing_time = now
        self.contact_start_time = now
        
        t_sec = current_air_time / 1000.0
        height_flight = (gravity * t_sec * t_sec) / 8.0 * 100.0  # cm
        velocity_flight = gravity * (t_sec / 2.0)
        height_impulse = (self.last_takeoff_velocity**2) / (2 * gravity) * 100.0
        
        jump_data = {
            "jump_number": len(self.completed_jumps) + 1,
            "flight_time": current_air_time,
            "height_flight": height_flight,
            "height_impulse": height_impulse,
            "velocity_takeoff": self.last_takeoff_velocity,
            "velocity_flight": velocity_flight,
            "peak_power": self.current_jump_peak_power,
            "avg_power": self.current_jump_sum_power / max(1, self.current_jump_power_count),
            "max_force": self.current_jump_max_force / gravity if self.current_jump_max_force > 0 else 0,
            "takeoff_time": self.takeoff_time,
            "landing_time": now,
            "contact_time": None  # Filled on next takeoff
        }
        self.completed_jumps.append(jump_data)
        
        # Prepare for next jump (rebound)
        v_impact = -1.0 * velocity_flight
        self.current_velocity = v_impact
        self._reset_jump_accumulators()
        
        self.state = "LANDING"
        self.integration_start_time = now
        self.jump_start_y = now
        self.block_sum = 0
        self.block_count = 0
        self.block_averages = []

    def _process_integration(self, now, weight, display_kg, raw_per_kg, gravity, result):
        """Handle physics integration during PROPULSION or LANDING."""
        
        # Step-off detection using both weight AND velocity
        if weight < AIR_THRESHOLD and self.current_velocity <= 0:
            if self.low_weight_start_time == 0:
                self.low_weight_start_time = now
            else:
                elapsed = now - self.low_weight_start_time
                vel_near_zero = abs(self.current_velocity) < 0.1
                if (vel_near_zero and elapsed > 100) or elapsed > 500:
                    if len(self.completed_jumps) > 0:
                        result = self._finalize_sequence(now, gravity)
                    self.state = "IDLE"
                    self.weight_confirmed = False
                    self.jumper_mass_kg = 0
                    self.current_velocity = 0
                    self._reset_jump_accumulators()
                    return result
        else:
            self.low_weight_start_time = 0

        # Physics integration
        if self.jumper_mass_kg > 0 and now - self.integration_start_time <= MAX_PROPULSION_TIME_MS:
            force_n = display_kg * gravity
            net_force_n = (display_kg - self.jumper_mass_kg) * gravity
            acc = net_force_n / self.jumper_mass_kg
            
            self.current_velocity += acc * (1.0 / self.engine.config["frequency"])
            instant_power = force_n * self.current_velocity
            
            if force_n > self.current_jump_max_force:
                self.current_jump_max_force = force_n
            
            if self.current_velocity > 0:
                self.current_jump_sum_power += instant_power
                self.current_jump_power_count += 1
            
            if instant_power > self.current_jump_peak_power:
                self.current_jump_peak_power = instant_power
            
            result = self._check_stability_exit(now, display_kg, raw_per_kg, result)

        # Timeout
        if now - self.integration_start_time > MAX_PROPULSION_TIME_MS:
            self.state = "READY"
            self._reset_jump_accumulators()
            
        return result

    def _check_stability_exit(self, now, display_kg, raw_per_kg, result):
        """Check if weight has stabilized (jump sequence complete)."""
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
                
                if noise_kg <= STABILITY_TOLERANCE_KG * 2 and diff_bw <= STABILITY_TOLERANCE_KG * 4:
                    self.jumper_mass_kg = avg_val
                    self.static_weight_raw = avg_val * raw_per_kg
                    
                    if len(self.completed_jumps) > 0:
                        result = self._finalize_sequence(now, self.engine.config["gravity"])

                    self.state = "READY"
                    self._reset_jump_accumulators()
        
        return result

    def _process_ready_state(self, now, weight, raw_per_kg):
        """Handle WEIGHING calibration and READY trigger detection."""
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
                        self.completed_jumps = []
                self.calibration_start_time = 0
        else:
            diff = abs(weight - self.static_weight_raw)
            if diff > MOVEMENT_THRESHOLD:
                self.state = "PROPULSION"
                self.integration_start_time = now
                self.jump_start_y = now
                if self.sequence_start_time == 0:
                    self.sequence_start_time = now
            else:
                self.state = "READY"

    def _finalize_sequence(self, now, gravity):
        """Build the aggregated result from all completed jumps."""
        if len(self.completed_jumps) == 0:
            return None
        
        jumps = self.completed_jumps
        
        heights = [j["height_flight"] for j in jumps]
        flight_times = [j["flight_time"] for j in jumps]
        contact_times = [j["contact_time"] for j in jumps if j["contact_time"] is not None]
        
        avg_height = sum(heights) / len(heights) if heights else 0
        best_height = max(heights) if heights else 0
        avg_contact_time = sum(contact_times) / len(contact_times) if contact_times else 0
        best_contact_time = min(contact_times) if contact_times else 0
        
        # Generate combined power curve for the entire sequence
        engine = self.engine
        curve_start = self.sequence_start_time - 600 if self.sequence_start_time > 0 else now - 5000
        curve = engine.generate_power_curve(
            curve_start,
            now,
            self.jumper_mass_kg,
            start_velocity=0
        )
        
        result = {
            "timestamp": now,
            "jump_count": len(jumps),
            "avg_height": avg_height,
            "best_height": best_height,
            "avg_contact_time": avg_contact_time,
            "best_contact_time": best_contact_time,
            "avg_flight_time": sum(flight_times) / len(flight_times) if flight_times else 0,
            "jumper_weight": self.jumper_mass_kg,
            "height_flight": best_height,
            "flight_time": sum(flight_times),
            "peak_power": max(j["peak_power"] for j in jumps) if jumps else 0,
            "avg_power": sum(j["avg_power"] for j in jumps) / len(jumps) if jumps else 0,
            "max_force": max(j["max_force"] for j in jumps) if jumps else 0,
            "velocity_takeoff": max(j["velocity_takeoff"] for j in jumps) if jumps else 0,
            "force_curve": curve,
            "curve_start_time": curve_start,
            "sub_jumps": jumps
        }
        
        # Reset for next sequence
        self.completed_jumps = []
        self.sequence_start_time = 0
        
        return result
