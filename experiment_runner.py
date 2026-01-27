# experiment_runner.py
from PySide6.QtCore import QThread, Signal
from datetime import datetime, timedelta
from pathlib import Path
import time
import json
import csv
import os
import motor_control
import camera
from camera_config import load_settings

class ExperimentRunner(QThread):
    status_signal = Signal(str)
    image_saved_signal = Signal(str)
    plate_signal = Signal(int)
    settling_started = Signal(int)
    settling_finished = Signal(int)
    finished_signal = Signal()

    def __init__(self, selected_plates, duration_days, frequency_minutes,
                 illumination_mode, led_control_fn, parent=None):
        super().__init__(parent)
        self.selected_plates = self._normalize_plates(selected_plates)
        self.duration_days = int(duration_days)
        self.frequency_minutes = int(frequency_minutes)
        self.illumination_mode = illumination_mode
        self.led_control_fn = led_control_fn
        self._abort = False
        self.wait_seconds_for_camera = 10
        self.cycle_count = 0  # NEW: count cycles for CSV logging

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = Path("/home/sybednar/Seedling_Imager/images").expanduser()
        self.run_dir = root / f"experiment_{ts}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for p in range(1, 7):
            (self.run_dir / f"plate{p}").mkdir(exist_ok=True)

        # Persist camera settings (JSON) created earlier
        self.cam_settings = load_settings()
        meta_path = self.run_dir / "metadata.json"
        meta = {
            "timestamp_start": datetime.now().isoformat(timespec="seconds"),
            "illumination_mode": self.illumination_mode,
            "selected_plates": self.selected_plates,
            "frequency_minutes": self.frequency_minutes,
            "duration_days": self.duration_days,
            "camera_settings": self.cam_settings
        }
        meta_path.write_text(json.dumps(meta, indent=2))

        # NEW: Prepare CSV metadata file
        self.csv_path = self.run_dir / "metadata.csv"
        self.csv_file = None
        self.csv_writer = None

    def _normalize_plates(self, plate_names):
        idxs = []
        for name in plate_names:
            try:
                idxs.append(int(name.split()[-1]))
            except Exception:
                pass
        return [p for p in idxs if 1 <= p <= 6]

    def abort(self):
        self._abort = True

    def _log(self, msg):
        self.status_signal.emit(msg)

    def _sleep_with_abort(self, seconds):
        end = time.time() + seconds
        while time.time() < end and not self._abort:
            time.sleep(0.1)

    def _open_csv(self):
        """Open metadata.csv and write header."""
        try:
            self.csv_file = open(self.csv_path, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                "timestamp_iso",
                "cycle_index",
                "plate",
                "illumination",
                "image_path",
                "width_px",
                "height_px",
                "file_size_bytes",
                "AeEnable",
                "ExposureTime_us",
                "AnalogueGain",
                "AwbEnable"
            ])
        except Exception as e:
            self._log(f"CSV open error: {e}")

    def _close_csv(self):
        try:
            if self.csv_file:
                self.csv_file.flush()
                self.csv_file.close()
        except Exception:
            pass

    def run(self):
        if not self.selected_plates:
            self._log("No plates selected; experiment aborted.")
            self.finished_signal.emit()
            return

        # Ensure driver is enabled prior to homing (GUI Stop may have left EN high)
        motor_control.driver_enable()  # EN low = enabled                         # [1](https://uwprod-my.sharepoint.com/personal/sybednar_wisc_edu/Documents/Microsoft%20Copilot%20Chat%20Files/seedling%20imager_controller_v0.06.txt)

        plate = motor_control.home(status_callback=self.status_signal.emit)
        if plate is None:
            self._log("Homing failed; experiment aborted.")
            self.finished_signal.emit()
            return

        try:
            camera.start_camera()
            camera.apply_settings(self.cam_settings)
        except Exception as e:
            self._log(f"Camera start error: {e}")
            self.finished_signal.emit()
            return

        # Open CSV once
        self._open_csv()
        self._log(
            f"Experiment started: {self.duration_days} day(s), "
            f"every {self.frequency_minutes} min. Illumination: {self.illumination_mode}"
        )

        end_time = datetime.now() + timedelta(days=self.duration_days)
        try:
            while datetime.now() < end_time and not self._abort:
                self.cycle_count += 1
                motor_control.goto_plate(1, status_callback=self.status_signal.emit)
                self.plate_signal.emit(1)

                for plate_idx in range(1, 7):
                    if self._abort:
                        break
                    # LED ON
                    if self.led_control_fn:
                        self.led_control_fn(True, self.illumination_mode)
                    # Settle: AE on + settle preview
                    camera.set_auto_exposure(True)
                    # (Optional AF trigger here if you've added it)
                    self.settling_started.emit(plate_idx)
                    self._log(f"Plate #{plate_idx}: waiting {self.wait_seconds_for_camera}s...")
                    self._sleep_with_abort(self.wait_seconds_for_camera)
                    self.settling_finished.emit(plate_idx)
                    if self._abort:
                        break
                    # Lock AE for consistent capture
                    camera.set_auto_exposure(False)
                    # Capture if plate selected
                    if plate_idx in self.selected_plates:
                        ts_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        img_name = f"plate{plate_idx}_{ts_str}.tif"
                        img_path = str(self.run_dir / f"plate{plate_idx}" / img_name)
                        saved = camera.save_image(img_path)
                        if saved:
                            # Size & dimensions
                            width = height = None
                            shape = camera.get_last_saved_shape()
                            if shape:
                                height, width = shape  # we stored (h, w)
                            try:
                                file_size = Path(img_path).stat().st_size
                            except Exception:
                                file_size = None
                            # Capture metadata snapshot
                            md = camera.get_metadata()
                            AeEnable = md.get("AeEnable", None)
                            ExposureTime = md.get("ExposureTime", None)  # microseconds
                            AnalogueGain = md.get("AnalogueGain", None)
                            AwbEnable = md.get("AwbEnable", None)
                            # Write CSV row
                            if self.csv_writer:
                                self.csv_writer.writerow([
                                    datetime.now().isoformat(timespec="seconds"),
                                    self.cycle_count,
                                    plate_idx,
                                    self.illumination_mode,
                                    img_path,
                                    width,
                                    height,
                                    file_size,
                                    AeEnable,
                                    ExposureTime,
                                    AnalogueGain,
                                    AwbEnable
                                ])
                            self.image_saved_signal.emit(img_path)
                            self._log(f"Saved: {img_path}")
                        else:
                            self._log(f"Capture failed on plate {plate_idx}")
                    else:
                        self._log(f"Plate #{plate_idx}: skipped.")
                    # LED OFF
                    if self.led_control_fn:
                        self.led_control_fn(False, self.illumination_mode)
                    # Re-enable AE for next plate’s settle
                    camera.set_auto_exposure(True)
                    # Advance (drift correction on wrap handled in motor_control.advance)
                    motor_control.advance(status_callback=self.status_signal.emit)
                    self.plate_signal.emit(1 if plate_idx == 6 else plate_idx + 1)
                # Post-cycle wait after plate 6
                if plate_idx == 6 and not self._abort:
                    self._log(f"Cycle complete. Waiting {self.frequency_minutes} min...")
                    self._sleep_with_abort(self.frequency_minutes * 60)
        finally:
            # Wrap up
            self._log("Experiment finished." if not self._abort else "Experiment aborted.")
            try:
                camera.stop_camera()
            except Exception:
                pass
            if self.led_control_fn:
                self.led_control_fn(False, self.illumination_mode)
            self._close_csv()
            self.finished_signal.emit()