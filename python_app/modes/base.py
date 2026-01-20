"""
Base physics mode class and shared constants.
"""


# Constants - logic specific
AIR_THRESHOLD = 90000
MOVEMENT_THRESHOLD = 26000
STABILITY_TOLERANCE_KG = 0.5
MAX_PROPULSION_TIME_MS = 100000
MIN_AIR_TIME = 150
MAX_AIR_TIME = 1500
GRAVITY = 9.80665


class PhysicsMode:
    def __init__(self, engine):
        self.engine = engine
        self.state = "IDLE"

    def process_sample(self, raw, timestamp, micros, now, dt):
        raise NotImplementedError

    def reset_state(self):
        self.state = "IDLE"
