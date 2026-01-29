import dearpygui.dearpygui as dpg
from .base import ModeController
from .callbacks import show_menu, connect_callback, reset_view_callback, manual_mass_callback, manual_start_vel_callback

class JumpEstimationController(ModeController):
    def setup_ui(self):
        with dpg.group(tag="group_header_estimation", show=False):
            with dpg.group(horizontal=True):
                dpg.add_button(label="< MENU", callback=show_menu)
                dpg.add_spacer(width=20)
                dpg.add_text("Jump Estimation Mode", color=(0, 255, 255))
                dpg.add_text("|")
                
                # Buttons first
                dpg.add_button(label="Connect", tag="btn_connect_e", callback=connect_callback, width=100)
                dpg.add_button(label="Reset View", callback=reset_view_callback, width=100)
                dpg.add_spacer(width=10)
                
                dpg.add_text("Disconnected", tag="txt_status_e", color=(255, 0, 0))
                
                dpg.add_spacer(width=50)
                # Controls specific to Estimation
                with dpg.group(horizontal=True):
                    dpg.add_text("Mass:")
                    dpg.add_input_float(tag="input_mass", width=100, default_value=75.0, callback=manual_mass_callback)
                    dpg.add_spacer(width=10)
                    dpg.add_text("Start V:")
                    dpg.add_input_float(tag="input_start_vel", width=100, default_value=0.0, step=0.1, callback=manual_start_vel_callback)

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

    def on_enter(self):
        dpg.show_item("group_header_estimation")
        dpg.show_item("plot_line_series")
        dpg.show_item("plot_line_series_mass")
        dpg.show_item("plot_line_series_power")
        dpg.show_item("plot_line_series_vel")
        dpg.hide_item("plot_line_series_ct_start")
        dpg.hide_item("plot_line_series_ct_end")

    def on_exit(self):
        dpg.hide_item("group_header_estimation")

    def update(self, physics, dt, selected_jump):
        dpg.set_value("met_e_state", physics.state)
        dpg.set_value("met_e_mass", f"{physics.jumper_mass_kg:.1f} kg")

        if selected_jump:
             dpg.set_value("met_e_height_imp", self.safe_fmt(selected_jump.get('height_impulse'), 'cm'))
             dpg.set_value("met_e_flight", self.safe_fmt(selected_jump.get('flight_time'), 'ms', ".0f"))
             dpg.set_value("met_e_peak_pwr", self.safe_fmt(selected_jump.get('peak_power'), 'W', ".0f"))
             dpg.set_value("met_e_mean_pwr", self.safe_fmt(selected_jump.get('avg_power'), 'W', ".0f"))
             dpg.set_value("met_e_peak_force", self.safe_fmt(selected_jump.get('max_force'), 'kg'))
             dpg.set_value("met_e_vel", self.safe_fmt(selected_jump.get('velocity_takeoff'), 'm/s', ".2f"))
        else:
             dpg.set_value("met_e_height_imp", "--")
             dpg.set_value("met_e_flight", "--")
             dpg.set_value("met_e_peak_pwr", "--")
             dpg.set_value("met_e_mean_pwr", "--")
             dpg.set_value("met_e_peak_force", "--")
             dpg.set_value("met_e_vel", "--")

def create_jump_estimation_header():
    """Backwards compatibility wrapper"""
    JumpEstimationController("Jump Estimation").setup_ui()
