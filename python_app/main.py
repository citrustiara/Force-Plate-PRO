import dearpygui.dearpygui as dpg
import time
import numpy as np
from physics import PhysicsEngine, GRAVITY
from serial_handler import SerialHandler
from database import DatabaseHandler

# --- INITIALIZATION ---
config = {"gravity": 9.81, "frequency": 1200}
physics = PhysicsEngine(config)
serial_handler = SerialHandler(physics)
db = DatabaseHandler("jumps_data.db")

# Load existing history
jump_history = db.load_history()

# --- VARIABLES ---
selected_jump = None
plot_data_x = []
plot_data_y = []
auto_fit_y = True

# Callback for new jumps
def on_new_jump(jump_result):
    global selected_jump, jump_history
    # Save to DB
    new_id = db.save_jump(jump_result)
    jump_result['_id'] = new_id
    
    # Add to history
    jump_history.insert(0, jump_result) # Newest first
    selected_jump = jump_result
    
serial_handler.on_jump_callback = on_new_jump

dpg.create_context()

# --- THEME ---
with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (20, 20, 20), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_Header, (40, 40, 40), category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5, category=dpg.mvThemeCat_Core)

dpg.bind_theme(global_theme)

# Mass Line Theme
with dpg.theme(tag="theme_mass_line"):
    with dpg.theme_component(dpg.mvLineSeries):
        dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 255, 0), category=dpg.mvThemeCat_Core)

def toggle_autofit(sender, app_data):
    global auto_fit_y
    auto_fit_y = app_data

# --- CALLBACKS ---
def connect_callback(sender, app_data):
    if not serial_handler.connected:
        ports = serial_handler.list_ports()
        target_port = ports[0] if ports else None
        for p in ports:
            if "COM9" in p:
                target_port = p
                break
        if target_port and serial_handler.connect(target_port):
            dpg.configure_item("txt_status_s", default_value=f"Connected: {target_port}", color=(0, 255, 0))
            dpg.configure_item("txt_status_e", default_value=f"Connected: {target_port}", color=(0, 255, 0))
            dpg.set_item_label("btn_connect_s", "Disconnect")
            dpg.set_item_label("btn_connect_e", "Disconnect")
    else:
        serial_handler.disconnect()
        dpg.configure_item("txt_status_s", default_value="Disconnected", color=(255, 0, 0))
        dpg.configure_item("txt_status_e", default_value="Disconnected", color=(255, 0, 0))
        dpg.set_item_label("btn_connect_s", "Connect")
        dpg.set_item_label("btn_connect_e", "Connect")

def tare_callback():
    physics.start_tare()
    print("Tare started")

def clear_history_callback():
    global jump_history
    db.clear()
    jump_history = []
    dpg.configure_item("list_history", items=[])
    dpg.configure_item("plot_line_series", x=[], y=[])
    dpg.configure_item("plot_line_series_power", x=[], y=[])
    dpg.configure_item("plot_line_series_vel", x=[], y=[])
    dpg.configure_item("plot_line_series_mass", x=[], y=[])
    
def delete_selected_jump_callback():
    global jump_history, selected_jump
    selection = dpg.get_value("list_history")
    if not selection: return
    
    idx_str = selection.split(':')[0].replace('#', '')
    try:
        idx = int(idx_str)
        jump_history = [j for j in jump_history if j['_id'] != idx]
        
        # Update Listbox
        items = [f"#{j['_id']}: {j['height_flight']:.1f}cm ({j['flight_time']:.0f}ms)" if j.get('height_flight', 0) > 0 else f"#{j['_id']}: Imp {j['height_impulse']:.1f}cm" for j in jump_history]
        dpg.configure_item("list_history", items=items)
        
        if selected_jump and selected_jump['_id'] == idx:
            selected_jump = None
            dpg.configure_item("plot_line_series", x=[], y=[])
            dpg.configure_item("plot_line_series_power", x=[], y=[])
            dpg.configure_item("plot_line_series_vel", x=[], y=[])
            
    except ValueError:
        pass

