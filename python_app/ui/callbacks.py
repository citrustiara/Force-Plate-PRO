"""
Callback functions for the Force Plate PRO application.
"""
import dearpygui.dearpygui as dpg
import numpy as np

# These will be set by setup_callbacks()
_physics = None
_serial_handler = None
_db = None
_jump_history = None
_selected_jump = None
_auto_fit_y = True


def setup_callbacks(physics, serial_handler, db, jump_history_ref):
    """Initialize callbacks with references to app components."""
    global _physics, _serial_handler, _db, _jump_history
    _physics = physics
    _serial_handler = serial_handler
    _db = db
    _jump_history = jump_history_ref


def get_state():
    """Get current application state."""
    global _selected_jump, _auto_fit_y, _jump_history
    return {
        'selected_jump': _selected_jump,
        'auto_fit_y': _auto_fit_y,
        'jump_history': _jump_history
    }


def set_selected_jump(jump):
    """Set the currently selected jump."""
    global _selected_jump
    _selected_jump = jump


def get_selected_jump():
    """Get the currently selected jump."""
    return _selected_jump


def get_jump_history():
    """Get reference to jump history list."""
    return _jump_history


def set_jump_history(history):
    """Update jump history reference."""
    global _jump_history
    _jump_history = history


def toggle_autofit(sender, app_data):
    """Toggle Y-axis auto-fit."""
    global _auto_fit_y
    _auto_fit_y = app_data


def is_autofit_enabled():
    """Check if autofit is enabled."""
    return _auto_fit_y


def connect_callback(sender, app_data):
    """Handle connect/disconnect button."""
    if not _serial_handler.connected:
        ports = _serial_handler.list_ports()
        target_port = ports[0] if ports else None
        for p in ports:
            if "COM9" in p:
                target_port = p
                break
        if target_port and _serial_handler.connect(target_port):
            dpg.configure_item("txt_status_s", default_value=f"Connected: {target_port}", color=(0, 255, 0))
            dpg.configure_item("txt_status_e", default_value=f"Connected: {target_port}", color=(0, 255, 0))
            dpg.configure_item("txt_status_c", default_value=f"Connected: {target_port}", color=(0, 255, 0))
            dpg.set_item_label("btn_connect_s", "Disconnect")
            dpg.set_item_label("btn_connect_e", "Disconnect")
            dpg.set_item_label("btn_connect_c", "Disconnect")
    else:
        _serial_handler.disconnect()
        dpg.configure_item("txt_status_s", default_value="Disconnected", color=(255, 0, 0))
        dpg.configure_item("txt_status_e", default_value="Disconnected", color=(255, 0, 0))
        dpg.configure_item("txt_status_c", default_value="Disconnected", color=(255, 0, 0))
        dpg.set_item_label("btn_connect_s", "Connect")
        dpg.set_item_label("btn_connect_e", "Connect")
        dpg.set_item_label("btn_connect_c", "Connect")


def tare_callback():
    """Start tare process."""
    _physics.start_tare()
    print("Tare started")


def calibrate_callback():
    """Start calibration process."""
    try:
        weight = dpg.get_value("input_calib_weight")
        _physics.start_calibrate(float(weight))
    except Exception as e:
        print(f"Calibration callback error: {e}")


def clear_history_callback():
    """Clear all jump history."""
    global _jump_history
    _db.clear()
    _jump_history.clear()
    dpg.configure_item("list_history", items=[])
    dpg.configure_item("plot_line_series", x=[], y=[])
    dpg.configure_item("plot_line_series_power", x=[], y=[])
    dpg.configure_item("plot_line_series_vel", x=[], y=[])
    dpg.configure_item("plot_line_series_mass", x=[], y=[])
    dpg.configure_item("plot_line_series_ct_start", x=[], y=[])
    dpg.configure_item("plot_line_series_ct_end", x=[], y=[])


