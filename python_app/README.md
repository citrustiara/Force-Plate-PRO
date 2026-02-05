# Force Plate PRO - Python Application

The Python application is the brain of the Force Plate PRO system. It handles:
- Serial communication with the ESP32.
- High-frequency data processing (circular buffering, filtering).
- Physics integration (Impulse-Momentum method).
- Real-time visualization using DearPyGui.
- Data storage (SQLite).

## Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt`

## Installation
```bash
pip install -r requirements.txt
```

## Usage
Run the main script:
```bash
python main.py
```

*Detailed documentation and explanation of physics algorithms will be added here.*