def history_click_callback(sender, app_data):
    global selected_jump
    if not app_data: return
    
    idx_str = app_data.split(':')[0].replace('#', '')
    try:
        idx = int(idx_str)
        target = None
        for j in jump_history:
            if j['_id'] == idx:
                target = j
                break
        
        if target:
            selected_jump = target
            curve = target['force_curve']
            xs = [(p['t'] - curve[0]['t'])/1000.0 for p in curve]
            ys = [p['v'] for p in curve] 
            ps = [p['p'] for p in curve] 
            vs = [p.get('vel', 0) for p in curve] 
            
            xs = np.ascontiguousarray(xs)
            ys = np.ascontiguousarray(ys)
            ps = np.ascontiguousarray(ps)
            vs = np.ascontiguousarray(vs)

            dpg.configure_item("plot_line_series", x=xs, y=ys)
            dpg.configure_item("plot_line_series_power", x=xs, y=ps)
            dpg.configure_item("plot_line_series_vel", x=xs, y=vs)
            
            dpg.fit_axis_data("x_axis")
            dpg.fit_axis_data("y_axis")
            dpg.fit_axis_data("y_axis_power")
            dpg.fit_axis_data("y_axis_vel")
            
    except Exception as e:
        print(e)
        
def reset_view_callback():
    global selected_jump
    selected_jump = None

def manual_mass_callback(sender, app_data):
    if hasattr(physics.active_mode, 'set_mass'):
        try:
            mass = float(app_data)
            physics.active_mode.set_mass(mass)
        except ValueError: pass

def manual_start_vel_callback(sender, app_data):
    if hasattr(physics.active_mode, 'set_start_velocity'):
        try:
            vel = float(app_data)
            physics.active_mode.set_start_velocity(vel)
        except ValueError: pass

# --- MENU CALLBACKS ---
def show_menu(sender, app_data):
    dpg.hide_item("group_workspace")
    dpg.show_item("group_menu")

def show_single_jump(sender, app_data):
    physics.set_mode("Single Jump")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.show_item("group_header_single")
    dpg.hide_item("group_header_estimation")

def show_jump_estimation(sender, app_data):
    physics.set_mode("Jump Estimation")
    dpg.hide_item("group_menu")
    dpg.show_item("group_workspace")
    dpg.hide_item("group_header_single")
    dpg.show_item("group_header_estimation")

