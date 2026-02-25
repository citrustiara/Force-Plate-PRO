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
_current_plot_data = {
    "x": [],
    "y": [],
    "p": [],
    "v": []
}


def setup_callbacks(physics, serial_handler, db, jump_history_ref):
    """Initialize callbacks with references to app components."""
    global _physics, _serial_handler, _db, _jump_history
    _physics = physics
    _serial_handler = serial_handler
    _db = db
    _jump_history = jump_history_ref


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


def toggle_autofit(sender, app_data):
    """Toggle Y-axis auto-fit."""
    global _auto_fit_y
    _auto_fit_y = app_data


def is_autofit_enabled():
    """Check if autofit is enabled."""
    return _auto_fit_y


def reset_connection_callback(sender=None, app_data=None):
    """Disconnect then reconnect after 100ms."""
    import threading
    
    def do_reconnect():
        import time
        _serial_handler.disconnect()
        time.sleep(0.1)
        auto_connect()
    
    threading.Thread(target=do_reconnect, daemon=True).start()


def reset_platform_callback(sender=None, app_data=None):
    """Send reset command to ESP32."""
    if _serial_handler.connected:
        _serial_handler.send_reset()


def auto_connect():
    """Attempt to connect to the first available port (preferring COM9)."""
    if _serial_handler.connected:
        return True
    
    ports = _serial_handler.list_ports()
    target_port = ports[0] if ports else None
    for p in ports:
        if "COM9" in p:
            target_port = p
            break
    
    if target_port and _serial_handler.connect(target_port):
        update_connection_status(True, target_port)
        return True
    else:
        update_connection_status(False)
        return False


def update_connection_status(connected, port_name=""):
    """Update connection status indicator (colored circle)."""
    if connected:
        # Green circle
        dpg.configure_item("connection_circle_s", fill=(0, 200, 0, 255))
        dpg.configure_item("connection_circle_e", fill=(0, 200, 0, 255))
        dpg.configure_item("connection_circle_c", fill=(0, 200, 0, 255))
        dpg.configure_item("connection_circle_cj", fill=(0, 200, 0, 255))
    else:
        # Red circle
        dpg.configure_item("connection_circle_s", fill=(200, 0, 0, 255))
        dpg.configure_item("connection_circle_e", fill=(200, 0, 0, 255))
        dpg.configure_item("connection_circle_c", fill=(200, 0, 0, 255))
        dpg.configure_item("connection_circle_cj", fill=(200, 0, 0, 255))


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
    _current_plot_data["x"] = []
    _current_plot_data["y"] = []
    _current_plot_data["p"] = []
    _current_plot_data["v"] = []
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
                
                _current_plot_data["x"] = xs
                _current_plot_data["y"] = ys
                _current_plot_data["p"] = ps if has_power else []
                _current_plot_data["v"] = vs if has_vel else []
                
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
            dpg.set_axis_limits_auto("y_axis_power")
            dpg.fit_axis_data("y_axis_power")
            dpg.set_axis_limits_auto("y_axis_vel")
            dpg.fit_axis_data("y_axis_vel")
            
    except Exception as e:
        print(f"Error in history_click_callback: {e}")


def update_current_plot_data(x, y, p, v):
    """External helper to update the tracked plot data."""
    global _current_plot_data
    _current_plot_data["x"] = x
    _current_plot_data["y"] = y
    _current_plot_data["p"] = p
    _current_plot_data["v"] = v


def plot_mouse_move_callback(sender, app_data):
    """Handle mouse movement on the plot for sticky cursor."""
    global _current_plot_data
    
    # Check if sticky cursor is enabled
    is_sticky = dpg.get_value("check_sticky_cursor")
    
    if not is_sticky or not dpg.is_item_hovered("main_plot"):
        dpg.configure_item("plot_cursor_v", show=False)
        dpg.configure_item("plot_cursor_h", show=False)
        dpg.configure_item("plot_cursor_text", show=False)
        return

    mouse_pos = dpg.get_plot_mouse_pos()
    mx, my = mouse_pos
    
    xs = _current_plot_data["x"]
    if len(xs) == 0:
        dpg.configure_item("plot_cursor_v", show=False)
        dpg.configure_item("plot_cursor_h", show=False)
        dpg.configure_item("plot_cursor_text", show=False)
        return

    # Find nearest index
    idx = np.argmin(np.abs(xs - mx))
    
    # Snap to data point
    snapped_x = xs[idx]
    snapped_y = _current_plot_data["y"][idx]
    
    dpg.configure_item("plot_cursor_v", show=True)
    dpg.configure_item("plot_cursor_h", show=True)
    dpg.configure_item("plot_cursor_text", show=True)
    
    dpg.set_value("plot_cursor_v", snapped_x)
    dpg.set_value("plot_cursor_h", snapped_y)
    
    # Info text
    info = f"Time: {snapped_x:.3f}s\nForce: {snapped_y:.1f}kg"
    if len(_current_plot_data["p"]) > idx:
        info += f"\nPower: {_current_plot_data['p'][idx]:.0f}W"
    if len(_current_plot_data["v"]) > idx:
        info += f"\nVelocity: {_current_plot_data['v'][idx]:.2f}m/s"
        
    dpg.configure_item("plot_cursor_text", label=info)
    dpg.set_value("plot_cursor_text", [snapped_x, snapped_y])


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


