# Seedling Imager Controller

## Overview
The Seedling Imager is a Raspberry Pi-based imaging system designed to monitor Arabidopsis seedling growth using a 6-position hexagonal carousel. It provides automated imaging, LED control, and experiment scheduling through a touch-friendly GUI.

## Features
- **GUI** built with PySide6 (dark mode interface)
- **Live View** camera preview with LED control
- **Experiment Setup Dialog**:
  - Hexagonal plate selection (1–6 positions)
  - Touch-friendly numeric input for duration and acquisition frequency
- **Motor Control**:
  - TMC2209 stepper driver
  - Drift correction using optical sensor
- **Camera Integration**:
  - Picamera2 for Raspberry Pi
  - Real-time preview and image capture

## Hardware Setup
- Raspberry Pi 5
- TMC2209 stepper driver
- Optical sensor (ITR20001) for drift correction
- Hall sensor for homing
- LED panel controlled via GPIO

## GPIO Pin Map
| Function        | GPIO Pin |
|-----------------|----------|
| STEP           | 16       |
| DIR            | 20       |
| EN             | 21       |
| Hall Sensor    | 26       |
| Optical Sensor | 19       |
| LED Control    | 12       |

## Software Requirements
- Python 3.11+
- PySide6
- Picamera2
- OpenCV
- gpiod

## Installation
```bash
# Clone repository
cd ~
git clone git@github.com:sybednar/Seedling_Imager.git
cd Seedling_Imager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install PySide6 opencv-python picamera2 gpiod
```

## Usage
```bash
# Activate virtual environment
source venv/bin/activate

# Run GUI
python3 main.py
```

## License
MIT License