# --- GUI LAYOUT ---
with dpg.window(tag="Primary Window"):
    
    # === MAIN MENU ===
    with dpg.group(tag="group_menu"):
        dpg.add_spacer(height=10)
        dpg.add_text("FORCE PLATE PRO", color=(0, 255, 255))
        dpg.add_spacer(height=50)
        
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=25)
            with dpg.group():
                dpg.add_button(label="SINGLE JUMP", width=150, height=30, callback=show_single_jump)
                dpg.add_spacer(height=10)
                dpg.add_button(label="CONTINUOUS JUMP", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="CONTACT TIME", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="JUMP ESTIMATION", width=150, height=30, callback=show_jump_estimation)
                dpg.add_spacer(height=50)
                dpg.add_button(label="DEADLIFT", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="POWER CLEAN", width=150, height=30, enabled=False)
                dpg.add_spacer(height=10)
                dpg.add_button(label="SQUAT", width=150, height=30, enabled=False)

    # === WORKSPACE (Shared Container) ===
    with dpg.group(tag="group_workspace", show=False):
        
        # --- HEADER: SINGLE JUMP ---
        with dpg.group(tag="group_header_single", show=False):
            with dpg.group(horizontal=True):
                dpg.add_button(label="< MENU", callback=show_menu)
                dpg.add_spacer(width=20)
                dpg.add_text("Single Jump Mode", color=(0, 255, 255))
                dpg.add_text("|")
                dpg.add_text("Disconnected", tag="txt_status_s", color=(255, 0, 0))
                dpg.add_spacer(width=20)
                dpg.add_button(label="Connect", tag="btn_connect_s", callback=connect_callback)
                dpg.add_button(label="Reset View", callback=reset_view_callback)

            dpg.add_separator()
            # METRICS SINGLE JUMP
            with dpg.group():
                # Row 1
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("HEIGHT (Flight)", color=(150, 150, 150))
                        dpg.add_text("-- cm", tag="met_s_height", color=(0, 255, 255))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("HEIGHT (Impulse)", color=(150, 150, 150))
                        dpg.add_text("-- cm", tag="met_s_height_imp", color=(0, 200, 200))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("FLIGHT TIME", color=(150, 150, 150))
                        dpg.add_text("-- ms", tag="met_s_flight", color=(100, 100, 255))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("MASS", color=(150, 150, 150))
                        dpg.add_text("-- kg", tag="met_s_mass", color=(255, 255, 0))

                dpg.add_spacer(height=5)
                # Row 2
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("PEAK POWER (Phys)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_peak_pwr", color=(255, 165, 0))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("PEAK POWER (Sayers)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_peak_pwr_form", color=(255, 140, 0))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("MEAN POWER (Phys)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_mean_pwr", color=(255, 200, 0))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("MEAN POWER (Harman)", color=(150, 150, 150))
                        dpg.add_text("-- W", tag="met_s_mean_pwr_form", color=(255, 180, 0))

                dpg.add_spacer(height=5)
                # Row 3
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_text("PEAK FORCE", color=(150, 150, 150))
                        dpg.add_text("-- kg", tag="met_s_peak_force", color=(255, 50, 50))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("VEL (Takeoff-Imp)", color=(150, 150, 150))
                        dpg.add_text("-- m/s", tag="met_s_vel", color=(100, 255, 100))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("VEL (Flight-Calc)", color=(150, 150, 150))
                        dpg.add_text("-- m/s", tag="met_s_vel_flight", color=(50, 200, 50))
                    dpg.add_spacer(width=20)
                    with dpg.group():
                        dpg.add_text("STATE", color=(150, 150, 150))
                        dpg.add_text("IDLE", tag="met_s_state")

        # --- HEADER: JUMP ESTIMATION ---
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

        dpg.add_separator()
        
        # --- SHARED CONTENT (Plot & History) ---
        with dpg.group(horizontal=True):
            
            # LEFT: PLOT
            with dpg.child_window(width=-250, height=600, border=True):
                dpg.add_text("Live Force Monitor / Analysis")
                with dpg.plot(tag="main_plot", height=-1, width=-1):
                    dpg.add_plot_legend()
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis")
                    
                    with dpg.plot_axis(dpg.mvYAxis, label="Force (kg)", tag="y_axis"):
                        dpg.add_line_series([], [], label="Force", tag="plot_line_series")
                        dpg.add_line_series([], [], label="Jumper Mass", tag="plot_line_series_mass")
                        dpg.bind_item_theme("plot_line_series_mass", "theme_mass_line")
                    
                    with dpg.plot_axis(dpg.mvYAxis, label="Power (W)", tag="y_axis_power"):
                        dpg.add_line_series([], [], label="Power", tag="plot_line_series_power", parent="y_axis_power")
                    
                    with dpg.plot_axis(dpg.mvYAxis, label="Velocity (m/s)", tag="y_axis_vel"):
                        dpg.add_line_series([], [], label="Velocity", tag="plot_line_series_vel", parent="y_axis_vel")

            # RIGHT: CONTROLS & HISTORY
            with dpg.child_window(width=240, height=600):
                dpg.add_text("Controls", color=(0, 255, 0))
                with dpg.group(horizontal=True):
                    dpg.add_button(label="TARE", callback=tare_callback, width=60)
                    dpg.add_checkbox(label="AutoY", default_value=True, callback=toggle_autofit)
                
                dpg.add_spacer(height=10)
                dpg.add_separator()
                dpg.add_text("History")
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Clr All", callback=clear_history_callback, width=60)
                    dpg.add_button(label="Del", callback=delete_selected_jump_callback, width=60)
                
                dpg.add_listbox(tag="list_history", items=[], num_items=15, width=-1, callback=history_click_callback)


# --- MAIN LOOP ---
dpg.create_viewport(title='Force Plate PRO', width=1400, height=850)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary Window", True)

live_x = np.linspace(0, 5, 500)
live_y = np.zeros(500)
last_update = time.time()

def safe_fmt(val, unit, fmt=".1f"):
    if val is None: return "--"
    return f"{val:{fmt}} {unit}"

