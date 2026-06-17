"""
Circular sample buffer for processed force-plate data.

Rows are stored as [time_ms, kg]. The buffer owns ordering/window logic so
physics modes do not need to know how wraparound storage works.
"""
import numpy as np


class SampleBuffer:
    def __init__(self, size):
        self.size = size
        self.data = np.zeros((size, 2), dtype=np.float64)
        self.idx = 0
        self.full = False

    def clear(self):
        self.data.fill(0)
        self.idx = 0
        self.full = False

    def add(self, time_ms, kg):
        self.data[self.idx] = [time_ms, kg]
        self.idx = (self.idx + 1) % self.size
        if self.idx == 0:
            self.full = True

    def available_count(self):
        return self.size if self.full else self.idx

    def average_kg(self, count):
        if count <= 0:
            return 0.0

        total_available = self.available_count()
        if total_available == 0:
            return 0.0

        count = min(count, total_available)
        chunks = self._recent_chunks(count)
        total = sum(np.sum(chunk[:, 1]) for chunk in chunks)
        return total / count

    def ordered(self):
        if self.full:
            return np.concatenate((self.data[self.idx:self.size], self.data[0:self.idx]))
        return self.data[0:self.idx]

    def window(self, end_time, duration_ms):
        ordered = self.ordered()
        start_time = end_time - duration_ms
        return ordered[ordered[:, 0] >= start_time]

    def slice_time_range(self, start_time, end_time=None):
        ordered = self.ordered()
        mask = ordered[:, 0] >= start_time
        if end_time is not None:
            mask &= ordered[:, 0] <= end_time
        return ordered[mask]

    def recent_start_index(self, count):
        count = min(max(0, count), self.available_count())
        return (self.idx - count) % self.size

    def at(self, index):
        return self.data[index]

    def iter_from_index_to_current(self, start_index, max_steps=None):
        steps = 0
        i = start_index
        while i != self.idx:
            yield self.data[i]
            i = (i + 1) % self.size
            steps += 1
            if max_steps is not None and steps >= max_steps:
                break

    def _recent_chunks(self, count):
        end_idx = self.idx
        start_idx = (end_idx - count) % self.size

        if start_idx < end_idx:
            return [self.data[start_idx:end_idx]]
        return [self.data[start_idx:], self.data[:end_idx]]
