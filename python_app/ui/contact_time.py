"""
Contact Time UI Header.
"""
import dearpygui.dearpygui as dpg
from .callbacks import show_menu, connect_callback, reset_view_callback

def create_contact_time_header():
    """Create the UI header for Contact Time mode."""
    with dpg.group(tag="group_header_contact_time", show=False):
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="< MENU", callback=show_menu)
            dpg.add_spacer(width=20)
            dpg.add_text("Contact Time Mode", color=(0, 255, 255))
            dpg.add_text("|")
            dpg.add_text("Disconnected", tag="txt_status_c", color=(255, 0, 0))
            dpg.add_spacer(width=20)
            dpg.add_button(label="Connect", tag="btn_connect_c", callback=connect_callback)
            dpg.add_button(label="Reset View", callback=reset_view_callback)

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
