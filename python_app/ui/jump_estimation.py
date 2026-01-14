"""
Jump Estimation mode UI layout.
"""
import dearpygui.dearpygui as dpg
from .callbacks import show_menu, connect_callback, reset_view_callback, manual_mass_callback, manual_start_vel_callback


def create_jump_estimation_header():
    """Create the Jump Estimation mode header and metrics."""
    with dpg.group(tag="group_header_estimation", show=False):
        with dpg.group(horizontal=True):
            dpg.add_button(label="< MENU", callback=show_menu)
            dpg.add_spacer(width=20)
            dpg.add_text("Jump Estimation Mode", color=(0, 255, 255))
            dpg.add_text("|")
            dpg.add_text("Disconnected", tag="txt_status_e", color=(255, 0, 0))
            dpg.add_spacer(width=20)
            dpg.add_button(label="Connect", tag="btn_connect_e", callback=connect_callback)
            dpg.add_button(label="Reset View", callback=reset_view_callback)
            
            dpg.add_spacer(width=20)
            dpg.add_text("Mass:")
            dpg.add_input_float(tag="input_mass", width=150, default_value=75.0, callback=manual_mass_callback)
            dpg.add_spacer(width=10)
            dpg.add_text("Start V:")
            dpg.add_input_float(tag="input_start_vel", width=150, default_value=0.0, step=0.1, callback=manual_start_vel_callback)

        dpg.add_separator()
        
        # METRICS ESTIMATION (Reduced Set)
        with dpg.group():
            # Row 1
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("HEIGHT (Impulse)", color=(150, 150, 150))
                    dpg.add_text("-- cm", tag="met_e_height_imp", color=(0, 200, 200))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("FLIGHT TIME (Calc)", color=(150, 150, 150))
                    dpg.add_text("-- ms", tag="met_e_flight", color=(100, 100, 255))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("MASS", color=(150, 150, 150))
                    dpg.add_text("-- kg", tag="met_e_mass", color=(255, 255, 0))

            dpg.add_spacer(height=5)
            
            # Row 2
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("PEAK POWER", color=(150, 150, 150))
                    dpg.add_text("-- W", tag="met_e_peak_pwr", color=(255, 165, 0))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("MEAN POWER", color=(150, 150, 150))
                    dpg.add_text("-- W", tag="met_e_mean_pwr", color=(255, 200, 0))

            dpg.add_spacer(height=5)
            
            # Row 3
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("PEAK FORCE", color=(150, 150, 150))
                    dpg.add_text("-- kg", tag="met_e_peak_force", color=(255, 50, 50))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("VEL (Takeoff)", color=(150, 150, 150))
                    dpg.add_text("-- m/s", tag="met_e_vel", color=(100, 255, 100))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("STATE", color=(150, 150, 150))
                    dpg.add_text("IDLE", tag="met_e_state")
