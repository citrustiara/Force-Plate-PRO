"""
Raw sample conditioning.

The current measurement path keeps filtering disabled by default so existing
mode behavior stays unchanged. This class is the future home for low-pass,
spike rejection, and baseline tracking without putting that logic in jump
state machines.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessedSample:
    raw: float
    raw_delta: float
    kg: float
    filtered_kg: float


class SignalConditioner:
    def __init__(self, config):
        self.config = config
        self.zero_offset = 0.0
        self.filtered_kg = 0.0
        self._filter_initialized = False

    def reset_filter(self):
        self.filtered_kg = 0.0
        self._filter_initialized = False

    def set_zero(self, offset):
        self.zero_offset = float(offset)
        self.reset_filter()

    def raw_delta(self, raw):
        return raw - self.zero_offset

    def raw_to_kg(self, raw):
        return self.raw_delta(raw) / self.config["raw_per_kg"]

    def process(self, raw):
        kg = self.raw_to_kg(raw)
        filtered_kg = self._low_pass(kg)
        return ProcessedSample(
            raw=raw,
            raw_delta=self.raw_delta(raw),
            kg=kg,
            filtered_kg=filtered_kg,
        )

    def _low_pass(self, kg):
        alpha = self.config.get("signal_lowpass_alpha")
        if alpha is None:
            return kg

        alpha = max(0.0, min(1.0, float(alpha)))
        if not self._filter_initialized:
            self.filtered_kg = kg
            self._filter_initialized = True
        else:
            self.filtered_kg = alpha * kg + (1.0 - alpha) * self.filtered_kg
        return self.filtered_kg
