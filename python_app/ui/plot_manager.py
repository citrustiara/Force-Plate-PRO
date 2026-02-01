import dearpygui.dearpygui as dpg
import numpy as np

class PlotManager:
    """
    Manages the DPG plot, including smart downsampling to preserve peaks.
    """
    def __init__(self, buffer_view_func_ref):
        self.get_buffer_view = buffer_view_func_ref
        self.last_update_time = 0.0
        self.update_interval = 0.033 # 30 FPS

    def heavy_average_downsample(self, data, target_points=150):
        """
        Downsample data using simple MEAN to provide a smooth, heavily averaged signal.
        This suppresses noise and peaks, suitable for monitoring state.
        :param data: 2D array [time, weight, ...]
        :return: xs, ys (as arrays)
        """
        if len(data) == 0:
            return [], []
        
        n_points = len(data)
        if n_points <= target_points:
             return (data[:, 0] - data[-1, 0]) / 1000.0 + 5, data[:, 1]
        
        # Calculate chunk size
        chunk_size = max(1, n_points // target_points)
        n_chunks = n_points // chunk_size
        
        # Truncate to multiple of chunk_size
        limit = n_chunks * chunk_size
        view = data[:limit]
        
        # Reshape to (n_chunks, chunk_size, columns)
        reshaped = view.reshape(n_chunks, chunk_size, -1)
        
        # Time: Mean of chunk
        xs_chunk = reshaped[:, :, 0].mean(axis=1) 
        
        # Weight Logic: Simple Mean (Heavy Averaging)
        ys_chunk = reshaped[:, :, 1].mean(axis=1)
        
        # Normalize Time
        t_last = data[-1, 0]
        xs = (xs_chunk - t_last) / 1000.0 + 5
        
        return xs, ys_chunk

    def update_live_plot(self, physics, now, is_contact_mode=False):
        if now - self.last_update_time < self.update_interval:
            return
            
        data = self.get_buffer_view(physics.logic_time, 5000)
        if len(data) > 0:
            xs, ys = self.heavy_average_downsample(data)
            
            # Update Plot
            # We need to make sure arrays are contiguous
            xs = np.ascontiguousarray(xs)
            ys = np.ascontiguousarray(ys)
            
            dpg.set_value("plot_line_series", [xs, ys])
            
            # Mass Line
            mass = physics.jumper_mass_kg if physics.jumper_mass_kg > 0 else 0
            if mass > 0 and len(xs) > 0:
                dpg.set_value("plot_line_series_mass", [[xs[0], xs[-1]], [mass, mass]])
            else:
                 dpg.set_value("plot_line_series_mass", [[], []])

            # Clear others
            dpg.set_value("plot_line_series_power", [[], []])
            dpg.set_value("plot_line_series_vel", [[], []])
            dpg.set_value("plot_line_series_ct_start", [[], []])
            dpg.set_value("plot_line_series_ct_end", [[], []])
            dpg.set_value("plot_line_phase_unweight", [[], []])
            dpg.set_value("plot_line_phase_braking", [[], []])
            dpg.set_value("plot_line_phase_propulsion", [[], []])
            
            # Update hover data
            from .callbacks import update_current_plot_data
            update_current_plot_data(xs, ys, [], [])
            
            dpg.fit_axis_data("x_axis")
            
            # Auto-fit Y
            from .callbacks import is_autofit_enabled
            if is_autofit_enabled():
                # Ensure we show at least 150kg range or data range
                y_max = max(150, np.max(ys) + 20) if len(ys) > 0 else 150
                dpg.set_axis_limits("y_axis", -10, y_max)
            else:
                dpg.set_axis_limits_auto("y_axis")
                
        self.last_update_time = now

    def update_selected_from_jump(self, jump_data):
        curve = jump_data.get('force_curve')
        if not curve:
            return
            
        xs = [(p['t'] - curve[0]['t'])/1000.0 for p in curve]
        ys = [p['v'] for p in curve] 
        
        has_power = all(p.get('p') is not None for p in curve)
        has_vel = all(p.get('vel') is not None for p in curve)

        ps = [p.get('p', 0) for p in curve] if has_power else []
        vs = [p.get('vel', 0) for p in curve] if has_vel else []
        
        xs = np.ascontiguousarray(xs)
        ys = np.ascontiguousarray(ys)
        ps = np.ascontiguousarray(ps)
        vs = np.ascontiguousarray(vs)
        
        dpg.set_value("plot_line_series", [xs, ys])
        
        mass = jump_data.get('jumper_weight', 0)
        if mass > 0 and len(xs) > 0:
           dpg.set_value("plot_line_series_mass", [[xs[0], xs[-1]], [mass, mass]])
        else:
           dpg.set_value("plot_line_series_mass", [[], []])

        dpg.set_value("plot_line_series_power", [xs, ps] if has_power else [[], []])
        dpg.set_value("plot_line_series_vel", [xs, vs] if has_vel else [[], []])
        
        # CT Markers
        t_start = jump_data.get('contact_start_time')
        t_end = jump_data.get('contact_end_time')
        t_curv = jump_data.get('curve_start_time')
        if t_start and t_end and t_curv:
            x_s = (t_start - t_curv) / 1000.0
            x_e = (t_end - t_curv) / 1000.0
            max_y = np.max(ys) if len(ys) > 0 else 200
            dpg.set_value("plot_line_series_ct_start", [[x_s, x_s], [0, max_y]])
            dpg.set_value("plot_line_series_ct_end", [[x_e, x_e], [0, max_y]])
        else:
            dpg.set_value("plot_line_series_ct_start", [[], []])
            dpg.set_value("plot_line_series_ct_end", [[], []])
        
        from .callbacks import update_current_plot_data
        update_current_plot_data(xs, ys, ps if has_power else [], vs if has_vel else [])

        # Phase Markers (vertical lines at phase boundaries)
        phase_times = jump_data.get('phase_times')
        curve_start = jump_data.get('curve_start_time')
        max_y = np.max(ys) if len(ys) > 0 else 200
        
        if phase_times and curve_start:
            # Unweight start (when velocity left ~0)
            t_unweight = phase_times.get('unweighting_start', 0)
            if t_unweight > 0:
                x_unweight = (t_unweight - curve_start) / 1000.0
                dpg.set_value("plot_line_phase_unweight", [[x_unweight, x_unweight], [0, max_y]])
            else:
                dpg.set_value("plot_line_phase_unweight", [[], []])
            
            # Braking start (min velocity time)
            t_braking = phase_times.get('min_velocity_time', 0)
            if t_braking > 0:
                x_braking = (t_braking - curve_start) / 1000.0
                dpg.set_value("plot_line_phase_braking", [[x_braking, x_braking], [0, max_y]])
            else:
                dpg.set_value("plot_line_phase_braking", [[], []])
            
            # Propulsion start (zero crossing time)
            t_propulsion = phase_times.get('zero_crossing_time', 0)
            if t_propulsion > 0:
                x_propulsion = (t_propulsion - curve_start) / 1000.0
                dpg.set_value("plot_line_phase_propulsion", [[x_propulsion, x_propulsion], [0, max_y]])
            else:
                dpg.set_value("plot_line_phase_propulsion", [[], []])
        else:
            dpg.set_value("plot_line_phase_unweight", [[], []])
            dpg.set_value("plot_line_phase_braking", [[], []])
            dpg.set_value("plot_line_phase_propulsion", [[], []])

        dpg.fit_axis_data("x_axis")
        dpg.fit_axis_data("y_axis")
        dpg.fit_axis_data("y_axis_power")
        dpg.fit_axis_data("y_axis_vel")
