# Force Plate PRO - Python Desktop App

The desktop companion application for the Force Plate PRO system. Built with Python 3.10 and **Dear PyGui**, it handles high-frequency data acquisition, complex physics modeling, and real-time visualization of ground reaction forces.

## Key Features

*   **Real-Time Visualization:** Smooth layout of Force, Velocity, and Power graphs rendering at 60 FPS while processing 1280 Hz sensor data.
*   **Physics Engine:** Implements **Impulse-Momentum** and **Flight Time** methods for jump height calculation.
    *   *Retroactive Integration:* Buffers data to capture the critical "start of movement" moments before trigger thresholds.
    *   *Bounce Protection:* Filters out mechanical vibrations after takeoff.
    *   *Measurement/Display Separation:* Live plots are downsampled for readability, while physics calculations work from the high-rate sample buffer.
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
    *   Fixed-rate sample timing based on the measured ADC rate.
    *   Calibration/tare flow and delegation to the active exercise mode.
*   **`serial_handler.py`**: Manages the threaded serial connection to the ESP32. Parses incoming JSON data streams.
*   **`database.py`**: Handling SQLite `jumps_data.db` for storing results and application settings (like calibration factors).
*   **`ui/`**: User Interface modules using Dear PyGui.
    *   **`plot_manager.py`**: Optimizes plotting performance by downsampling data for display without losing measurement precision.
*   **`modes/`**: Specific logic for different exercise types (Single Jump, Repeat Jumps, etc.).

## Signal Processing Notes

The current denoising approach is intentionally conservative: the firmware streams raw values, the physics engine converts them to kilograms, and the plot manager averages chunks only for display. That makes the system easy to reason about, but it leaves room for a proper measurement filter layer.

Recommended next step:

1.  Extend the `signal_processing/` package with a `SignalConditioner` that receives raw samples and returns both raw and filtered kilograms.
2.  Use simple real-time filters first: moving median or Hampel spike rejection, a causal low-pass IIR filter, and slow baseline tracking while the plate is unloaded.
3.  Keep raw data in the circular buffer so saved jumps can be reprocessed with improved algorithms later.
4.  Use FFT/Welch analysis on recorded quiet/impact sessions to choose filter cutoffs and find resonance/noise sources. Treat FFT/Welch as diagnostics, not the default live denoiser.

This matters because broad averaging makes the UI pleasant, but it can flatten peak force, move threshold crossings, and change jump phase timing.

## Refactoring Plan

The largest files are currently carrying too many responsibilities:

| File | Current role | Suggested split |
| :--- | :--- | :--- |
| `modes/single_jump.py` | State machine, edge cases, integration, result assembly | Keep mode transitions here; move phase detection and metric/result building to `metrics/` |
| `modes/continuous_jump.py` | Multi-jump state machine plus summary generation | Share landing/takeoff helpers with single jump; move aggregation to a result builder |
| `ui/callbacks.py` | Connection, history, mode switching, keyboard, plot cursor | Split into `ui/actions.py`, `ui/history.py`, `ui/navigation.py`, and `ui/plot_interaction.py` |
| `physics.py` | Engine, calibration, buffer utilities, mode registry | Move buffer and signal conditioning into `signal_processing/`; keep orchestration in `PhysicsEngine` |
| `database.py` | Schema creation, migrations, serialization, settings | Split schema/migrations from repository-style load/save methods |

Target package shape:

```text
python_app/
  acquisition/
  signal_processing/
  domain/
  metrics/
  modes/
  storage/
  ui/
```

Refactor in small steps: extract pure helpers first, add tests around those helpers, then replace state-string comparisons with enums once behavior is covered.

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