while dpg.is_dearpygui_running():
    now = time.time()
    
    # 1. Update Metrics Trigger
    is_est = (dpg.get_item_configuration("group_header_estimation")["show"])
    is_single = (dpg.get_item_configuration("group_header_single")["show"])
    
    # State / Mass updates
    if is_single:
        dpg.set_value("met_s_state", physics.state)
        dpg.set_value("met_s_mass", f"{physics.jumper_mass_kg:.1f} kg")
    if is_est:
        dpg.set_value("met_e_state", physics.state)
        dpg.set_value("met_e_mass", f"{physics.jumper_mass_kg:.1f} kg")

    # 2. History List Update
    current_items = dpg.get_item_configuration("list_history")["items"]
    target_items = [f"#{j['_id']}: {j['height_flight']:.1f}cm ({j['flight_time']:.0f}ms)" if j.get('height_flight', 0) > 0 else f"#{j['_id']}: Imp {j['height_impulse']:.1f}cm" for j in jump_history]
    
    if len(current_items) != len(target_items) or (len(current_items) > 0 and current_items[0] != target_items[0]):
        dpg.configure_item("list_history", items=target_items)
        
    # 3. Update Metrics Valid
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

        if is_est:
             dpg.set_value("met_e_height_imp", safe_fmt(selected_jump.get('height_impulse'), 'cm'))
             dpg.set_value("met_e_flight", safe_fmt(selected_jump.get('flight_time'), 'ms', ".0f"))
             dpg.set_value("met_e_peak_pwr", safe_fmt(selected_jump.get('peak_power'), 'W', ".0f"))
             dpg.set_value("met_e_mean_pwr", safe_fmt(selected_jump.get('avg_power'), 'W', ".0f"))
             dpg.set_value("met_e_peak_force", safe_fmt(selected_jump.get('max_force'), 'kg'))
             dpg.set_value("met_e_vel", safe_fmt(selected_jump.get('velocity_takeoff'), 'm/s', ".2f"))
             
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

    # 4. Live Plot
    if not selected_jump:
        if now - last_update > 0.033: # 30fps
            data = physics.get_buffer_view_time_window(physics.logic_time, 5000) 
            if len(data) > 0:
                xs = (data[:, 0] - data[-1, 0]) / 1000.0 
                ys = data[:, 1]
                if len(xs) > 2000:
                    xs, ys = xs[::5], ys[::5]
                
                xs = np.ascontiguousarray(xs)
                ys = np.ascontiguousarray(ys)
                
                dpg.set_value("plot_line_series", [xs, ys])
                
                mass = physics.jumper_mass_kg if physics.jumper_mass_kg > 0 else 0
                if mass > 0 and len(xs) > 0:
                    dpg.set_value("plot_line_series_mass", [[xs[0], xs[-1]], [mass, mass]])
                else:
                    dpg.set_value("plot_line_series_mass", [[], []])

                dpg.set_value("plot_line_series_power", [[], []])
                dpg.set_value("plot_line_series_vel", [[], []])
                
                dpg.fit_axis_data("x_axis")
                if auto_fit_y:
                    dpg.set_axis_limits("y_axis", -10, max(150, np.max(ys) + 20))
                else:
                    dpg.set_axis_limits_auto("y_axis")
            last_update = now
    
    if selected_jump:
        curr_p_x = dpg.get_value("plot_line_series_power")[0]
        if len(curr_p_x) == 0: 
            curve = selected_jump['force_curve']
            if curve:
                xs = [(p['t'] - curve[0]['t'])/1000.0 for p in curve]
                ys = [p['v'] for p in curve] 
                ps = [p['p'] for p in curve] 
                vs = [p.get('vel', 0) for p in curve] 
                
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

                dpg.set_value("plot_line_series_power", [xs, ps])
                dpg.set_value("plot_line_series_vel", [xs, vs])
                
                dpg.fit_axis_data("x_axis")
                dpg.fit_axis_data("y_axis")
                dpg.fit_axis_data("y_axis_power")
                dpg.fit_axis_data("y_axis_vel")

    dpg.render_dearpygui_frame()

dpg.destroy_context()
