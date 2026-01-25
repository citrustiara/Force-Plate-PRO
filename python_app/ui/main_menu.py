"""
Main menu UI layout.
"""
import dearpygui.dearpygui as dpg
from .callbacks import (
    show_single_jump, 
    show_jump_estimation, 
    show_contact_time,
    show_box_drop,
    show_box_drop_jump,
    show_push_up
)


def create_main_menu():
    """Create the main menu layout."""
    with dpg.group(tag="group_menu"):
        dpg.add_spacer(height=10)
        dpg.add_text("FORCE PLATE PRO", color=(0, 255, 255))
        dpg.add_spacer(height=50)
        
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=25)
            
            # --- COLUMN 1: JUMPS ---
            with dpg.group():
                dpg.add_text("JUMPS", color=(150, 150, 150))
                dpg.add_spacer(height=10)
                
                dpg.add_button(label="SINGLE JUMP", width=180, height=30, callback=show_single_jump)
                dpg.add_spacer(height=10)
                dpg.add_button(label="BOX DROP", width=180, height=30, callback=show_box_drop)
                dpg.add_spacer(height=10)
                dpg.add_button(label="BOX DROP JUMP", width=180, height=30, callback=show_box_drop_jump)
                dpg.add_spacer(height=10)
                dpg.add_button(label="CONTACT TIME", width=180, height=30, callback=show_contact_time)
                dpg.add_spacer(height=10)
                dpg.add_button(label="JUMP EST. (BETA)", width=180, height=30, callback=show_jump_estimation)
                dpg.add_spacer(height=10)
                dpg.add_button(label="CONTINUOUS JUMP", width=180, height=30, enabled=False)

            dpg.add_spacer(width=50)
            
            # --- COLUMN 2: EXERCISES ---
            with dpg.group():
                dpg.add_text("EXERCISES", color=(150, 150, 150))
                dpg.add_spacer(height=10)
                
                dpg.add_button(label="PUSH UP", width=180, height=30, callback=show_push_up)
                dpg.add_spacer(height=10)
                dpg.add_button(label="SQUAT", width=180, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="DEADLIFT", width=180, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="POWER CLEAN", width=180, height=30, enabled=False)
