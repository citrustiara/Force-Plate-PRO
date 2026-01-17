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

    # Mass Line Theme (Yellow)
    with dpg.theme(tag="theme_mass_line"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 255, 0), category=dpg.mvThemeCat_Core)

    # Contact Time Marker Theme (Orange)
    with dpg.theme(tag="theme_ct_marker"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (255, 165, 0), category=dpg.mvThemeCat_Core)
