from serial_handler import SerialHandler


class FakePhysics:
    def __init__(self):
        self.samples = []
        self.frequency = None
        self.reset_count = 0
        self.zero_offsets = []

    def reset(self):
        self.reset_count += 1

    def set_frequency(self, hz):
        self.frequency = hz

    def set_zero(self, offset):
        self.zero_offsets.append(offset)

    def process_sample(self, raw, missing_samples=0):
        self.samples.append((raw, missing_samples))
        result = {"raw": raw} if raw == 42 else None
        return {"result": result}


def test_serial_thread_only_enqueues_and_main_thread_processes_messages():
    physics = FakePhysics()
    handler = SerialHandler(physics)
    results = []
    handler.on_jump_callback = results.append

    handler._process_line('{"w":10,"seq":0}')
    handler._process_line('{"w":42,"seq":3}')
    handler._process_line('{"event":"rate","hz":640}')
    handler._process_line('{"event":"zero","offset":123}')

    assert physics.samples == []

    handler.process_pending()

    assert physics.samples == [(10, 0), (42, 2)]
    assert handler.dropped_samples == 2
    assert physics.frequency == 640
    assert physics.zero_offsets == [0]
    assert results == [{"raw": 42}]
