# Seedling Imager Controller

## Overview
Inspired by the SPIRO (Smart Plate Imaging Robot; Ohlsson et al., *The Plant Journal*, doi: 10.1111/tpj.16587) project, the **Seedling Imager** is a Raspberry Pi 5-based imaging system designed to monitor Arabidopsis seedling growth using a 6-position hexagonal carousel. It provides automated imaging, LED control, experiment scheduling, and camera configuration through a touch-friendly GUI.

---

## Features (v0.06)

### **GUI (PySide6)**
- Dark mode interface optimized for Raspberry Pi touchscreens.
- **Live View**:
  - Real-time preview from low-resolution stream (640×360) for speed.
  - Illumination toggle (Green @ GPIO12, IR @ GPIO13).
  - Continuous autofocus during preview.
- **Experiment Setup**:
  - Select plates (1–6) in a compact two-row layout with visible checkbox outlines.
  - Choose illumination mode (Green or Infrared) with color-coded toggle (teal for Green, deep red for IR).
  - Configure experiment duration (days) and acquisition frequency (minutes).
  - **Storage Estimate**:
    - Calculates expected image count and disk space usage.
    - Warns if estimated size exceeds available free space.
- **Camera Config Dialog**:
  - Adjust AE, exposure time, gain, AWB, contrast, brightness, saturation, sharpness, noise reduction, HDR.
  - Settings persist in `camera_settings.json` and apply to Live View and experiments.
- **File Manager**:
  - Browse experiments under `/home/sybednar/Seedling_Imager/images/`.
  - View metadata.json and disk usage.
  - **Thumbnails**:
    - Robust preview for TIFF/PNG/JPEG (fallback via `tifffile`, Pillow, or OpenCV).
    - Click thumbnail to open full image in system viewer.
  - **CSV Tab**:
    - Displays `metadata.csv` (sortable table).
    - Toolbar actions: Refresh, Open Folder, Archive (ZIP), Export, Delete, Open CSV.
    - Plate filter for thumbnails (All plates or plate1–plate6).
- **End Experiment** button for safe abort.

---

### **Experiment Runner**
- Automates time-lapse imaging cycles:
  - For each plate: illumination ON → autofocus → 10 s settle → capture (full-res TIFF) → illumination OFF → advance.
  - Drift correction applied when wrapping to Plate #1 (reports extra steps, even if zero).
  - Wait begins immediately after Plate 6, then next cycle starts at Plate 1.
- Signals for GUI:
  - `image_saved_signal(path)` updates preview with the **last captured image**.
  - `settling_started(plate_idx)` / `settling_finished(plate_idx)` enable **optional live preview during settle**.
- **CSV Metadata Logging**:
  - `metadata.csv` includes timestamp, cycle index, plate, illumination, image path, dimensions, file size, AE state, exposure time, gain, AWB.

---

### **Camera Integration**
- Picamera2 dual-stream configuration:
  - **main**: full-resolution RGB (4608×2592) for TIFF saving.
  - **lores**: low-resolution RGB (640×360) for Live View.
- Full-resolution TIFF saving with lossless zlib compression.
- Autofocus helpers:
  - Continuous AF for Live View.
  - Single AF trigger during settle before capture.
- AE lock/unlock for consistent intensity.

---

### **Motor Control**
- TMC2209 stepper driver via GPIO.
- Homing routine using hall sensor and optical sensor.
- Drift correction logic ensures alignment at Plate #1.

---

### **Illumination Control**
- AO4805 MOSFET 2P-CH driven Dual LED channels:
  - Green (520 nm) on GPIO12.
  - Infrared (940 nm) on GPIO13 for dark-grown seedlings.

---

### **Image Storage**
- Images saved under:
  ```
  /home/sybednar/Seedling_Imager/images/experiment_<YYYYMMDD_HHMMSS>/plateN/
  ```
- Filenames include plate number and timestamp.
- Metadata:
  - `metadata.json` (experiment settings).
  - `metadata.csv` (per-image details).

---

## Hardware Setup
- Raspberry Pi 5
- TMC2209 stepper driver
- AO4805 MOSFET 2P-CH 
- Hall sensor for homing
- Optical sensor (ITR20001) for drift correction
- LED panel with dual illumination (Green + IR)
- 12 MP Raspberry Pi Camera Module (NoIR for IR imaging)
- Raspberry Pi TouchDisplay

### GPIO Pin Map
| Function        | GPIO Pin |
|-----------------|----------|
| STEP           | 20       |
| DIR            | 16       |
| EN             | 21       |
| Hall Sensor    | 26       |
| Optical Sensor | 19       |
| Green LED      | 12       |
| IR LED         | 13       |

---

## Software Requirements
- Raspberry Pi OS (Bookworm recommended)
- Python 3.11+
- PySide6
- Picamera2
- OpenCV
- gpiod
- tifffile (for robust TIFF handling)
- Pillow (optional, for thumbnails fallback)

---

## Installation
```bash
# Clone repository
cd ~
git clone git@github.com:sybednar/Seedling-imager-.git
cd Seedling-imager-/seedling_imager_controller

# Create virtual environment
python3 -m venv /home/sybednar/Seedling_Imager
source /home/sybednar/Seedling_Imager/bin/activate

# Install dependencies
pip install PySide6 opencv-python picamera2 gpiod tifffile Pillow
```

---

## Autostart & Desktop Launcher
- Wrapper script: `start_seedling_imager.sh` activates venv and runs GUI.
- Autostart options:
  - **Systemd user service** (recommended): `~/.config/systemd/user/seedling-imager.service`.
  - **Desktop autostart**: `~/.config/autostart/seedling-imager.desktop`.
- Desktop icon:
  - `~/Desktop/Seedling-Imager.desktop` with `Exec` pointing to wrapper script and `Icon` set to PNG.

---

## Workflow
1. **Home** the carousel using the GUI button.
2. Use **Live View** to check illumination and framing.
3. Open **Experiment Setup**:
   - Select plates, duration, frequency, and illumination mode.
   - Review storage estimate.
4. Start experiment:
   - The system captures images per plate, applies drift correction, and waits for the configured interval before the next cycle.
   - Preview updates with the last saved image after each capture.
5. Press **End Experiment** to abort safely.
6. Use **File Manager** to browse, export, or archive experiments.

---

## License
MIT License