def delete_selected_jump_callback():
    """Delete the currently selected jump."""
    global _jump_history, _selected_jump
    selection = dpg.get_value("list_history")
    if not selection:
        return
    
    idx_str = selection.split(':')[0].replace('#', '')
    try:
        idx = int(idx_str)
        _jump_history[:] = [j for j in _jump_history if j['_id'] != idx]
        
        # Update Listbox
        items = [
            f"#{j['_id']}: {j['height_flight']:.1f}cm ({j['flight_time']:.0f}ms)" 
            if (j.get('height_flight') or 0) > 0 
            else f"#{j['_id']}: CT {j.get('contact_time', 0):.0f}ms" if 'contact_time' in j
            else f"#{j['_id']}: Imp {j.get('height_impulse', 0):.1f}cm" 
            for j in _jump_history
        ]
        dpg.configure_item("list_history", items=items)
        
        if _selected_jump and _selected_jump['_id'] == idx:
            _selected_jump = None
            dpg.configure_item("plot_line_series", x=[], y=[])
            dpg.configure_item("plot_line_series_power", x=[], y=[])
            dpg.configure_item("plot_line_series_vel", x=[], y=[])
            
    except ValueError:
        pass


def history_click_callback(sender, app_data):
    """Handle click on history item."""
    global _selected_jump
    if not app_data:
        return
    
    try:
        idx_str = app_data.split(':')[0].replace('#', '')
        idx = int(idx_str)
        target = None
        for j in _jump_history:
            if j['_id'] == idx:
                target = j
                break
        
        if target:
            _selected_jump = target
            
            curve = target.get('force_curve')
            if curve and len(curve) > 0:
                xs = [(p['t'] - curve[0]['t'])/1000.0 for p in curve]
                ys = [p.get('v', 0) for p in curve] 
                
                # Check if power and velocity are present
                has_power = all(p.get('p') is not None for p in curve)
                has_vel = all(p.get('vel') is not None for p in curve)

                ps = [p.get('p', 0) for p in curve] if has_power else []
                vs = [p.get('vel', 0) for p in curve] if has_vel else []
                
                xs = np.ascontiguousarray(xs)
                ys = np.ascontiguousarray(ys)
                ps = np.ascontiguousarray(ps)
                vs = np.ascontiguousarray(vs)

                dpg.configure_item("plot_line_series", x=xs, y=ys)
                dpg.configure_item("plot_line_series_power", x=xs if has_power else [], y=ps if has_power else [])
                dpg.configure_item("plot_line_series_vel", x=xs if has_vel else [], y=vs if has_vel else [])
                
                # --- Mass line update ---
                mass = target.get('jumper_weight', 0)
                if mass > 0 and len(xs) > 0:
                    dpg.configure_item("plot_line_series_mass", x=[xs[0], xs[-1]], y=[mass, mass])
                else:
                    dpg.configure_item("plot_line_series_mass", x=[], y=[])

                # --- Contact Time Markers ---
                t_start = target.get('contact_start_time')
                t_end = target.get('contact_end_time')
                t_curve = target.get('curve_start_time')
                
                if t_start and t_end and t_curve:
                    x_s = (t_start - t_curve) / 1000.0
                    x_e = (t_end - t_curve) / 1000.0
                    max_y = np.max(ys) if len(ys) > 0 else 200
                    dpg.configure_item("plot_line_series_ct_start", x=[x_s, x_s], y=[0, max_y])
                    dpg.configure_item("plot_line_series_ct_end", x=[x_e, x_e], y=[0, max_y])
                else:
                    dpg.configure_item("plot_line_series_ct_start", x=[], y=[])
                    dpg.configure_item("plot_line_series_ct_end", x=[], y=[])
            else:
                # No curve, clear plots
                dpg.configure_item("plot_line_series", x=[], y=[])
                dpg.configure_item("plot_line_series_power", x=[], y=[])
                dpg.configure_item("plot_line_series_vel", x=[], y=[])
                dpg.configure_item("plot_line_series_mass", x=[], y=[])
                dpg.configure_item("plot_line_series_ct_start", x=[], y=[])
                dpg.configure_item("plot_line_series_ct_end", x=[], y=[])
            
            dpg.fit_axis_data("x_axis")
            dpg.fit_axis_data("y_axis")
            dpg.fit_axis_data("y_axis_power")
            dpg.fit_axis_data("y_axis_vel")
            
    except Exception as e:
        print(f"Error in history_click_callback: {e}")


