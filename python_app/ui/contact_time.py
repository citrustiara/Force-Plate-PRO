import dearpygui.dearpygui as dpg
from .base import ModeController
from .callbacks import show_menu, connect_callback, reset_view_callback

class ContactTimeController(ModeController):
    def setup_ui(self):
        with dpg.group(tag="group_header_contact_time", show=False):
            
            with dpg.group(horizontal=True):
                dpg.add_button(label="< MENU", callback=show_menu)
                dpg.add_spacer(width=20)
                dpg.add_text("Contact Time Mode", color=(0, 255, 255))
                dpg.add_text("|")
                # Buttons first
                dpg.add_button(label="Connect", tag="btn_connect_c", callback=connect_callback, width=100)
                dpg.add_button(label="Reset View", callback=reset_view_callback, width=100)
                dpg.add_spacer(width=10)
                
                dpg.add_text("Disconnected", tag="txt_status_c", color=(255, 0, 0))

            dpg.add_separator()
            with dpg.group():
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("CONTACT TIME TEST", color=(255, 200, 0))
                        with dpg.group(horizontal=True):
                            dpg.add_text("State:")
                            dpg.add_text("READY", tag="met_c_state", color=(0, 255, 0))
                    
                    dpg.add_spacer(width=20)
                    
                    # Metric Boxes
                    with dpg.child_window(width=160, height=60, border=True):
                        dpg.add_text("Contact Time", color=(200, 200, 200))
                        dpg.add_text("-- ms", tag="met_c_contact_time", color=(255, 255, 255), bullet=False)
                    
                    dpg.add_spacer(width=10)
                    
                    with dpg.child_window(width=160, height=60, border=True):
                        dpg.add_text("Max Force", color=(200, 200, 200))
                        dpg.add_text("-- kg", tag="met_c_max_force", color=(255, 100, 100), bullet=False)

    def on_enter(self):
        dpg.show_item("group_header_contact_time")
        # Update legend
        dpg.show_item("plot_line_series")
        dpg.hide_item("plot_line_series_mass")
        dpg.hide_item("plot_line_series_power")
        dpg.hide_item("plot_line_series_vel")
        dpg.show_item("plot_line_series_ct_start")
        dpg.show_item("plot_line_series_ct_end")

    def on_exit(self):
        dpg.hide_item("group_header_contact_time")

    def update(self, physics, dt, selected_jump):
        dpg.set_value("met_c_state", physics.state)
        
        if selected_jump:
             dpg.set_value("met_c_contact_time", self.safe_fmt(selected_jump.get('contact_time'), 'ms', ".0f"))
             dpg.set_value("met_c_max_force", self.safe_fmt(selected_jump.get('max_force'), 'kg'))
        else:
             dpg.set_value("met_c_contact_time", "--")
             dpg.set_value("met_c_max_force", "--")

def create_contact_time_header():
    """Backwards compatibility wrapper"""
    ContactTimeController("Contact Time").setup_ui()
