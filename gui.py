
# gui.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QDialog
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap

from styles import dark_style
from experiment_setup import ExperimentSetupDialog, ILLUM_GREEN, ILLUM_IR
from experiment_runner import ExperimentRunner
from camera_config import CameraConfigDialog
from file_manager import FileManagerDialog
import motor_control
import camera

# --- Constants for LED colors/styles ---
SEA_FOAM_GREEN = "#26A69A"  # Green mode button color
DEEP_RED = "#B71C1C"        # Infrared mode button color


# LED GPIO setup
try:
    import gpiod
    from gpiod.line import Value, Direction
    LED_GREEN_PIN = 12
    LED_IR_PIN = 13
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


class SeedlingImagerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arabidopsis Seedling Imager")
        self.setFixedSize(800, 480)
        self.setStyleSheet(dark_style)

        self.threads = []
        self.experiment_thread = None
        self.active_illum_mode = ILLUM_GREEN

        main_layout = QHBoxLayout()
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setAlignment(Qt.AlignTop)
        button_width = 250

        self.live_view_btn = QPushButton("Live View")
        self.live_view_btn.setFixedWidth(button_width)
        self.live_view_btn.setStyleSheet(dark_style + " QPushButton { background-color: #FFD600; color: black; }")
        self.live_view_btn.clicked.connect(self.toggle_live_view)
        button_layout.addWidget(self.live_view_btn)

        self.illum_toggle_btn = QPushButton(f"Illum: {self.active_illum_mode}")
        self.illum_toggle_btn.setFixedWidth(button_width)
        self.apply_main_illum_style()
        self.illum_toggle_btn.clicked.connect(self.toggle_illumination_mode)
        button_layout.addWidget(self.illum_toggle_btn)

        ha_layout = QHBoxLayout()
        self.home_btn = QPushButton("Home"); self.home_btn.setFixedWidth(button_width // 2 - 5)
        self.advance_btn = QPushButton("Advance"); self.advance_btn.setFixedWidth(button_width // 2 - 5)
        ha_layout.addWidget(self.home_btn); ha_layout.addWidget(self.advance_btn)
        self.home_btn.clicked.connect(lambda: self.run_motor_action("home"))
        self.advance_btn.clicked.connect(lambda: self.run_motor_action("advance"))
        button_layout.addLayout(ha_layout)

        self.experiment_btn = QPushButton("Experiment Setup")
        self.experiment_btn.setFixedWidth(button_width)
        self.experiment_btn.setStyleSheet(dark_style + " QPushButton { background-color: #8E24AA; color: white; }")
        self.experiment_btn.clicked.connect(self.open_experiment_setup)
        button_layout.addWidget(self.experiment_btn)

        self.end_experiment_btn = QPushButton("End Experiment")
        self.end_experiment_btn.setFixedWidth(button_width)
        self.end_experiment_btn.setStyleSheet(dark_style + " QPushButton { background-color: #E53935; color: white; }")
        self.end_experiment_btn.clicked.connect(self.end_experiment)
        button_layout.addWidget(self.end_experiment_btn)

        # Camera Config button
        self.camera_config_btn = QPushButton("Camera Config")
        self.camera_config_btn.setFixedWidth(button_width)
        self.camera_config_btn.setStyleSheet(dark_style + " QPushButton { background-color: #546E7A; color: white; }")
        self.camera_config_btn.clicked.connect(self.open_camera_config)
        button_layout.addWidget(self.camera_config_btn)

        self.file_manager_btn = QPushButton("File Manager")
        self.file_manager_btn.setFixedWidth(button_width)
        self.file_manager_btn.setStyleSheet(
            dark_style + " QPushButton { background-color: #455A64; color: white; }"
        )
        self.file_manager_btn.clicked.connect(self.open_file_manager)
        button_layout.addWidget(self.file_manager_btn)


        main_layout.addLayout(button_layout)

        right_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Ready"); self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)
        self.camera_label = QLabel("Camera Preview"); self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setFixedSize(512, 288)
        right_layout.addWidget(self.camera_label, alignment=Qt.AlignRight)
        self.log_panel = QTextEdit(); self.log_panel.setReadOnly(True)
        right_layout.addWidget(self.log_panel)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

        self.timer = QTimer(); self.timer.timeout.connect(self.update_camera_frame)
        self.live_view_active = False
        self.update_controls_for_experiment(False)

        # Apply persisted camera settings at startup
        camera.apply_settings()

    def apply_main_illum_style(self):
        color = "#26A69A" if self.active_illum_mode == ILLUM_GREEN else "#B71C1C"
        self.illum_toggle_btn.setStyleSheet(dark_style + f" QPushButton {{ background-color: {color}; color: white; font-weight: bold; }}")

    def toggle_illumination_mode(self):
        """Switch between Green and Infrared illumination; update button style."""
        from gpiod.line import Value
        self.active_illum_mode = ILLUM_IR if self.active_illum_mode == ILLUM_GREEN else ILLUM_GREEN
        self.illum_toggle_btn.setText(f"Illum: {self.active_illum_mode}")
        self.apply_main_illum_style()

        # If live view is active, apply the new illumination immediately
        if self.live_view_active:
            if self.active_illum_mode == ILLUM_GREEN:
                led_request.set_value(12, Value.ACTIVE)
                led_request.set_value(13, Value.INACTIVE)
            else:
                led_request.set_value(12, Value.INACTIVE)
                led_request.set_value(13, Value.ACTIVE)

        self.update_status(f"Illumination set to {self.active_illum_mode}")


    def run_motor_action(self, action):
        worker = MotorWorker(action)
        self.threads.append(worker)
        worker.finished.connect(lambda: self.threads.remove(worker))
        worker.status_signal.connect(self.update_status)
        worker.start()

    def update_status(self, text):
        self.status_label.setText(text)
        self.log_panel.append(text)


    def toggle_live_view(self):
        if not self.live_view_active:
            camera.start_camera()
            camera.set_af_mode(2)  # Continuous AF for preview
            self.timer.start(100)
            self.live_view_active = True
            self.live_view_btn.setStyleSheet(dark_style + " QPushButton { background-color: #43A047; color: white; }")
            self.update_status(f"Live View started. {self.active_illum_mode} LED ON.")
            # Turn ON selected illumination
            if led_request:
                if self.active_illum_mode == ILLUM_GREEN:
                    led_request.set_value(LED_GREEN_PIN, Value.ACTIVE)
                    led_request.set_value(LED_IR_PIN, Value.INACTIVE)
                else:
                    led_request.set_value(LED_GREEN_PIN, Value.INACTIVE)
                    led_request.set_value(LED_IR_PIN, Value.ACTIVE)
        else:
            self.timer.stop()
            camera.stop_camera()
            self.live_view_active = False
            self.live_view_btn.setStyleSheet(dark_style + " QPushButton { background-color: #FFD600; color: black; }")
            self.update_status("Live View stopped.")
            # Turn OFF both LEDs
            if led_request:
                led_request.set_value(LED_GREEN_PIN, Value.INACTIVE)
                led_request.set_value(LED_IR_PIN, Value.INACTIVE)


    def update_camera_frame(self):
        frame = camera.get_frame()
        pixmap = QPixmap.fromImage(frame)
        self.camera_label.setPixmap(pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio))

    def open_experiment_setup(self):
        if self.live_view_active:
            self.toggle_live_view()
        dialog = ExperimentSetupDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.start_experiment(dialog.selected_plates, dialog.duration_days, dialog.frequency_minutes, dialog.selected_illum)

    def start_experiment(self, plates, days, freq, illum):
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.update_status("Experiment already running."); return
        if self.live_view_active: self.toggle_live_view()
        self.experiment_thread = ExperimentRunner(plates, days, freq, illum, self.set_led)
        self.experiment_thread.status_signal.connect(self.update_status)
        self.experiment_thread.image_saved_signal.connect(lambda p: self.log_panel.append(f"Image saved: {p}"))
        self.experiment_thread.plate_signal.connect(lambda idx: self.status_label.setText(f"Plate #{idx}"))
        self.experiment_thread.finished_signal.connect(self.on_experiment_finished)
        self.update_controls_for_experiment(True)
        self.experiment_thread.start()

    def end_experiment(self):
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.experiment_thread.abort(); self.experiment_thread.wait()
            self.update_status("Experiment ended by user.")
        else:
            self.update_status("No experiment running.")
        self.update_controls_for_experiment(False)

    def on_experiment_finished(self):
        self.update_controls_for_experiment(False)
        self.update_status("Experiment finished.")

    def update_controls_for_experiment(self, running):
        self.live_view_btn.setEnabled(not running)
        self.home_btn.setEnabled(not running)
        self.advance_btn.setEnabled(not running)
        self.experiment_btn.setEnabled(not running)
        self.illum_toggle_btn.setEnabled(not running)
        self.end_experiment_btn.setEnabled(running)
        self.camera_config_btn.setEnabled(not running)

    def open_camera_config(self):
        if self.live_view_active:
            self.toggle_live_view()  # Stop live preview while changing settings

        dialog = CameraConfigDialog(current_settings=camera.get_current_settings(), parent=self)
        if dialog.exec() == QDialog.Accepted:
            # Dialog saves settings to JSON internally
            camera.apply_settings(dialog.settings)
            self.update_status("Camera settings applied.")
            # Optionally restart Live View so user can see effect immediately
            # self.toggle_live_view()  # Uncomment if desired

    def set_led(self, on: bool, mode: str):
        """LED control helper passed to ExperimentRunner."""
        from gpiod.line import Value
        if mode == ILLUM_GREEN:
            led_request.set_value(12, Value.ACTIVE if on else Value.INACTIVE)
            led_request.set_value(13, Value.INACTIVE)
        else:
            led_request.set_value(12, Value.INACTIVE)
            led_request.set_value(13, Value.ACTIVE if on else Value.INACTIVE)

    def open_file_manager(self):
        # Stop Live View to avoid racing the camera while user manages files (optional)
        if self.live_view_active:
            self.toggle_live_view()
        dlg = FileManagerDialog(self)
        dlg.exec()

    def closeEvent(self, event):
        # Graceful shutdown
        if self.experiment_thread and self.experiment_thread.isRunning():
            self.experiment_thread.abort()
            self.experiment_thread.wait()
        if self.live_view_active:
            self.toggle_live_view()
        event.accept()


# MotorWorker class (unchanged from previous versions)
from PySide6.QtCore import QThread, Signal
class MotorWorker(QThread):
    status_signal = Signal(str)
    def __init__(self, action):
        super().__init__()
        self.action = action
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