def _show_single_jump_type(mode_name):
    """Shared logic for all Single Jump-type modes (Single Jump, Box Drop, Push Up, etc.)."""
    _physics.set_mode(mode_name)
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.show_item("group_header_single")
    dpg.hide_item("group_header_estimation")
    dpg.hide_item("group_header_contact_time")
    dpg.hide_item("group_header_continuous")
    
    dpg.show_item("plot_line_series")
    dpg.show_item("plot_line_series_mass")
    dpg.show_item("plot_line_series_power")
    dpg.show_item("plot_line_series_vel")
    dpg.hide_item("plot_line_series_ct_start")
    dpg.hide_item("plot_line_series_ct_end")
    dpg.show_item("plot_line_phase_unweight")
    dpg.show_item("plot_line_phase_braking")
    dpg.show_item("plot_line_phase_propulsion")


def show_single_jump(sender=None, app_data=None):
    _show_single_jump_type("Single Jump")


def show_box_drop(sender=None, app_data=None):
    _show_single_jump_type("Box Drop")


def show_box_drop_jump(sender=None, app_data=None):
    _show_single_jump_type("Box Drop Jump")


def show_push_up(sender=None, app_data=None):
    _show_single_jump_type("Push Up")


def show_jump_estimation(sender=None, app_data=None):
    """Switch to Jump Estimation mode."""
    _physics.set_mode("Jump Estimation")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.hide_item("group_header_single")
    dpg.show_item("group_header_estimation")
    dpg.hide_item("group_header_contact_time")
    dpg.hide_item("group_header_continuous")
    
    dpg.show_item("plot_line_series")
    dpg.show_item("plot_line_series_mass")
    dpg.show_item("plot_line_series_power")
    dpg.show_item("plot_line_series_vel")
    dpg.hide_item("plot_line_series_ct_start")
    dpg.hide_item("plot_line_series_ct_end")
    dpg.hide_item("plot_line_phase_unweight")
    dpg.hide_item("plot_line_phase_braking")
    dpg.hide_item("plot_line_phase_propulsion")


def show_contact_time(sender=None, app_data=None):
    """Switch to Contact Time mode."""
    _physics.set_mode("Contact Time")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.hide_item("group_header_single")
    dpg.hide_item("group_header_estimation")
    dpg.show_item("group_header_contact_time")
    dpg.hide_item("group_header_continuous")
    
    dpg.show_item("plot_line_series")
    dpg.hide_item("plot_line_series_mass")
    dpg.hide_item("plot_line_series_power")
    dpg.hide_item("plot_line_series_vel")
    dpg.show_item("plot_line_series_ct_start")
    dpg.show_item("plot_line_series_ct_end")
    dpg.hide_item("plot_line_phase_unweight")
    dpg.hide_item("plot_line_phase_braking")
    dpg.hide_item("plot_line_phase_propulsion")


def show_continuous_jump(sender=None, app_data=None):
    """Switch to Continuous Jump mode."""
    _physics.set_mode("Continuous Jump")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.hide_item("group_header_single")
    dpg.hide_item("group_header_estimation")
    dpg.hide_item("group_header_contact_time")
    dpg.show_item("group_header_continuous")
    
    dpg.show_item("plot_line_series")
    dpg.show_item("plot_line_series_mass")
    dpg.show_item("plot_line_series_power")
    dpg.show_item("plot_line_series_vel")
    dpg.hide_item("plot_line_series_ct_start")
    dpg.hide_item("plot_line_series_ct_end")
    dpg.hide_item("plot_line_phase_unweight")
    dpg.hide_item("plot_line_phase_braking")
    dpg.hide_item("plot_line_phase_propulsion")


