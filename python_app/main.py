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
    get_jump_history,
    is_autofit_enabled
)
from ui.main_menu import create_main_menu
from ui.shared import create_shared_content
from ui.factory import get_controller
from ui.plot_manager import PlotManager


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

    # --- CONTROLLERS & MANAGERS ---
    # Initial setup for specific modes
    # We delay setup_ui calls until after DPG context is ready, which is now.
    
    # Pre-initialize controllers to create their UI elements (hidden by default)
    # This ensures tags exist when we try to show/hide them.
    # Note: create_shared_content already called the legacy header creation functions
    # which created the groups. Our controllers expect these groups to exist.
    # If we move fully to controllers creating UI, we would call controller.setup_ui() here.
    # For now, we assume UI is created by create_shared_content -> create_X_header.
    
    plot_manager = PlotManager(physics.get_buffer_view_time_window)
    
    current_mode_name = physics.active_mode_name
    current_controller = get_controller(current_mode_name)
    
    # --- MAIN LOOP ---
    dpg.create_viewport(title='ForcePlatePRO', width=1600, height=1000)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)

    last_update = time.time()
    last_selected_jump_id = None
    
    # Ensure initial state matches
    if current_controller:
        current_controller.on_enter()

    while dpg.is_dearpygui_running():
        now = time.time()
        
        # 1. Mode Switching Check
        if physics.active_mode_name != current_mode_name:
            # excessive safety: ensure old controller cleans up
            if current_controller:
                current_controller.on_exit()
            
            current_mode_name = physics.active_mode_name
            current_controller = get_controller(current_mode_name)
            
            if current_controller:
                current_controller.on_enter()

        # Get Common State
        selected_jump = get_selected_jump()
        jump_history = get_jump_history()
        # auto_fit_y = is_autofit_enabled() # Managed by PlotManager now internally if passed or accessed via callback

        # 2. Controller Update (Metrics & State)
        if current_controller:
            # We pass 'dt' as approx frame time (0.016) or calculate real dt
            dt = now - last_update 
            current_controller.update(physics, dt, selected_jump)

        # 3. History List Update
        # Filter logic based on mode type (Simplification: Name check)
        # "Single Jump" and variants vs "Contact Time" vs "Jump Estimation"
        
        current_items = dpg.get_item_configuration("list_history")["items"]
        filtered_history = jump_history
        
        if current_mode_name in ["Single Jump", "Box Drop", "Box Drop Jump", "Push Up", "Squat", "Deadlift", "Power Clean"]:
             filtered_history = [j for j in jump_history if j.get('formula_peak_power') is not None]
        elif current_mode_name == "Contact Time":
             filtered_history = [j for j in jump_history if 'contact_time' in j]
        elif current_mode_name == "Jump Estimation":
             filtered_history = [j for j in jump_history if j.get('formula_peak_power') is None and 'contact_time' not in j]

        target_items = [
            f"#{j['_id']}: {j['height_flight']:.1f}cm ({j['flight_time']:.0f}ms)" 
            if (j.get('height_flight') or 0) > 0 
            else f"#{j['_id']}: CT {j.get('contact_time', 0):.0f}ms" if 'contact_time' in j
            else f"#{j['_id']}: Imp {j.get('height_impulse', 0):.1f}cm" 
            for j in filtered_history
        ]
        
        if len(current_items) != len(target_items) or (len(current_items) > 0 and current_items[0] != target_items[0]):
            dpg.configure_item("list_history", items=target_items)

        # 4. Plot Update
        if not selected_jump:
            # LIVE VIEW
            # Last selected ID reset so we refresh if we select again
            last_selected_jump_id = None
            
            # 30 FPS update cap inside plot_manager
            plot_manager.update_live_plot(physics, now)
            
        else:
            # SELECTED VIEW
            # Only update if the selection actually changed or we haven't drawn it yet
            sel_id = selected_jump.get('_id')
            if sel_id != last_selected_jump_id:
                plot_manager.update_selected_from_jump(selected_jump)
                last_selected_jump_id = sel_id

        last_update = now
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
