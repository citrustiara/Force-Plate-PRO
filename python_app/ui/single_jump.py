import dearpygui.dearpygui as dpg
import numpy as np
from .base import ModeController
from .callbacks import show_menu, connect_callback, reset_view_callback

class SingleJumpController(ModeController):
    def setup_ui(self):
        with dpg.group(tag="group_header_single", show=False):
            # HEADER LINE
            with dpg.group(horizontal=True):
                dpg.add_button(label="< MENU", callback=show_menu)
                dpg.add_spacer(width=20)
                dpg.add_text("Single Jump Mode", color=(0, 255, 255))
                dpg.add_text("|")
                
                # Buttons first (fixed position)
                dpg.add_button(label="Connect", tag="btn_connect_s", callback=connect_callback, width=100)
                dpg.add_button(label="Reset View", callback=reset_view_callback, width=100)
                dpg.add_spacer(width=10)
                
                # Variable width text follows
                dpg.add_text("Disconnected", tag="txt_status_s", color=(255, 0, 0))
                
                dpg.add_spacer(width=150)
                dpg.add_text("State:", color=(150, 150, 150))
                dpg.add_text("IDLE", tag="met_s_state", color=(255, 255, 255))

            dpg.add_separator()
            
            # --- METRICS GROUP 1 (MAIN) ---
            with dpg.group():
                # Row 1
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("HEIGHT (Flight)", color=(150, 150, 150))
                        dpg.add_text("-- cm", tag="met_s_height", color=(0, 255, 255))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("FLIGHT TIME", color=(150, 150, 150))
                        dpg.add_text("-- ms", tag="met_s_flight", color=(100, 100, 255))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("PEAK POWER (Phys)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_peak_pwr", color=(255, 165, 0))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("MEAN POWER (Phys)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_mean_pwr", color=(255, 200, 0))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("MASS", color=(150, 150, 150))
                        dpg.add_text("-- kg", tag="met_s_mass", color=(255, 255, 0))

                dpg.add_spacer(height=5)
                
                # Row 2
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("PEAK FORCE (kg)", color=(150, 150, 150))
                        dpg.add_text("-- kg", tag="met_s_peak_force", color=(255, 50, 50))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("PEAK FORCE (N)", color=(150, 150, 150))
                        dpg.add_text("-- N", tag="met_s_peak_force_n", color=(255, 80, 80))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("PEAK POWER (W/kg)", color=(150, 150, 150))
                        dpg.add_text("-- W/kg", tag="met_s_peak_pwr_w_kg", color=(255, 165, 50))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("VEL (Flight-Calc)", color=(150, 150, 150))
                        dpg.add_text("-- m/s", tag="met_s_vel_flight", color=(50, 200, 50))
            
            dpg.add_separator()
            
            # --- PHASE TIMING METRICS ---
            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg.add_text("UNWEIGHTING", color=(255, 100, 100))
                    dpg.add_text("-- ms", tag="met_s_phase_unweight", color=(255, 100, 100))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("BRAKING", color=(100, 100, 255))
                    dpg.add_text("-- ms", tag="met_s_phase_braking", color=(100, 100, 255))
                dpg.add_spacer(width=20)
                with dpg.group():
                    dpg.add_text("PROPULSION", color=(100, 255, 100))
                    dpg.add_text("-- ms", tag="met_s_phase_propulsion", color=(100, 255, 100))
            
            dpg.add_separator()
            
            # --- METRICS GROUP 2 (DEBUG / DETAILS) ---
            with dpg.collapsing_header(label="Debug / Additional Metrics", default_open=True):
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("HEIGHT (Impulse)", color=(150, 150, 150))
                        dpg.add_text("-- cm", tag="met_s_height_imp", color=(0, 200, 200))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("VEL (Takeoff-Imp)", color=(150, 150, 150))
                        dpg.add_text("-- m/s", tag="met_s_vel", color=(100, 255, 100))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("PEAK POWER (Sayers)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_peak_pwr_form", color=(255, 140, 0))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("MEAN POWER (Harman)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_mean_pwr_form", color=(255, 180, 0))

    def on_enter(self):
        dpg.show_item("group_header_single")
        dpg.show_item("plot_line_series")
        dpg.show_item("plot_line_series_mass")
        dpg.show_item("plot_line_series_power")
        dpg.show_item("plot_line_series_vel")
        dpg.hide_item("plot_line_series_ct_start")
        dpg.hide_item("plot_line_series_ct_end")

    def on_exit(self):
        dpg.hide_item("group_header_single")

    def update(self, physics, dt, selected_jump):
        # 1. Update State & Mass (Live)
        state = physics.state
        color = (255, 255, 255) # Default White
        if state == "READY": color = (0, 255, 0)
        elif state == "WEIGHING": color = (255, 255, 0)
        elif state == "PROPULSION": color = (255, 165, 0)
        elif state == "LANDING": color = (255, 100, 100)
        elif state == "IN_AIR": color = (0, 255, 255)
            
        dpg.configure_item("met_s_state", default_value=state, color=color)
        dpg.set_value("met_s_mass", f"{physics.jumper_mass_kg:.1f} kg")

        # 2. Update Metrics if selected
        if selected_jump:
             mass = selected_jump.get('jumper_weight', 0)
             peak_force_kg = selected_jump.get('max_force', 0)
             peak_pwr = selected_jump.get('peak_power', 0)
             
             # Conversions
             g = physics.config["gravity"]
             peak_force_n = peak_force_kg * g if peak_force_kg else 0
             pwr_w_kg = peak_pwr / mass if mass > 0 else 0
             
             dpg.set_value("met_s_height", self.safe_fmt(selected_jump.get('height_flight'), 'cm'))
             dpg.set_value("met_s_height_imp", self.safe_fmt(selected_jump.get('height_impulse'), 'cm'))
             dpg.set_value("met_s_flight", self.safe_fmt(selected_jump.get('flight_time'), 'ms', ".0f"))
             dpg.set_value("met_s_peak_pwr", self.safe_fmt(peak_pwr, 'W', ".0f"))
             dpg.set_value("met_s_peak_pwr_form", self.safe_fmt(selected_jump.get('formula_peak_power'), 'W', ".0f"))
             dpg.set_value("met_s_mean_pwr", self.safe_fmt(selected_jump.get('avg_power'), 'W', ".0f"))
             dpg.set_value("met_s_mean_pwr_form", self.safe_fmt(selected_jump.get('formula_avg_power'), 'W', ".0f"))
             
             dpg.set_value("met_s_peak_force", self.safe_fmt(peak_force_kg, 'kg'))
             dpg.set_value("met_s_peak_force_n", f"{peak_force_n:.0f} N" if peak_force_n else "--")
             
             dpg.set_value("met_s_peak_pwr_w_kg", f"{pwr_w_kg:.1f} W/kg" if pwr_w_kg else "--")
             
             dpg.set_value("met_s_vel", self.safe_fmt(selected_jump.get('velocity_takeoff'), 'm/s', ".2f"))
             dpg.set_value("met_s_vel_flight", self.safe_fmt(selected_jump.get('velocity_flight'), 'm/s', ".2f"))
             
             dpg.set_value("met_s_mass", f"{mass:.1f} kg" if mass else "--")
             
             # Phase times
             phase_times = selected_jump.get('phase_times')
             if phase_times:
                 t_start = phase_times.get('unweighting_start', 0)
                 t_min_vel = phase_times.get('min_velocity_time', 0)
                 t_zero = phase_times.get('zero_crossing_time', 0)
                 t_takeoff = phase_times.get('takeoff_time', 0)
                 
                 # Calculate phase durations
                 unweight_time = (t_min_vel - t_start) if (t_start > 0 and t_min_vel > 0) else 0
                 braking_time = (t_zero - t_min_vel) if (t_min_vel > 0 and t_zero > 0) else 0
                 propulsion_time = (t_takeoff - t_zero) if (t_zero > 0 and t_takeoff > 0) else 0
                 
                 dpg.set_value("met_s_phase_unweight", f"{unweight_time:.0f} ms" if unweight_time > 0 else "--")
                 dpg.set_value("met_s_phase_braking", f"{braking_time:.0f} ms" if braking_time > 0 else "--")
                 dpg.set_value("met_s_phase_propulsion", f"{propulsion_time:.0f} ms" if propulsion_time > 0 else "--")
             else:
                 dpg.set_value("met_s_phase_unweight", "--")
                 dpg.set_value("met_s_phase_braking", "--")
                 dpg.set_value("met_s_phase_propulsion", "--")
        else:
             # Clear metrics
             dpg.set_value("met_s_height", "--")
             dpg.set_value("met_s_height_imp", "--")
             dpg.set_value("met_s_flight", "--")
             dpg.set_value("met_s_peak_pwr", "--")
             dpg.set_value("met_s_peak_pwr_form", "--")
             dpg.set_value("met_s_mean_pwr", "--")
             dpg.set_value("met_s_mean_pwr_form", "--")
             dpg.set_value("met_s_peak_force", "--")
             dpg.set_value("met_s_peak_force_n", "--")
             dpg.set_value("met_s_peak_pwr_w_kg", "--")
             dpg.set_value("met_s_vel", "--")
             dpg.set_value("met_s_vel_flight", "--")
             dpg.set_value("met_s_phase_unweight", "--")
             dpg.set_value("met_s_phase_braking", "--")
             dpg.set_value("met_s_phase_propulsion", "--")

def create_single_jump_header():
    """Backwards compatibility wrapper to create UI"""
    SingleJumpController("Single Jump").setup_ui()
