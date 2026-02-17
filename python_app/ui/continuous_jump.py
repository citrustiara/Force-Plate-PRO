"""
Continuous Jump mode UI controller.
Shows aggregate metrics, connection status, and collapsible jump details table.
"""
import dearpygui.dearpygui as dpg
from .base import ModeController
from .callbacks import show_menu, reset_connection_callback, reset_platform_callback, reset_view_callback


def create_continuous_jump_header():
    """Create the Continuous Jump mode header UI elements."""
    with dpg.group(tag="group_header_continuous", show=False):
        # HEADER LINE
        with dpg.group(horizontal=True):
            dpg.add_button(label="< MENU", callback=show_menu)
            dpg.add_spacer(width=20)
            dpg.add_text("Continuous Jump Mode", color=(0, 255, 255))
            dpg.add_text("|")
            
            # Connection status circle
            with dpg.drawlist(width=16, height=16):
                dpg.draw_circle((8, 8), 6, fill=(200, 0, 0, 255), tag="connection_circle_cj")
            
            dpg.add_spacer(width=10)
            
            # Buttons
            dpg.add_button(label="Reset Connection", tag="btn_reset_conn_cj", callback=reset_connection_callback, width=120)
            dpg.add_button(label="Reset Platform", tag="btn_reset_plat_cj", callback=reset_platform_callback, width=110)
            dpg.add_button(label="Reset View", callback=reset_view_callback, width=100)
            
            dpg.add_spacer(width=150)
            dpg.add_text("State:", color=(150, 150, 150))
            dpg.add_text("IDLE", tag="met_cj_state", color=(255, 255, 255))

        dpg.add_separator()
        
        # --- METRICS ROW ---
        with dpg.group(horizontal=True):
            with dpg.group():
                dpg.add_text("JUMPS", color=(150, 150, 150))
                dpg.add_text("0", tag="met_cj_jump_count", color=(255, 255, 255))
            dpg.add_spacer(width=20)
            with dpg.group():
                dpg.add_text("AVG HEIGHT", color=(150, 150, 150))
                dpg.add_text("-- cm", tag="met_cj_avg_height", color=(255, 255, 255))
            dpg.add_spacer(width=20)
            with dpg.group():
                dpg.add_text("BEST HEIGHT", color=(150, 150, 150))
                dpg.add_text("-- cm", tag="met_cj_best_height", color=(255, 255, 255))
            dpg.add_spacer(width=20)
            with dpg.group():
                dpg.add_text("AVG CONTACT TIME", color=(150, 150, 150))
                dpg.add_text("-- ms", tag="met_cj_avg_ct", color=(255, 255, 255))
            dpg.add_spacer(width=20)
            with dpg.group():
                dpg.add_text("BEST CONTACT TIME", color=(150, 150, 150))
                dpg.add_text("-- ms", tag="met_cj_best_ct", color=(255, 255, 255))
            dpg.add_spacer(width=20)
            with dpg.group():
                dpg.add_text("MASS", color=(150, 150, 150))
                dpg.add_text("-- kg", tag="met_cj_mass", color=(255, 255, 255))

        dpg.add_separator()
        
        # --- COLLAPSIBLE JUMP DETAILS TABLE ---
        with dpg.collapsing_header(label="Jump Details", tag="cj_details_header", default_open=False):
            with dpg.table(tag="cj_details_table",
                           header_row=True,
                           borders_innerH=True,
                           borders_outerH=True,
                           borders_innerV=True,
                           borders_outerV=True,
                           resizable=True,
                           policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(label="#")
                dpg.add_table_column(label="Height (cm)")
                dpg.add_table_column(label="Flight (ms)")
                dpg.add_table_column(label="Contact (ms)")
                dpg.add_table_column(label="Peak Power (W)")
                dpg.add_table_column(label="Takeoff Vel (m/s)")
                dpg.add_table_column(label="Peak Force (kg)")


class ContinuousJumpController(ModeController):
    def __init__(self, name):
        super().__init__(name)
        self._last_table_count = 0  # Track rows to avoid redundant updates
    
    def setup_ui(self):
        pass

    def on_enter(self):
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

    def on_exit(self):
        dpg.hide_item("group_header_continuous")
        self._last_table_count = 0

    def _update_table(self, jumps):
        """Update the jump details table with current jump data."""
        if len(jumps) == self._last_table_count:
            return  # No change
            
        # Clear existing rows
        children = dpg.get_item_children("cj_details_table", 1)
        if children:
            for row in children:
                dpg.delete_item(row)
        
        # Add rows for each jump
        for j in jumps:
            with dpg.table_row(parent="cj_details_table"):
                dpg.add_text(str(j.get("jump_number", "?")))
                dpg.add_text(f"{j['height_flight']:.1f}")
                dpg.add_text(f"{j['flight_time']:.0f}")
                ct = j.get("contact_time")
                dpg.add_text(f"{ct:.0f}" if ct is not None else "--")
                dpg.add_text(f"{j.get('peak_power', 0):.0f}")
                dpg.add_text(f"{j.get('velocity_takeoff', 0):.2f}")
                dpg.add_text(f"{j.get('max_force', 0):.1f}")
        
        self._last_table_count = len(jumps)

    def update(self, physics, dt, selected_jump):
        mode = physics.active_mode
        
        # Live state update
        state = getattr(mode, 'state', 'IDLE')
        color = (255, 255, 255)
        if state == "READY": color = (0, 255, 0)
        elif state == "WEIGHING": color = (255, 255, 0)
        elif state == "PROPULSION": color = (255, 165, 0)
        elif state == "LANDING": color = (255, 100, 100)
        elif state == "IN_AIR": color = (0, 255, 255)
        
        dpg.configure_item("met_cj_state", default_value=state, color=color)
        dpg.set_value("met_cj_mass", self.safe_fmt(getattr(mode, 'jumper_mass_kg', 0), "kg"))
        
        # Live metrics from completed jumps
        jumps = getattr(mode, 'completed_jumps', [])
        jump_count = len(jumps)
        dpg.set_value("met_cj_jump_count", str(jump_count))
        
        if jump_count > 0:
            heights = [j["height_flight"] for j in jumps]
            contact_times = [j["contact_time"] for j in jumps if j["contact_time"] is not None]
            
            dpg.set_value("met_cj_avg_height", self.safe_fmt(sum(heights) / len(heights), "cm"))
            dpg.set_value("met_cj_best_height", self.safe_fmt(max(heights), "cm"))
            
            if contact_times:
                dpg.set_value("met_cj_avg_ct", self.safe_fmt(sum(contact_times) / len(contact_times), "ms", ".0f"))
                dpg.set_value("met_cj_best_ct", self.safe_fmt(min(contact_times), "ms", ".0f"))
            
            # Update table with live jump data
            self._update_table(jumps)
        
        # Selected historical jump
        if selected_jump:
            dpg.set_value("met_cj_jump_count", str(selected_jump.get("jump_count", "--")))
            dpg.set_value("met_cj_avg_height", self.safe_fmt(selected_jump.get("avg_height"), "cm"))
            dpg.set_value("met_cj_best_height", self.safe_fmt(selected_jump.get("best_height") or selected_jump.get("height_flight"), "cm"))
            dpg.set_value("met_cj_avg_ct", self.safe_fmt(selected_jump.get("avg_contact_time"), "ms", ".0f"))
            dpg.set_value("met_cj_best_ct", self.safe_fmt(selected_jump.get("best_contact_time"), "ms", ".0f"))
            dpg.set_value("met_cj_mass", self.safe_fmt(selected_jump.get("jumper_weight"), "kg"))
            
            # Populate table from sub_jumps if available
            sub_jumps = selected_jump.get("sub_jumps", [])
            if sub_jumps:
                self._update_table(sub_jumps)
