"""
Signal processing utilities for raw force-plate samples.

This package is intentionally separate from exercise modes: modes decide what a
sample means for a jump, while this layer owns sample storage and raw-to-kg
conditioning.
"""

from .conditioning import ProcessedSample, SignalConditioner
from .sample_buffer import SampleBuffer

__all__ = ["ProcessedSample", "SignalConditioner", "SampleBuffer"]
