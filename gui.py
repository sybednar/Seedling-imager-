
# gui.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QDialog
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap

from styles import dark_style
from experiment_setup import ExperimentSetupDialog, ILLUM_GREEN, ILLUM_IR
from experiment_runner import ExperimentRunner
import motor_control
import camera

# --- Constants for LED colors/styles ---
SEA_FOAM_GREEN = "#26A69A"  # Green mode button color
DEEP_RED = "#B71C1C"        # Infrared mode button color

# --- GPIO setup for LEDs ---
try:
    import gpiod
    from gpiod.line import Value, Direction
    LED_GREEN_PIN = 12  # GPIO12 -> Green LED (520 nm)
    LED_IR_PIN = 13     # GPIO13 -> Infrared LED (940 nm)

    chip = "/dev/gpiochip0"
    led_request = gpiod.request_lines(
        chip,
        consumer="seedling_leds",
        config={
            LED_GREEN_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
            LED_IR_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        }
    )
except Exception as e:
    print(f"LED init failed: {e}", flush=True)
    led_request = None


# --- Motor worker thread for homing/advance ---
class MotorWorker(QThread):
    status_signal = Signal(str)

    def __init__(self, action):
        super().__init__()
        self.action = action  # "home" or "advance"

    def run(self):
        try:
            if self.action == "home":
                plate = motor_control.home(status_callback=self.status_signal.emit)
                if plate is not None:
                    self.status_signal.emit(f"Homing finished. Plate #{plate}")
                else:
                    self.status_signal.emit("Homing failed")
            elif self.action == "advance":
                self.status_signal.emit("Advancing to next plate...")
                motor_control.advance(status_callback=self.status_signal.emit)
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")


