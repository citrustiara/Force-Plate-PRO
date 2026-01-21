"""
Shared UI components - plot and history panel.
"""
import dearpygui.dearpygui as dpg
from .callbacks import (
    tare_callback, 
    toggle_autofit, 
    clear_history_callback, 
    delete_selected_jump_callback, 
    history_click_callback,
    calibrate_callback,
    plot_mouse_move_callback
)
from .single_jump import create_single_jump_header
from .jump_estimation import create_jump_estimation_header
from .contact_time import create_contact_time_header


def create_shared_content():
    """Create the shared workspace content (plot and history)."""
    with dpg.group(tag="group_workspace", show=False):
        
        # Mode-specific headers
        create_single_jump_header()
        create_jump_estimation_header()
        create_contact_time_header()
        
        dpg.add_separator()
        
        # --- SHARED CONTENT (Plot & History) ---
        with dpg.group(horizontal=True):
            
            # LEFT: PLOT
            with dpg.child_window(width=-250, height=700, border=True):
                dpg.add_text("Live Force Monitor / Analysis")
                with dpg.plot(tag="main_plot", height=-1, width=-1, callback=None):
                    dpg.add_plot_legend()
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis")
                    
                    with dpg.plot_axis(dpg.mvYAxis, label="Force (kg)", tag="y_axis"):
                        dpg.add_line_series([], [], label="Force", tag="plot_line_series")
                        dpg.bind_item_theme("plot_line_series", "theme_force_line")
                        dpg.add_line_series([], [], label="Jumper Mass", tag="plot_line_series_mass")
                        dpg.bind_item_theme("plot_line_series_mass", "theme_mass_line")
                        
                        # Contact Time Markers
                        dpg.add_line_series([], [], label="CT Start", tag="plot_line_series_ct_start")
                        dpg.add_line_series([], [], label="CT End", tag="plot_line_series_ct_end")
                        dpg.bind_item_theme("plot_line_series_ct_start", "theme_ct_marker")
                        dpg.bind_item_theme("plot_line_series_ct_end", "theme_ct_marker")

                    with dpg.plot_axis(dpg.mvYAxis, label="Power (W)", tag="y_axis_power"):
                        dpg.add_line_series([], [], label="Power", tag="plot_line_series_power", parent="y_axis_power")
                        dpg.bind_item_theme("plot_line_series_power", "theme_power_line")
                    
                    with dpg.plot_axis(dpg.mvYAxis, label="Velocity (m/s)", tag="y_axis_vel"):
                        dpg.add_line_series([], [], label="Velocity", tag="plot_line_series_vel", parent="y_axis_vel")
                        dpg.bind_item_theme("plot_line_series_vel", "theme_vel_line")

                    # --- STICKY CURSOR ELEMENTS (Parented to Plot) ---
                    dpg.add_drag_line(label="", tag="plot_cursor_v", color=[200, 200, 200, 255], vertical=True, show=False)
                    dpg.add_drag_line(label="", tag="plot_cursor_h", color=[200, 200, 200, 255], vertical=False, show=False)
                    dpg.add_plot_annotation(label="", tag="plot_cursor_text", offset=[-10, -10], show=False)

                # Item handler for mouse movement
                with dpg.item_handler_registry(tag="plot_handler_reg"):
                    dpg.add_item_hover_handler(callback=plot_mouse_move_callback)
                dpg.bind_item_handler_registry("main_plot", "plot_handler_reg")

            # RIGHT: CONTROLS & HISTORY
            with dpg.child_window(width=240, height=700):
                dpg.add_text("Controls", color=(0, 255, 0))
                with dpg.group(horizontal=True):
                    dpg.add_button(label="TARE", callback=tare_callback, width=60)
                    dpg.add_checkbox(label="AutoY", default_value=True, callback=toggle_autofit)
                dpg.add_checkbox(label="Sticky Cursor", default_value=True, tag="check_sticky_cursor")
                
                dpg.add_spacer(height=5)
                with dpg.group(horizontal=True):
                    dpg.add_input_float(tag="input_calib_weight", default_value=20.0, width=80, format="%.1f kg")
                    dpg.add_button(label="CALIBRATE", callback=calibrate_callback, width=80)
                
                dpg.add_spacer(height=10)
                dpg.add_separator()
                dpg.add_text("History")
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Clr All", callback=clear_history_callback, width=60)
                    dpg.add_button(label="Del", callback=delete_selected_jump_callback, width=60)
                
                dpg.add_listbox(tag="list_history", items=[], num_items=15, width=-1, callback=history_click_callback)