def on_new_jump(jump_result):
    """Callback when a new jump is recorded."""
    global _selected_jump, _jump_history
    # Save to DB
    new_id = _db.save_jump(jump_result)
    jump_result['_id'] = new_id
    
    # Add to history
    _jump_history.insert(0, jump_result)  # Newest first
    _selected_jump = jump_result


# --- KEYBOARD CONTROLS ---

_menu_items = [
    ("SINGLE JUMP", show_single_jump, "menu_btn_0"),
    ("BOX DROP JUMP", show_box_drop_jump, "menu_btn_1"),
    ("CONTACT TIME", show_contact_time, "menu_btn_2"),
    ("JUMP EST. (BETA)", show_jump_estimation, "menu_btn_3"),
    ("CONTINUOUS JUMP", show_continuous_jump, "menu_btn_4"),
    ("PUSH UP", show_push_up, "menu_btn_5"),
    ("BOX DROP", show_box_drop, "menu_btn_6"),
]
_menu_selection_index = 0
_prev_key_state = {}  # Track previous frame state for edge detection
_menu_highlight_theme = None


def _key_just_pressed(key_code):
    """True only on the frame the key transitions from up to down."""
    currently_down = dpg.is_key_down(key_code)
    was_down = _prev_key_state.get(key_code, False)
    _prev_key_state[key_code] = currently_down
    return currently_down and not was_down


def _is_menu_visible():
    try:
        return dpg.is_item_shown("group_menu")
    except:
        return False


def _ensure_highlight_theme():
    """Create the highlight theme for selected menu buttons (once)."""
    global _menu_highlight_theme
    if _menu_highlight_theme is None:
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 180, 180, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 220, 220, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 0, 0, 255))
        _menu_highlight_theme = t


def _highlight_menu_selection():
    """Highlight the currently selected menu button, reset others."""
    _ensure_highlight_theme()
    for i, (_, _, tag) in enumerate(_menu_items):
        try:
            if i == _menu_selection_index:
                dpg.bind_item_theme(tag, _menu_highlight_theme)
            else:
                dpg.bind_item_theme(tag, 0)  # Reset to default
        except:
            pass


def handle_keyboard():
    """
    Called every frame. Edge-detected key handling:
    - Up/Down: navigate history or menu
    - Escape: deselect or go to menu
    - Shift: toggle sticky cursor
    - Enter: select mode in menu
    """
    global _selected_jump, _menu_selection_index

    in_menu = _is_menu_visible()

    # --- ESCAPE ---
    if _key_just_pressed(dpg.mvKey_Escape):
        if not in_menu:
            if _selected_jump is not None:
                _selected_jump = None
                dpg.set_value("list_history", "")
            else:
                show_menu()
                _highlight_menu_selection()
        return

    # --- SHIFT: Toggle sticky cursor ---
    if _key_just_pressed(dpg.mvKey_LShift) or _key_just_pressed(dpg.mvKey_RShift):
        if not in_menu:
            current = dpg.get_value("check_sticky_cursor")
            dpg.set_value("check_sticky_cursor", not current)
        return

    if in_menu:
        # --- MENU NAVIGATION ---
        if _key_just_pressed(dpg.mvKey_Down):
            _menu_selection_index = (_menu_selection_index + 1) % len(_menu_items)
            _highlight_menu_selection()
        elif _key_just_pressed(dpg.mvKey_Up):
            _menu_selection_index = (_menu_selection_index - 1) % len(_menu_items)
            _highlight_menu_selection()
        elif _key_just_pressed(dpg.mvKey_Return):
            _, callback, _ = _menu_items[_menu_selection_index]
            callback()
    else:
        # --- HISTORY NAVIGATION ---
        if _key_just_pressed(dpg.mvKey_Down):
            _navigate_history(1)
        elif _key_just_pressed(dpg.mvKey_Up):
            _navigate_history(-1)
        
        # --- ACTION SHORTCUTS (edge-detected) ---
        if _key_just_pressed(dpg.mvKey_Y):
            global _auto_fit_y
            _auto_fit_y = not _auto_fit_y
            try:
                dpg.set_value("check_autofit", _auto_fit_y)
            except:
                pass
        
        if _key_just_pressed(dpg.mvKey_T):
            tare_callback()
        
        if _key_just_pressed(dpg.mvKey_Z):
            reset_connection_callback()
        
        if _key_just_pressed(dpg.mvKey_X):
            reset_platform_callback()
        
        if _key_just_pressed(dpg.mvKey_R):
            reset_view_callback()
        
        # --- GRAPH PAN/ZOOM (continuous while held) ---
        _handle_graph_navigation()


