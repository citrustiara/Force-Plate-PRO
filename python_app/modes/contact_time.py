"""
Contact Time Mode - Tracks the sequence: Ready -> Propulsion -> Flight 1 -> Contact -> Flight 2.
Calculates contact time between two flights.
"""
from .base import PhysicsMode, AIR_THRESHOLD, MAX_AIR_TIME

class ContactTimeMode(PhysicsMode):
    def __init__(self, engine):
        super().__init__(engine)
        self.state = "READY"
        self.contact_start_time = 0.0
        self.contact_end_time = 0.0
        self.jumper_mass_kg = 0.0
        self.max_force = 0.0
        self.contact_duration = 0.0
        self.in_air_start_time = 0.0
        self.in_air_duration = 0.0
    
    def reset_state(self):
        self.state = "READY"
        self.contact_start_time = 0.0
        self.contact_end_time = 0.0
        self.jumper_mass_kg = 0.0
        self.contact_duration = 0.0
        self.max_force = 0.0
        self.in_air_duration = 0.0

    def process_sample(self, raw, timestamp, micros, now, dt):
        engine = self.engine
        raw_per_kg = engine.config["raw_per_kg"]
        
        # We use raw weight for thresholding
        weight = raw - engine.zero_offset
            
        display_kg = weight / raw_per_kg
        result = None
        
        # --- STATE MACHINE ---
        # States: READY -> PROPULSION -> IN_AIR_1 -> CONTACT -> IN_AIR_2 (RESULT)
        
        if self.state == "READY":
            # Nothing on platform
            if weight > AIR_THRESHOLD:
                self.state = "PROPULSION"
                
        elif self.state == "PROPULSION":
            # On platform
            if weight < AIR_THRESHOLD:
                self.in_air_start_time = now
                self.state = "IN_AIR_1"
                
        elif self.state == "IN_AIR_1":
            # first jump
            self.in_air_duration = now - self.in_air_start_time
            if self.in_air_duration > MAX_AIR_TIME:
                self.reset_state()
            if weight > AIR_THRESHOLD:
                self.state = "CONTACT"
                self.contact_start_time = now
                
        elif self.state == "CONTACT":
            # kontakt i liczenie
            if weight > (self.max_force * engine.config["raw_per_kg"]):
                 self.max_force = display_kg
                 
            if weight < AIR_THRESHOLD:
                self.in_air_start_time = now
                self.contact_end_time = now
                self.state = "IN_AIR_2"
                #TODO!!!!!! zmienic z 
                # Calculate result
                self.contact_duration = self.contact_end_time - self.contact_start_time
                
                
        elif self.state == "IN_AIR_2":
            # second jump
            self.in_air_duration = now - self.in_air_start_time
            if self.in_air_duration > MAX_AIR_TIME:
                self.reset_state()
            if weight > AIR_THRESHOLD:
                self.state = "RESULT"
                curve_start = self.contact_start_time - 500
                # puste p i vel bo to chujstwo nie zadziala ianczwej bo to metoda engine
                curve = engine.generate_power_curve(curve_start, now, 70.0)
                for p in curve:
                    p['p'] = None
                    p['vel'] = None
                
                result = {
                    "timestamp": self.contact_end_time,
                    "contact_time": self.contact_duration,
                    "max_force": self.max_force,
                    "force_curve": curve,
                    "contact_start_time": self.contact_start_time,
                    "contact_end_time": self.contact_end_time,
                    "curve_start_time": curve_start
                }
        
        elif self.state == "RESULT":
            # jak zejdzie to ready
            if weight < AIR_THRESHOLD:
                self.reset_state()

        return {
            "state": self.state,
            "kg": display_kg,
            "display_kg": display_kg,
            "result": result,
            "jumper_mass_kg": 0.0,
            "velocity": 0.0
        }