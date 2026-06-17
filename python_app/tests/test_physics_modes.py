import pytest

from physics import PhysicsEngine


def test_missing_samples_advance_logic_time():
    engine = PhysicsEngine({"frequency": 1000, "raw_per_kg": 1000})

    engine.process_sample(0, missing_samples=4)

    assert engine.logic_time == pytest.approx(5.0)


def test_single_jump_movement_threshold_uses_calibrated_kg():
    engine = PhysicsEngine({"frequency": 1000, "raw_per_kg": 1000})
    engine.set_zero(0)

    for _ in range(310):
        engine.process_sample(70000)

    assert engine.state == "READY"
    assert engine.jumper_mass_kg == pytest.approx(70.0)

    engine.process_sample(71100)

    assert engine.state == "PROPULSION"


def test_jump_estimation_rejects_invalid_manual_mass():
    engine = PhysicsEngine({"frequency": 1000, "raw_per_kg": 1000})
    engine.set_mode("Jump Estimation")

    with pytest.raises(ValueError):
        engine.active_mode.set_mass(0)

    with pytest.raises(ValueError):
        engine.active_mode.set_mass(500)
