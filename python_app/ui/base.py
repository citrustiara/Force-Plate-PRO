from abc import ABC, abstractmethod
import dearpygui.dearpygui as dpg
import numpy as np

class ModeController(ABC):
    """
    Abstract Base Class for UI Mode Controllers.
    Responsibility: Handle UI updates, plot rendering, and events for a specific mode.
    """
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def setup_ui(self):
        """Create the specific UI elements for this mode (if not already created)."""
        pass

    @abstractmethod
    def on_enter(self):
        """Called when the mode is activated. Use this to show specific UI headers."""
        pass

    @abstractmethod
    def on_exit(self):
        """Called when the mode is deactivated. Use this to hide specific UI headers."""
        pass

    @abstractmethod
    def update(self, physics, dt):
        """
        Called every frame.
        :param physics: The PhysicsEngine instance.
        :param dt: Time delta since last frame.
        """
        pass

    def safe_fmt(self, val, unit, fmt=".1f"):
        """Helper to format values safely."""
        if val is None:
            return "--"
        try:
            fval = float(val)
            return f"{fval:{fmt}} {unit}"
        except (ValueError, TypeError):
            return "--"
