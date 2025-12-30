
# experiment_runner.py
from PySide6.QtCore import QThread, Signal
from datetime import datetime, timedelta
from pathlib import Path
import time

import motor_control
import camera

class ExperimentRunner(QThread):
    """
    Executes time-lapse acquisition cycles:
      - Start at Plate #1 each cycle (goto_plate).
      - For each plate 1..6: turn on light, wait 10s, capture if selected, turn off light, advance.
      - Advance wraps to #1 and drift-corrects (via motor_control.advance()).
      - After Plate 6, wait frequency_minutes, then begin next cycle at Plate 1.
      - Repeat until duration reached or aborted.
    """

    # Signals to update GUI
    status_signal = Signal(str)
    image_saved_signal = Signal(str)    # emits file path
    plate_signal = Signal(int)          # current plate index 1..6
    settling_started = Signal(int)      # plate index (before wait)
    settling_finished = Signal(int)     # plate index (after wait)
    finished_signal = Signal()          # experiment completed or aborted

    def __init__(self, selected_plates, duration_days, frequency_minutes, illumination_mode,
                 led_control_fn, parent=None):
        """
        Args:
            selected_plates (list[str]): e.g., ["Plate 1", "Plate 3", ...]
            duration_days (int)
            frequency_minutes (int)
            illumination_mode (str): "Green" or "Infrared"
            led_control_fn (callable): (on: bool, mode: str) -> None
        """
        super().__init__(parent)
        self.selected_plates = self._normalize_plates(selected_plates)
        self.duration_days = int(duration_days)
        self.frequency_minutes = int(frequency_minutes)
        self.illumination_mode = illumination_mode
        self.led_control_fn = led_control_fn

        self._abort = False
        self.wait_seconds_for_camera = 10  # settle time per plate

        # Prepare directory structure: experiment_<timestamp>/plateN
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use a writable path (update to your preferred location)
        root = Path("/home/sybednar/Seedling_Imager/images").expanduser()
        self.run_dir = root / f"experiment_{ts}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for p in range(1, 7):
            (self.run_dir / f"plate{p}").mkdir(exist_ok=True)

    # ---------- helpers ----------
    def _normalize_plates(self, plate_names):
        idxs = []
        for name in plate_names:
            try:
                idxs.append(int(name.split()[-1]))
            except Exception:
                pass
        # Keep order as selected in the dialog
        return [p for p in idxs if 1 <= p <= 6]

    def abort(self):
        self._abort = True

    def _log(self, msg):
        self.status_signal.emit(msg)

    def _sleep_with_abort(self, seconds):
        """Sleep in short chunks so abort is responsive."""
        end = time.time() + seconds
        while time.time() < end and not self._abort:
            time.sleep(0.1)

    # ---------- main thread run ----------
    def run(self):
        if not self.selected_plates:
            self._log("No plates selected; experiment aborted.")
            self.finished_signal.emit()
            return

        # Home/index before the very first cycle
        plate = motor_control.home(status_callback=self.status_signal.emit)
        if plate is None:
            self._log("Homing failed; experiment aborted.")
            self.finished_signal.emit()
            return

        # Start camera once for the whole experiment
        try:
            camera.start_camera()
        except Exception as e:
            self._log(f"Camera start error: {e}")
            self.finished_signal.emit()
            return

        self._log(
            f"Experiment started: {self.duration_days} day(s), "
            f"every {self.frequency_minutes} min. Illumination: {self.illumination_mode}"
        )

        end_time = datetime.now() + timedelta(days=self.duration_days)

        # === Main loop: repeat cycles until duration or abort ===
        while datetime.now() < end_time and not self._abort:
            # Ensure we start each cycle at Plate #1 (no full homing between cycles)
            motor_control.goto_plate(1, status_callback=self.status_signal.emit)
            self.plate_signal.emit(1)

            # --- Iterate through plates 1..6 ---
            for plate_idx in range(1, 7):
                if self._abort:
                    break

                # Turn ON selected illumination
                if self.led_control_fn:
                    self.led_control_fn(True, self.illumination_mode)

                # Live preview during settle (optional)
                self.settling_started.emit(plate_idx)

                # Wait for camera to adjust (10 s)
                self._log(
                    f"Plate #{plate_idx}: {self.illumination_mode} LED ON, waiting {self.wait_seconds_for_camera}s..."
                )
                self._sleep_with_abort(self.wait_seconds_for_camera)

                # Stop live preview right before capture (optional)
                self.settling_finished.emit(plate_idx)
                if self._abort:
                    break

                # Capture image IF this plate is selected
                if plate_idx in self.selected_plates:
                    img_name = f"plate{plate_idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    img_path = str(self.run_dir / f"plate{plate_idx}" / img_name)
                    saved = camera.save_image(img_path)
                    if saved:
                        self.image_saved_signal.emit(img_path)
                        self._log(f"Saved: {img_path}")
                    else:
                        self._log(f"Capture failed on plate {plate_idx}")
                else:
                    self._log(f"Plate #{plate_idx}: skipped (not selected).")

                # Turn OFF illumination
                if self.led_control_fn:
                    self.led_control_fn(False, self.illumination_mode)

                # Advance to next position
                motor_control.advance(status_callback=self.status_signal.emit)
                self.plate_signal.emit(1 if plate_idx == 6 else plate_idx + 1)

                # If we just finished Plate 6, start the period wait now
                if plate_idx == 6 and not self._abort:
                    self._log(f"Cycle complete. Waiting {self.frequency_minutes} minute(s) before next cycle...")
                    self._sleep_with_abort(self.frequency_minutes * 60)
                    # After the wait, the while-loop will begin the next cycle by goto_plate(1)

        # Wrap up
        if self._abort:
            self._log("Experiment aborted by user.")
        else:
            self._log("Experiment finished.")

        try:
            camera.stop_camera()
        except Exception:
            pass

        # Ensure LEDs are OFF
        if self.led_control_fn:
            self.led_control_fn(False, self.illumination_mode)

        self.finished_signal.emit()
