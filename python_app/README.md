# Force Plate PRO - Python Desktop App

The desktop companion application for the Force Plate PRO system. Built with Python 3.10 and **Dear PyGui**, it handles high-frequency data acquisition, complex physics modeling, and real-time visualization of ground reaction forces.

## Key Features

*   **Real-Time Visualization:** Smooth layout of Force, Velocity, and Power graphs rendering at 60 FPS while processing 1280 Hz sensor data.
*   **Physics Engine:** Implements **Impulse-Momentum** and **Flight Time** methods for jump height calculation.
    *   *Retroactive Integration:* Buffers data to capture the critical "start of movement" moments before trigger thresholds.
    *   *Drift Compensation:* Automatically re-zeros the platform if weight drift is detected during inactivity.
    *   *Bounce Protection:* Filters out mechanical vibrations after takeoff.
*   **Exercise Modes:**
    *   **Countermovement Jump (CMJ):** Full phase analysis (Unweighting, Braking, Propulsion, Flight, Landing).
    *   **Contact Time:** Optimized for measuring quick rebound jumps.
    *   **Continuous Jump:** Chains multiple jumps in a single recording. Tracks per-jump height, power, and contact time, providing an aggregated summary once the athlete steps off the plate.
    *   **Isometric Tests:** (In development) For measuring peak force without movement.
*   **Data Persistence:** Automatic saving of jump history and raw data to `jumps_data.db` (SQLite).
*   **Hardware Integration:** Auto-connects to ESP32 via USB Serial (defaults to 921600 baud).

## Keyboard Controls

The application supports comprehensive keyboard navigation for high-speed operation:

| Category | Key | Action |
| :--- | :--- | :--- |
| **Navigation** | `Esc` | Deselect jump / Back to Main Menu |
| | `Enter` | Select mode in Main Menu |
| | `Up/Down` | Navigate Menu or Jump History |
| **Plotting** | `L/R Shift` | Toggle Sticky Cursor (info on hover) |
| | `Y` | Toggle Y-Axis Auto-fit |
| | `R` | Reset View (return to live stream) |
| | `WASD / Arrows` | Pan graph (W/S vertical, A/D horizontal) |
| | `Q / E` | Zoom Graph Out / In |
| **System** | `T` | Manual Tare |
| | `Z` | Reset Connection (soft restart) |
| | `X` | Reset Device (hard reset command) |

## Installation

1.  **Prerequisites:**
    *   Python 3.10 or newer.
    *   Drivers for your ESP32's USB-UART bridge (CP210x or CH340).

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application:**
    ```bash
    python main.py
    ```

## Project Structure

*   **`main.py`**: Application entry point. Initializes the UI loop, Database, and Serial Handler.
*   **`physics.py`**: The core Physics Engine. Handles:
    *   Circular buffering of raw samples.
    *   Trapezoidal integration for Velocity and Power.
    *   State machine logic for lift-off and landing detection.
*   **`serial_handler.py`**: Manages the threaded serial connection to the ESP32. Parses incoming JSON data streams.
*   **`database.py`**: Handling SQLite `jumps_data.db` for storing results and application settings (like calibration factors).
*   **`ui/`**: User Interface modules using Dear PyGui.
    *   **`plot_manager.py`**: Optimizes plotting performance by downsampling data for display without losing measurement precision.
*   **`modes/`**: Specific logic for different exercise types (Single Jump, Repeat Jumps, etc.).

## Usage Guide

1.  **Connect:** Plug in the ESP32. The app usually auto-connects. If not, check the "Connection" status in the top bar.
2.  **Calibrate (Tare):** Ensure the plate is empty. The system tares automatically on startup, but you can force a re-tare if needed.
3.  **Jump:**
    *   Stand still on the plate ("WEIGHING").
    *   Wait for the "READY" signal.
    *   Perform your jump.
4.  **Analyze:**
    *   Click on any jump in the history sidebar to view its Force/Velocity/Power curves.
    *   **Sticky Cursor:** Hold `L/R Shift` or toggle the "Sticky Cursor" checkbox to enable data inspection. Hover over the plot to see exact values at any point.
    *   **Graph Navigation:** Use `WASD` or `Arrow Keys` to pan, and `Q/E` to zoom for detailed inspection.

## Troubleshooting

*   **"Not Connecting":** Check if the COM port is being used by another app (like Arduino Serial Monitor). Close other apps and restart.
*   **"Drifting Weight/inaccurate weight":** Tare and calibrate to ensure the best results, worst case scenario reset connection and device using dedicated buttons.
