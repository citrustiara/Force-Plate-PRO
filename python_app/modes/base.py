"""
Base physics mode class and shared constants.
"""


# Constants - logic specific. Thresholds are in kilograms so calibration
# changes do not silently change state-machine behavior.
AIR_THRESHOLD_KG = 6.2
MOVEMENT_THRESHOLD_KG = 1.0
STABILITY_TOLERANCE_KG = 0.5
MAX_PROPULSION_TIME_MS = 100000
MIN_AIR_TIME = 100
MAX_AIR_TIME = 1500
GRAVITY = 9.80665

# Backward-compatible names for external imports.
AIR_THRESHOLD = AIR_THRESHOLD_KG
MOVEMENT_THRESHOLD = MOVEMENT_THRESHOLD_KG


class PhysicsMode:
    def __init__(self, engine):
        self.engine = engine
        self.state = "IDLE"

    def process_sample(self, raw, now, dt):
        raise NotImplementedError

    def reset_state(self):
        self.state = "IDLE"
