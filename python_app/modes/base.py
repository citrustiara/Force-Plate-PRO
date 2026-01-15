"""
Base physics mode class and shared constants.
"""
import numpy as np

# Constants - logic specific
AIR_THRESHOLD = 200000
MOVEMENT_THRESHOLD = 26000
STABILITY_TOLERANCE_KG = 1.9
MAX_PROPULSION_TIME_MS = 100000
MIN_AIR_TIME = 150
MAX_AIR_TIME = 1500
GRAVITY = 9.81


class PhysicsMode:
    """Base class for all physics modes."""
    
    def __init__(self, engine):
        self.engine = engine
        self.state = "IDLE"

    def process_sample(self, raw, timestamp, micros, now, dt):
        """
        Process a single sample.
        Returns a dict with state, metrics, etc.
        """
        raise NotImplementedError

    def reset_state(self):
        self.state = "IDLE"