class SeedlingImagerGUI(QWidget):
    def __init__(self):
        super().__init__()

        # --- Window setup ---
        self.setWindowTitle("Arabidopsis Seedling Imager")
        self.setFixedSize(800, 480)  # Touch-friendly size for Pi display
        self.setStyleSheet(dark_style)

        # --- Thread tracking ---
        self.threads = []
        self.experiment_thread = None

        # --- Illumination mode state (default to Green) ---
        self.active_illum_mode = ILLUM_GREEN

        # --- Main layout: horizontal split ---
        main_layout = QHBoxLayout()
        main_layout.setSpacing(15)

        # --- Left: control buttons ---
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setAlignment(Qt.AlignTop)
        button_width = 250

        # Live View
        self.live_view_btn = QPushButton("Live View")
        self.live_view_btn.setFixedWidth(button_width)
        self.live_view_btn.setStyleSheet(
            dark_style + " QPushButton { background-color: #FFD600; color: black; }"
        )
        self.live_view_btn.clicked.connect(self.toggle_live_view)
        button_layout.addWidget(self.live_view_btn)

        # Illumination toggle (Green/Infrared)
        self.illum_toggle_btn = QPushButton(f"Illum: {self.active_illum_mode}")
        self.illum_toggle_btn.setFixedWidth(button_width)
        self.apply_main_illum_style()
        self.illum_toggle_btn.clicked.connect(self.toggle_illumination_mode)
        button_layout.addWidget(self.illum_toggle_btn)

        # Home + Advance row
        ha_layout = QHBoxLayout()
        ha_layout.setSpacing(10)

        self.home_btn = QPushButton("Home")
        self.home_btn.setFixedWidth(button_width // 2 - 5)
        ha_layout.addWidget(self.home_btn)

        self.advance_btn = QPushButton("Advance")
        self.advance_btn.setFixedWidth(button_width // 2 - 5)
        ha_layout.addWidget(self.advance_btn)

        # Connect motor actions
        self.home_btn.clicked.connect(lambda: self.run_motor_action("home"))
        self.advance_btn.clicked.connect(lambda: self.run_motor_action("advance"))
        button_layout.addLayout(ha_layout)

        # Experiment Setup
        self.experiment_btn = QPushButton("Experiment Setup")
        self.experiment_btn.setFixedWidth(button_width)
        self.experiment_btn.setStyleSheet(
            dark_style + " QPushButton { background-color: #8E24AA; color: white; }"
        )
        self.experiment_btn.clicked.connect(self.open_experiment_setup)
        button_layout.addWidget(self.experiment_btn)

        # End Experiment
        self.end_experiment_btn = QPushButton("End Experiment")
        self.end_experiment_btn.setFixedWidth(button_width)
        self.end_experiment_btn.setStyleSheet(
            dark_style + " QPushButton { background-color: #E53935; color: white; }"
        )
        self.end_experiment_btn.clicked.connect(self.end_experiment)
        button_layout.addWidget(self.end_experiment_btn)

        # Future placeholders (optional)
        for i in range(2):
            future_btn = QPushButton("Future Function")
            future_btn.setFixedWidth(button_width)
            button_layout.addWidget(future_btn)

        main_layout.addLayout(button_layout)

        # --- Right: status + preview + log ---
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)

        self.camera_label = QLabel("Camera Preview")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setFixedSize(512, 288)  # 16:9 preview area
        right_layout.addWidget(self.camera_label, alignment=Qt.AlignRight)

        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        right_layout.addWidget(self.log_panel)

        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

        # --- Preview timer (used for live preview) ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera_frame)

        # --- Live view flag ---
        self.live_view_active = False

        # UI state helpers
        self.update_controls_for_experiment(running=False)

    # -----------------------------
    # Illumination helpers & styles
    # -----------------------------
    def apply_main_illum_style(self):
        """Update main-window illumination toggle button color."""
        if self.active_illum_mode == ILLUM_GREEN:
            self.illum_toggle_btn.setStyleSheet(
                dark_style + f" QPushButton {{ background-color: {SEA_FOAM_GREEN}; color: white; font-weight: bold; }}"
            )
        else:
            self.illum_toggle_btn.setStyleSheet(
                dark_style + f" QPushButton {{ background-color: {DEEP_RED}; color: white; font-weight: bold; }}"
            )

    def set_leds(self, green_on=False, ir_on=False):
        """Low-level LED control using a single gpiod request for both lines."""
        if not led_request:
            return
        led_request.set_value(LED_GREEN_PIN, Value.ACTIVE if green_on else Value.INACTIVE)
        led_request.set_value(LED_IR_PIN, Value.ACTIVE if ir_on else Value.INACTIVE)

    def set_illum(self, on: bool, mode: str):
        """Used by ExperimentRunner to set illumination deterministically."""
        if mode == ILLUM_GREEN:
            self.set_leds(green_on=on, ir_on=False)
        else:
            self.set_leds(green_on=False, ir_on=on)

    def apply_active_illumination(self, on: bool):
        """Turn on/off currently selected illumination mode (for Live View)."""
        self.set_illum(on, self.active_illum_mode)

    def toggle_illumination_mode(self):
        """Switch between Green and Infrared; applies immediately if Live View is active."""
        self.active_illum_mode = ILLUM_IR if self.active_illum_mode == ILLUM_GREEN else ILLUM_GREEN
        self.illum_toggle_btn.setText(f"Illum: {self.active_illum_mode}")
        self.apply_main_illum_style()
        if self.live_view_active:
            self.apply_active_illumination(True)
        self.update_status(f"Illumination set to {self.active_illum_mode}")

    # -----------------------------
    # Motor control threading
    # -----------------------------
    def run_motor_action(self, action):
        worker = MotorWorker(action)
        self.threads.append(worker)
        worker.finished.connect(lambda: self.threads.remove(worker))
        worker.status_signal.connect(self.update_status)
        worker.start()

    # -----------------------------
    # Status & logging
    # -----------------------------
    def update_status(self, text):
        self.status_label.setText(text)
        self.log_panel.append(text)

    # -----------------------------
    # Live View control
    # -----------------------------
    def toggle_live_view(self):
        if not self.live_view_active:
            # Turn on selected illumination
            self.apply_active_illumination(True)
            # Start camera preview
            camera.start_camera()
            self.timer.start(100)  # ~10 fps preview
            self.live_view_active = True
            self.live_view_btn.setStyleSheet(
                dark_style + " QPushButton { background-color: #43A047; color: white; }"
            )
            self.update_status(f"Live View started. {self.active_illum_mode} LED ON.")
        else:
            # Stop preview and camera
            self.timer.stop()
            camera.stop_camera()
            # Safety: ensure both LEDs are OFF
            self.set_leds(green_on=False, ir_on=False)
            self.live_view_active = False
            self.live_view_btn.setStyleSheet(
                dark_style + " QPushButton { background-color: #FFD600; color: black; }"
            )
            self.update_status("Live View stopped. LEDs OFF.")

    def update_camera_frame(self):
        frame = camera.get_frame()
        pixmap = QPixmap.fromImage(frame)
        self.camera_label.setPixmap(pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio))

    # -----------------------------
    # Preview last saved image
    # -----------------------------
    def display_saved_image(self, path: str):
        """Load the last saved image and show it in the preview pane."""
        try:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.camera_label.setPixmap(
                    pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio)
                )
                self.update_status(f"Preview updated: {path}")
            else:
                self.update_status(f"Preview load failed (empty image): {path}")
        except Exception as e:
            self.update_status(f"Preview load error: {e}")

    # -----------------------------
    # Settle signals (optional live preview during wait)
    # -----------------------------
    def on_settling_started(self, plate_idx: int):
        """Start the live preview during the settle period."""
        self.timer.start(100)  # 10 fps preview
        self.update_status(f"Settling on plate {plate_idx}: live preview ON")

    def on_settling_finished(self, plate_idx: int):
        """Stop the live preview right before capture."""
        self.timer.stop()
        self.update_status(f"Settling finished on plate {plate_idx}: live preview OFF")

    # -----------------------------
    # Experiment Setup & run
    # -----------------------------
    def open_experiment_setup(self):
        # Turn off Live View if active
        if self.live_view_active:
            self.toggle_live_view()

        # Visual feedback for opening
        self.experiment_btn.setStyleSheet(
            dark_style + " QPushButton { background-color: #43A047; color: white; }"
        )
        dialog = ExperimentSetupDialog(self)  # parent is GUI for centering
        result = dialog.exec()
        # Reset button color
        self.experiment_btn.setStyleSheet(
            dark_style + " QPushButton { background-color: #8E24AA; color: white; }"
        )

        if result == QDialog.Accepted:
            duration_days = dialog.duration_days
            frequency_minutes = dialog.frequency_minutes
            selected_plates = dialog.selected_plates
            selected_illum = dialog.selected_illum  # from dialog

            self.update_status(
                f"Experiment configured:\n"
                f"Duration: {duration_days} days\n"
                f"Frequency: every {frequency_minutes} min\n"
                f"Plates: {', '.join(selected_plates)}\n"
                f"Illumination: {selected_illum}"
            )

            # Store illumination choice for Live View consistency (optional)
            self.active_illum_mode = selected_illum
            self.illum_toggle_btn.setText(f"Illum: {self.active_illum_mode}")
            self.apply_main_illum_style()

            # Start experiment thread
            self.start_experiment(selected_plates, duration_days, frequency_minutes, selected_illum)

    def start_experiment(self, selected_plates, duration_days, frequency_minutes, illum_mode):
        # Prevent multiple runs
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.update_status("Experiment already running.")
            return

        # Ensure camera preview is off
        if self.live_view_active:
            self.toggle_live_view()

        # Create runner
        self.experiment_thread = ExperimentRunner(
            selected_plates=selected_plates,
            duration_days=duration_days,
            frequency_minutes=frequency_minutes,
            illumination_mode=illum_mode,
            led_control_fn=self.set_illum
        )
        # Hook signals
        self.experiment_thread.status_signal.connect(self.update_status)
        self.experiment_thread.image_saved_signal.connect(self.display_saved_image)
        self.experiment_thread.image_saved_signal.connect(
            lambda p: self.log_panel.append(f"Image saved: {p}")
        )
        self.experiment_thread.plate_signal.connect(lambda idx: self.status_label.setText(f"Plate #{idx}"))
        self.experiment_thread.settling_started.connect(self.on_settling_started)
        self.experiment_thread.settling_finished.connect(self.on_settling_finished)
        self.experiment_thread.finished_signal.connect(self.on_experiment_finished)

        # Update UI
        self.update_controls_for_experiment(running=True)
        self.update_status("Starting experiment...")
        self.experiment_thread.start()

    def end_experiment(self):
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.update_status("Ending experiment (please wait)...")
            self.experiment_thread.abort()
            self.experiment_thread.wait()  # block until the thread finishes
            self.update_status("Experiment ended by user.")
            self.update_controls_for_experiment(running=False)
            # Ensure LEDs off
            self.set_leds(green_on=False, ir_on=False)
        else:
            self.update_status("No experiment is running.")

    def on_experiment_finished(self):
        self.update_controls_for_experiment(running=False)
        self.update_status("Experiment thread finished.")
        # Ensure LEDs off
        self.set_leds(green_on=False, ir_on=False)

    def update_controls_for_experiment(self, running: bool):
        """Disable/enable controls to avoid conflicts during experiments."""
        self.live_view_btn.setEnabled(not running)
        self.home_btn.setEnabled(not running)
        self.advance_btn.setEnabled(not running)
        self.experiment_btn.setEnabled(not running)
        self.illum_toggle_btn.setEnabled(not running)
        self.end_experiment_btn.setEnabled(running)

    # -----------------------------
    # Graceful close
    # -----------------------------
    def closeEvent(self, event):
        # End experiment if running
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.experiment_thread.abort()
            self.experiment_thread.wait()
        # Stop preview if active
        if self.live_view_active:
            self.toggle_live_view()
        # Safety: LEDs OFF
        self.set_leds(green_on=False, ir_on=False)
        event.accept()