def _navigate_history(direction):
    """Navigate through history. direction: 1=down (older), -1=up (newer)."""
    global _selected_jump

    try:
        items = dpg.get_item_configuration("list_history")["items"]
    except:
        return

    if not items:
        return

    # Find current selection index
    current_idx = -1
    if _selected_jump:
        current_id = _selected_jump.get('_id')
        for i, item in enumerate(items):
            try:
                item_id = int(item.split(':')[0].replace('#', ''))
                if item_id == current_id:
                    current_idx = i
                    break
            except ValueError:
                continue

    # Calculate new index
    if current_idx == -1:
        new_idx = 0
    else:
        new_idx = current_idx + direction

    # Bounds: wrap to deselect or to last
    if new_idx < -1:
        new_idx = len(items) - 1
    elif new_idx >= len(items):
        new_idx = -1

    if new_idx == -1:
        _selected_jump = None
        dpg.set_value("list_history", "")
        return

    selected_item = items[new_idx]
    dpg.set_value("list_history", selected_item)
    history_click_callback("list_history", selected_item)


def _handle_graph_navigation():
    """Handle WASD/Arrow panning and Q/E zooming on all plot axes."""
    PAN_X_FRACTION = 0.005  # Horizontal pan 0.5% per frame
    PAN_Y_FRACTION = 0.015  # Vertical pan 1.5% per frame
    ZOOM_FACTOR = 0.015     # Zoom 1.5% per frame
    
    ALL_Y_AXES = ["y_axis", "y_axis_power", "y_axis_vel"]
    
    try:
        x_min, x_max = dpg.get_axis_limits("x_axis")
    except:
        return
    
    # Gather current limits for all Y axes
    y_limits = {}
    for ax in ALL_Y_AXES:
        try:
            y_limits[ax] = list(dpg.get_axis_limits(ax))
        except:
            pass
    
    x_range = x_max - x_min
    moved_x = False
    moved_y = False
    
    # --- PAN ---
    if dpg.is_key_down(dpg.mvKey_A) or dpg.is_key_down(dpg.mvKey_Left):
        x_min -= x_range * PAN_X_FRACTION
        x_max -= x_range * PAN_X_FRACTION
        moved_x = True
    if dpg.is_key_down(dpg.mvKey_D) or dpg.is_key_down(dpg.mvKey_Right):
        x_min += x_range * PAN_X_FRACTION
        x_max += x_range * PAN_X_FRACTION
        moved_x = True
    if dpg.is_key_down(dpg.mvKey_W):
        for ax in y_limits:
            r = y_limits[ax][1] - y_limits[ax][0]
            y_limits[ax][0] += r * PAN_Y_FRACTION
            y_limits[ax][1] += r * PAN_Y_FRACTION
        moved_y = True
    if dpg.is_key_down(dpg.mvKey_S):
        for ax in y_limits:
            r = y_limits[ax][1] - y_limits[ax][0]
            y_limits[ax][0] -= r * PAN_Y_FRACTION
            y_limits[ax][1] -= r * PAN_Y_FRACTION
        moved_y = True
    
    # --- ZOOM ---
    if dpg.is_key_down(dpg.mvKey_Q):
        # Zoom out
        cx = (x_min + x_max) / 2
        x_range *= (1 + ZOOM_FACTOR)
        x_min = cx - x_range / 2
        x_max = cx + x_range / 2
        moved_x = True
        for ax in y_limits:
            r = y_limits[ax][1] - y_limits[ax][0]
            cy = (y_limits[ax][0] + y_limits[ax][1]) / 2
            r *= (1 + ZOOM_FACTOR)
            y_limits[ax] = [cy - r / 2, cy + r / 2]
        moved_y = True
    if dpg.is_key_down(dpg.mvKey_E):
        # Zoom in
        cx = (x_min + x_max) / 2
        x_range *= (1 - ZOOM_FACTOR)
        x_min = cx - x_range / 2
        x_max = cx + x_range / 2
        moved_x = True
        for ax in y_limits:
            r = y_limits[ax][1] - y_limits[ax][0]
            cy = (y_limits[ax][0] + y_limits[ax][1]) / 2
            r *= (1 - ZOOM_FACTOR)
            y_limits[ax] = [cy - r / 2, cy + r / 2]
        moved_y = True
    
    if moved_x:
        dpg.set_axis_limits("x_axis", x_min, x_max)
    if moved_y:
        for ax, lims in y_limits.items():
            dpg.set_axis_limits(ax, lims[0], lims[1])


