"""
Theme definitions for the Force Plate PRO application.
"""
import dearpygui.dearpygui as dpg


def setup_themes():
    """Create and apply all themes."""
    # Global Theme
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (20, 20, 20), category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Header, (40, 40, 40), category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5, category=dpg.mvThemeCat_Core)

    dpg.bind_theme(global_theme)

    # Individual Series Themes
    
    # Force Line Theme (Electric Blue)
    with dpg.theme(tag="theme_force_line"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (0, 191, 255), category=dpg.mvThemeCat_Core)

    # Power Line Theme (Neon Green)
    with dpg.theme(tag="theme_power_line"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (57, 255, 20), category=dpg.mvThemeCat_Core)

    # Velocity Line Theme (Vivid Magenta)
    with dpg.theme(tag="theme_vel_line"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 0, 255), category=dpg.mvThemeCat_Core)

    # Mass Line Theme (Bright Yellow)
    with dpg.theme(tag="theme_mass_line"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 255, 0), category=dpg.mvThemeCat_Core)

    # Contact Time Marker Theme (Bright Orange)
    with dpg.theme(tag="theme_ct_marker"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 128, 0), category=dpg.mvThemeCat_Core)

    # Phase Marker Themes
    with dpg.theme(tag="theme_phase_unweight"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 100, 100), category=dpg.mvThemeCat_Core)  # Red
    
    with dpg.theme(tag="theme_phase_braking"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (100, 100, 255), category=dpg.mvThemeCat_Core)  # Blue
    
    with dpg.theme(tag="theme_phase_propulsion"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (100, 255, 100), category=dpg.mvThemeCat_Core)  # Green
