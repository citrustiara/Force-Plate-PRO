import numpy as np

from signal_processing import SampleBuffer, SignalConditioner


def test_sample_buffer_keeps_recent_samples_in_order_after_wrap():
    buffer = SampleBuffer(3)
    buffer.add(1, 10)
    buffer.add(2, 20)
    buffer.add(3, 30)
    buffer.add(4, 40)

    ordered = buffer.ordered()

    assert ordered.tolist() == [[2.0, 20.0], [3.0, 30.0], [4.0, 40.0]]
    assert buffer.average_kg(2) == 35.0
    np.testing.assert_array_equal(buffer.window(4, 1), np.array([[3.0, 30.0], [4.0, 40.0]]))


def test_signal_conditioner_zero_and_low_pass():
    conditioner = SignalConditioner({
        "raw_per_kg": 10.0,
        "signal_lowpass_alpha": 0.5,
    })
    conditioner.set_zero(100)

    first = conditioner.process(120)
    second = conditioner.process(140)

    assert first.kg == 2.0
    assert first.filtered_kg == 2.0
    assert second.kg == 4.0
    assert second.filtered_kg == 3.0
