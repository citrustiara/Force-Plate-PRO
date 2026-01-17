"""
Force Plate PRO - Main Entry Point
Clean, minimal entry point that initializes the application.
"""
import dearpygui.dearpygui as dpg
import time
import numpy as np

from physics import PhysicsEngine, GRAVITY
from serial_handler import SerialHandler
from database import DatabaseHandler

from ui.themes import setup_themes
from ui.callbacks import (
    setup_callbacks, 
    on_new_jump, 
    get_selected_jump, 
    set_selected_jump,
    get_jump_history,
    is_autofit_enabled,
    safe_fmt
)
from ui.main_menu import create_main_menu
from ui.shared import create_shared_content


def main():
    # --- INITIALIZATION ---
    db = DatabaseHandler("jumps_data.db")
    
    # Load settings from DB
    saved_raw_per_kg = db.load_setting("raw_per_kg")
    
    config = {"gravity": 9.80665, "frequency": 1288}
    if saved_raw_per_kg:
        config["raw_per_kg"] = float(saved_raw_per_kg)
        print(f"Loaded raw_per_kg from DB: {config['raw_per_kg']}")
        
    physics = PhysicsEngine(config)
    physics.on_calib_callback = lambda val: db.save_setting("raw_per_kg", val)
    
    serial_handler = SerialHandler(physics)

    # Load existing history
    jump_history = db.load_history()

    # Setup callbacks with references
    setup_callbacks(physics, serial_handler, db, jump_history)
    serial_handler.on_jump_callback = on_new_jump

    # --- GUI SETUP ---
    dpg.create_context()
    setup_themes()

    # --- GUI LAYOUT ---
    with dpg.window(tag="Primary Window"):
        create_main_menu()
        create_shared_content()

    # --- MAIN LOOP ---
    dpg.create_viewport(title='ForcePlatePRO', width=1600, height=1000)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)

    last_update = time.time()

    while dpg.is_dearpygui_running():
        now = time.time()
        
        # Get current state
        selected_jump = get_selected_jump()
        jump_history = get_jump_history()
        auto_fit_y = is_autofit_enabled()
        
        # 1. Update Metrics Trigger
        is_est = dpg.get_item_configuration("group_header_estimation")["show"]
        is_single = dpg.get_item_configuration("group_header_single")["show"]
        is_contact = dpg.get_item_configuration("group_header_contact_time")["show"]
        
        # State / Mass updates
        if is_single:
            dpg.set_value("met_s_state", physics.state)
            dpg.set_value("met_s_mass", f"{physics.jumper_mass_kg:.1f} kg")
        if is_est:
            dpg.set_value("met_e_state", physics.state)
            dpg.set_value("met_e_mass", f"{physics.jumper_mass_kg:.1f} kg")
        if is_contact:
            dpg.set_value("met_c_state", physics.state)

        # 2. History List Update
        current_items = dpg.get_item_configuration("list_history")["items"]
        
        # Filter history by mode
        if is_single:
            filtered_history = [j for j in jump_history if j.get('formula_peak_power') is not None]
        elif is_contact:
            filtered_history = [j for j in jump_history if 'contact_time' in j]
        elif is_est:
            filtered_history = [j for j in jump_history if j.get('formula_peak_power') is None and 'contact_time' not in j]
        else:
            filtered_history = jump_history

        target_items = [
            f"#{j['_id']}: {j['height_flight']:.1f}cm ({j['flight_time']:.0f}ms)" 
            if (j.get('height_flight') or 0) > 0 
            else f"#{j['_id']}: CT {j.get('contact_time', 0):.0f}ms" if 'contact_time' in j
            else f"#{j['_id']}: Imp {j.get('height_impulse', 0):.1f}cm" 
            for j in filtered_history
        ]
        
        if len(current_items) != len(target_items) or (len(current_items) > 0 and current_items[0] != target_items[0]):
            dpg.configure_item("list_history", items=target_items)
            
        # 3. Update Metrics
        if selected_jump:
            if is_single:
                 dpg.set_value("met_s_height", safe_fmt(selected_jump.get('height_flight'), 'cm'))
                 dpg.set_value("met_s_height_imp", safe_fmt(selected_jump.get('height_impulse'), 'cm'))
                 dpg.set_value("met_s_flight", safe_fmt(selected_jump.get('flight_time'), 'ms', ".0f"))
                 dpg.set_value("met_s_peak_pwr", safe_fmt(selected_jump.get('peak_power'), 'W', ".0f"))
                 dpg.set_value("met_s_peak_pwr_form", safe_fmt(selected_jump.get('formula_peak_power'), 'W', ".0f"))
                 dpg.set_value("met_s_mean_pwr", safe_fmt(selected_jump.get('avg_power'), 'W', ".0f"))
                 dpg.set_value("met_s_mean_pwr_form", safe_fmt(selected_jump.get('formula_avg_power'), 'W', ".0f"))
                 dpg.set_value("met_s_peak_force", safe_fmt(selected_jump.get('max_force'), 'kg'))
                 dpg.set_value("met_s_vel", safe_fmt(selected_jump.get('velocity_takeoff'), 'm/s', ".2f"))
                 dpg.set_value("met_s_vel_flight", safe_fmt(selected_jump.get('velocity_flight'), 'm/s', ".2f"))
                 # Show mass from selected jump
                 mass = selected_jump.get('jumper_weight', 0)
                 dpg.set_value("met_s_mass", f"{mass:.1f} kg" if mass else "--")

            if is_est:
                 dpg.set_value("met_e_height_imp", safe_fmt(selected_jump.get('height_impulse'), 'cm'))
                 dpg.set_value("met_e_flight", safe_fmt(selected_jump.get('flight_time'), 'ms', ".0f"))
                 dpg.set_value("met_e_peak_pwr", safe_fmt(selected_jump.get('peak_power'), 'W', ".0f"))
                 dpg.set_value("met_e_mean_pwr", safe_fmt(selected_jump.get('avg_power'), 'W', ".0f"))
                 dpg.set_value("met_e_peak_force", safe_fmt(selected_jump.get('max_force'), 'kg'))
                 dpg.set_value("met_e_vel", safe_fmt(selected_jump.get('velocity_takeoff'), 'm/s', ".2f"))
                 
            if is_contact:
                 dpg.set_value("met_c_contact_time", safe_fmt(selected_jump.get('contact_time'), 'ms', ".0f"))
                 dpg.set_value("met_c_max_force", safe_fmt(selected_jump.get('max_force'), 'kg'))
                 
        else:
            # Clear metrics
            if is_single:
                 dpg.set_value("met_s_height", "--")
                 dpg.set_value("met_s_height_imp", "--")
                 dpg.set_value("met_s_flight", "--")
                 dpg.set_value("met_s_peak_pwr", "--")
                 dpg.set_value("met_s_peak_pwr_form", "--")
                 dpg.set_value("met_s_mean_pwr", "--")
                 dpg.set_value("met_s_mean_pwr_form", "--")
                 dpg.set_value("met_s_peak_force", "--")
                 dpg.set_value("met_s_vel", "--")
                 dpg.set_value("met_s_vel_flight", "--")
                 
            if is_est:
                 dpg.set_value("met_e_height_imp", "--")
                 dpg.set_value("met_e_flight", "--")
                 dpg.set_value("met_e_peak_pwr", "--")
                 dpg.set_value("met_e_mean_pwr", "--")
                 dpg.set_value("met_e_peak_force", "--")
                 dpg.set_value("met_e_vel", "--")
            
            if is_contact:
                dpg.set_value("met_c_contact_time", "--")
                dpg.set_value("met_c_max_force", "--")

        # 4. Live Plot with Averaging
        if not selected_jump:
            if now - last_update > 0.033:  # 30fps
                data = physics.get_buffer_view_time_window(physics.logic_time, 5000) 
                if len(data) > 0:
                    # Apply averaging to reduce noise
                    # At 1280Hz with 30fps updates: ~43 samples per frame
                    # Target ~150 points on graph for smooth display
                    downsample_factor = max(1, len(data) // 150)
                    
                    if downsample_factor > 1:
                        # Trim data to be evenly divisible
                        n_groups = len(data) // downsample_factor
                        trimmed_len = n_groups * downsample_factor
                        
                        # Reshape and average
                        xs_raw = data[:trimmed_len, 0].reshape(n_groups, downsample_factor).mean(axis=1)
                        ys = data[:trimmed_len, 1].reshape(n_groups, downsample_factor).mean(axis=1)
                        xs = (xs_raw - data[-1, 0]) / 1000.0 + 5
                    else:
                        xs = (data[:, 0] - data[-1, 0]) / 1000.0 + 5
                        ys = data[:, 1]
                    
                    xs = np.ascontiguousarray(xs)
                    ys = np.ascontiguousarray(ys)
                    
                    dpg.set_value("plot_line_series", [xs, ys])
                    
                    mass = physics.jumper_mass_kg if physics.jumper_mass_kg > 0 else 0
                    if mass > 0 and len(xs) > 0:
                        dpg.set_value("plot_line_series_mass", [[xs[0], xs[-1]], [mass, mass]])
                    else:
                        dpg.set_value("plot_line_series_mass", [[], []])

                    if is_contact:
                        dpg.set_value("plot_line_series_power", [[], []])
                        dpg.set_value("plot_line_series_vel", [[], []])
                    else:
                        dpg.set_value("plot_line_series_power", [[], []])
                        dpg.set_value("plot_line_series_vel", [[], []])
                    
                    dpg.set_value("plot_line_series_ct_start", [[], []])
                    dpg.set_value("plot_line_series_ct_end", [[], []])
                    
                    dpg.fit_axis_data("x_axis")
                    if auto_fit_y:
                        dpg.set_axis_limits("y_axis", -10, max(150, np.max(ys) + 20))
                    else:
                        dpg.set_axis_limits_auto("y_axis")
                last_update = now
        
        # 5. Selected Jump Display
        if selected_jump:
            p_val = dpg.get_value("plot_line_series_power")
            curr_p_x = p_val[0] if p_val and len(p_val) > 0 else []
            if len(curr_p_x) == 0: 
                curve = selected_jump.get('force_curve')
                if curve:
                    xs = [(p['t'] - curve[0]['t'])/1000.0 for p in curve]
                    ys = [p['v'] for p in curve] 
                    
                    # Check if power and velocity are present
                    has_power = all(p.get('p') is not None for p in curve)
                    has_vel = all(p.get('vel') is not None for p in curve)

                    ps = [p.get('p', 0) for p in curve] if has_power else []
                    vs = [p.get('vel', 0) for p in curve] if has_vel else []
                    
                    xs = np.ascontiguousarray(xs)
                    ys = np.ascontiguousarray(ys)
                    ps = np.ascontiguousarray(ps)
                    vs = np.ascontiguousarray(vs)
                    
                    dpg.set_value("plot_line_series", [xs, ys])
                    
                    mass = selected_jump.get('jumper_weight', 0)
                    if mass > 0 and len(xs) > 0:
                       dpg.set_value("plot_line_series_mass", [[xs[0], xs[-1]], [mass, mass]])
                    else:
                       dpg.set_value("plot_line_series_mass", [[], []])

                    dpg.set_value("plot_line_series_power", [xs, ps] if has_power else [[], []])
                    dpg.set_value("plot_line_series_vel", [xs, vs] if has_vel else [[], []])
                    
                    # --- Contact Time Markers ---
                    t_start = selected_jump.get('contact_start_time')
                    t_end = selected_jump.get('contact_end_time')
                    t_curv = selected_jump.get('curve_start_time')
                    if t_start and t_end and t_curv:
                        x_s = (t_start - t_curv) / 1000.0
                        x_e = (t_end - t_curv) / 1000.0
                        max_y = np.max(ys) if len(ys) > 0 else 200
                        dpg.set_value("plot_line_series_ct_start", [[x_s, x_s], [0, max_y]])
                        dpg.set_value("plot_line_series_ct_end", [[x_e, x_e], [0, max_y]])
                    else:
                        dpg.set_value("plot_line_series_ct_start", [[], []])
                        dpg.set_value("plot_line_series_ct_end", [[], []])
                    
                    dpg.fit_axis_data("x_axis")
                    dpg.fit_axis_data("y_axis")
                    dpg.fit_axis_data("y_axis_power")
                    dpg.fit_axis_data("y_axis_vel")

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
