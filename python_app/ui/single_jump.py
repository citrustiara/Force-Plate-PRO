"""
Single Jump mode UI layout.
"""
import dearpygui.dearpygui as dpg
from .callbacks import show_menu, connect_callback, reset_view_callback


def create_single_jump_header():
    """Create the Single Jump mode header and metrics."""
    with dpg.group(tag="group_header_single", show=False):
        with dpg.group(horizontal=True):
            dpg.add_button(label="< MENU", callback=show_menu)
            dpg.add_spacer(width=20)
            dpg.add_text("Single Jump Mode", color=(0, 255, 255))
            dpg.add_text("|")
            dpg.add_text("Disconnected", tag="txt_status_s", color=(255, 0, 0))
            dpg.add_spacer(width=20)
            dpg.add_button(label="Connect", tag="btn_connect_s", callback=connect_callback)
            dpg.add_button(label="Reset View", callback=reset_view_callback)

        dpg.add_separator()
        
        # METRICS SINGLE JUMP
        with dpg.group():
            # Row 1
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("HEIGHT (Flight)", color=(150, 150, 150))
                    dpg.add_text("-- cm", tag="met_s_height", color=(0, 255, 255))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("HEIGHT (Impulse)", color=(150, 150, 150))
                    dpg.add_text("-- cm", tag="met_s_height_imp", color=(0, 200, 200))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("FLIGHT TIME", color=(150, 150, 150))
                    dpg.add_text("-- ms", tag="met_s_flight", color=(100, 100, 255))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("MASS", color=(150, 150, 150))
                    dpg.add_text("-- kg", tag="met_s_mass", color=(255, 255, 0))

            dpg.add_spacer(height=5)
            
            # Row 2
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("PEAK POWER (Phys)", color=(150, 150, 150))
                    dpg.add_text("-- W", tag="met_s_peak_pwr", color=(255, 165, 0))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("PEAK POWER (Sayers)", color=(150, 150, 150))
                    dpg.add_text("-- W", tag="met_s_peak_pwr_form", color=(255, 140, 0))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("MEAN POWER (Phys)", color=(150, 150, 150))
                    dpg.add_text("-- W", tag="met_s_mean_pwr", color=(255, 200, 0))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("MEAN POWER (Harman)", color=(150, 150, 150))
                    dpg.add_text("-- W", tag="met_s_mean_pwr_form", color=(255, 180, 0))

            dpg.add_spacer(height=5)
            
            # Row 3
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("PEAK FORCE", color=(150, 150, 150))
                    dpg.add_text("-- kg", tag="met_s_peak_force", color=(255, 50, 50))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("VEL (Takeoff-Imp)", color=(150, 150, 150))
                    dpg.add_text("-- m/s", tag="met_s_vel", color=(100, 255, 100))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("VEL (Flight-Calc)", color=(150, 150, 150))
                    dpg.add_text("-- m/s", tag="met_s_vel_flight", color=(50, 200, 50))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("STATE", color=(150, 150, 150))
                    dpg.add_text("IDLE", tag="met_s_state")
