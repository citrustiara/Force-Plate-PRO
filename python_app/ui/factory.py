from .single_jump import SingleJumpController
from .jump_estimation import JumpEstimationController
from .contact_time import ContactTimeController
from .continuous_jump import ContinuousJumpController

def get_controller(mode_name):
    if mode_name in ["Single Jump", "Box Drop", "Box Drop Jump", "Push Up", "Squat", "Deadlift", "Power Clean"]:
        # All these currently share the same UI logic
        return SingleJumpController(mode_name)
    elif mode_name == "Jump Estimation":
        return JumpEstimationController(mode_name)
    elif mode_name == "Contact Time":
        return ContactTimeController(mode_name)
    elif mode_name == "Continuous Jump":
        return ContinuousJumpController(mode_name)
    return None