def reset_view_callback():
    """Reset to live view."""
    global _selected_jump
    _selected_jump = None


def manual_mass_callback(sender, app_data):
    """Handle manual mass input."""
    if hasattr(_physics.active_mode, 'set_mass'):
        try:
            mass = float(app_data)
            _physics.active_mode.set_mass(mass)
        except ValueError:
            pass


def manual_start_vel_callback(sender, app_data):
    """Handle manual start velocity input."""
    if hasattr(_physics.active_mode, 'set_start_velocity'):
        try:
            vel = float(app_data)
            _physics.active_mode.set_start_velocity(vel)
        except ValueError:
            pass


# --- MENU NAVIGATION ---
def show_menu(sender=None, app_data=None):
    """Show main menu, hide workspace."""
    dpg.hide_item("group_workspace")
    dpg.show_item("group_menu")


def show_single_jump(sender=None, app_data=None):
    """Switch to Single Jump mode."""
    _physics.set_mode("Single Jump")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.show_item("group_header_single")
    dpg.hide_item("group_header_estimation")
    dpg.hide_item("group_header_contact_time")
    
    # Update legend
    dpg.show_item("plot_line_series")
    dpg.show_item("plot_line_series_mass")
    dpg.show_item("plot_line_series_power")
    dpg.show_item("plot_line_series_vel")
    dpg.hide_item("plot_line_series_ct_start")
    dpg.hide_item("plot_line_series_ct_end")


def show_jump_estimation(sender=None, app_data=None):
    """Switch to Jump Estimation mode."""
    _physics.set_mode("Jump Estimation")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.hide_item("group_header_single")
    dpg.show_item("group_header_estimation")
    dpg.hide_item("group_header_contact_time")
    
    # Update legend
    dpg.show_item("plot_line_series")
    dpg.show_item("plot_line_series_mass")
    dpg.show_item("plot_line_series_power")
    dpg.show_item("plot_line_series_vel")
    dpg.hide_item("plot_line_series_ct_start")
    dpg.hide_item("plot_line_series_ct_end")


def show_contact_time(sender=None, app_data=None):
    """Switch to Contact Time mode."""
    _physics.set_mode("Contact Time")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.hide_item("group_header_single")
    dpg.hide_item("group_header_estimation")
    dpg.show_item("group_header_contact_time")
    
    # Update legend
    dpg.show_item("plot_line_series")
    dpg.hide_item("plot_line_series_mass")
    dpg.hide_item("plot_line_series_power")
    dpg.hide_item("plot_line_series_vel")
    dpg.show_item("plot_line_series_ct_start")
    dpg.show_item("plot_line_series_ct_end")


def on_new_jump(jump_result):
    """Callback when a new jump is recorded."""
    global _selected_jump, _jump_history
    # Save to DB
    new_id = _db.save_jump(jump_result)
    jump_result['_id'] = new_id
    
    # Add to history
    _jump_history.insert(0, jump_result)  # Newest first
    _selected_jump = jump_result


def safe_fmt(val, unit, fmt=".1f"):
    """Format value with unit, handling None and non-numeric types."""
    if val is None:
        return "--"
    try:
        fval = float(val)
        return f"{fval:{fmt}} {unit}"
    except (ValueError, TypeError):
        # If it's already a string or can't be cast to float, return as is or with unit
        if isinstance(val, str) and val.strip() == "":
            return "--"
        return f"{val} {unit}"
