"""
Main menu UI layout.
"""
import dearpygui.dearpygui as dpg
from .callbacks import show_single_jump, show_jump_estimation


def create_main_menu():
    """Create the main menu layout."""
    with dpg.group(tag="group_menu"):
        dpg.add_spacer(height=10)
        dpg.add_text("FORCE PLATE PRO", color=(0, 255, 255))
        dpg.add_spacer(height=50)
        
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=25)
            with dpg.group():
                dpg.add_button(label="SINGLE JUMP", width=150, height=30, callback=show_single_jump)
                dpg.add_spacer(height=10)
                dpg.add_button(label="CONTINUOUS JUMP", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="CONTACT TIME", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="JUMP EST. (BETA)", width=150, height=30, callback=show_jump_estimation)
                dpg.add_spacer(height=50)
                dpg.add_button(label="DEADLIFT", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="POWER CLEAN", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="SQUAT", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="SQUAT", width=150, height=30, enabled=False)
