#gui.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QDialog
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap
from experiment_setup import ExperimentSetupDialog
from styles import dark_style
import motor_control
import camera
import time

# Safe LED initialization
try:
    import gpiod
    LED_PIN = 12
    chip = "/dev/gpiochip0"
    led_request = gpiod.request_lines(
        chip,
        consumer="seedling_led",
        config={LED_PIN: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT, output_value=gpiod.line.Value.INACTIVE)}
    )
except Exception as e:
    print(f"LED init failed: {e}", flush=True)
    led_request = None

LED_ON = 10  # seconds for Advance

class MotorWorker(QThread):
    status_signal = Signal(str)

    def __init__(self, action):
        super().__init__()
        self.action = action

    def run(self):
        try:
            if self.action == "calibrate":
                plate = motor_control.calibrate(status_callback=self.status_signal.emit)
                if plate is not None:
                    self.status_signal.emit(f"Calibration finished. Plate #{plate}")
                else:
                    self.status_signal.emit("Calibration failed")
            elif self.action == "advance":
                self.status_signal.emit("Advancing to next plate...")
                plate = motor_control.advance(status_callback=self.status_signal.emit)
                if plate is None:
                    self.status_signal.emit("Advance failed")
        except Exception as e:
            self.status_signal.emit(f"Error: {e}")

class SeedlingImagerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arabidopsis Seedling Imager")
        self.setFixedSize(800, 480)

        # Apply global dark style
        self.setStyleSheet(dark_style)

        # Track active threads
        self.threads = []

        # Main layout: horizontal split
        main_layout = QHBoxLayout()
        main_layout.setSpacing(15)

        # Left side: vertical stack aligned to top
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setAlignment(Qt.AlignTop)

        button_width = 250  # Increased width for touch-friendly design

        # Live View button
        self.live_view_btn = QPushButton("Live View")
        self.live_view_btn.setFixedWidth(button_width)
        self.live_view_btn.setStyleSheet(dark_style + " QPushButton { background-color: #FFD600; color: black; }")
        self.live_view_btn.clicked.connect(self.toggle_live_view)
        button_layout.addWidget(self.live_view_btn)

        # Horizontal layout for Calibrate and Advance
        calibrate_advance_layout = QHBoxLayout()
        calibrate_advance_layout.setSpacing(10)

        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setFixedWidth(button_width // 2 - 5)
        calibrate_advance_layout.addWidget(self.calibrate_btn)

        self.advance_btn = QPushButton("Advance")
        self.advance_btn.setFixedWidth(button_width // 2 - 5)
        calibrate_advance_layout.addWidget(self.advance_btn)

        # Connect motor actions
        self.calibrate_btn.clicked.connect(lambda: self.run_motor_action("calibrate"))
        self.advance_btn.clicked.connect(lambda: self.run_motor_action("advance"))

        button_layout.addLayout(calibrate_advance_layout)

        # Experiment Setup button
        self.experiment_btn = QPushButton("Experiment Setup")
        self.experiment_btn.setFixedWidth(button_width)
        self.experiment_btn.setStyleSheet(dark_style + " QPushButton { background-color: #8E24AA; color: white; }")
        self.experiment_btn.clicked.connect(self.open_experiment_setup)
        button_layout.addWidget(self.experiment_btn)

        # Three placeholders for future buttons
        for i in range(3):
            future_btn = QPushButton("Future Function")
            future_btn.setFixedWidth(button_width)
            button_layout.addWidget(future_btn)

        main_layout.addLayout(button_layout)

        # Right side: preview and log
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)

        self.camera_label = QLabel("Camera Preview")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setFixedSize(512, 288)
        right_layout.addWidget(self.camera_label, alignment=Qt.AlignRight)

        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        right_layout.addWidget(self.log_panel)

        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

        # Timer for camera preview
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera_frame)

        # Live view state
        self.live_view_active = False

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
            if led_request:
                led_request.set_value(LED_PIN, gpiod.line.Value.ACTIVE)
            camera.start_camera()
            self.timer.start(100)
            self.live_view_active = True
            self.live_view_btn.setStyleSheet(dark_style + " QPushButton { background-color: #43A047; color: white; }")
            self.update_status("Live View started. LED ON.")
        else:
            self.timer.stop()
            camera.stop_camera()
            if led_request:
                led_request.set_value(LED_PIN, gpiod.line.Value.INACTIVE)
            self.live_view_active = False
            self.live_view_btn.setStyleSheet(dark_style + " QPushButton { background-color: #FFD600; color: black; }")
            self.update_status("Live View stopped. LED OFF.")

    def open_experiment_setup(self):
        # Turn off Live View if active
        if self.live_view_active:
            self.toggle_live_view()

        # Change button color to green
        self.experiment_btn.setStyleSheet(dark_style + " QPushButton { background-color: #43A047; color: white; }")

        # Open dialog
        dialog = ExperimentSetupDialog(self)
        result = dialog.exec()

        # Reset button color to purple after closing
        self.experiment_btn.setStyleSheet(dark_style + " QPushButton { background-color: #8E24AA; color: white; }")

        if result == QDialog.Accepted:
            # Retrieve values from dialog
            duration_days = dialog.duration_days
            frequency_minutes = dialog.frequency_minutes
            selected_plates = dialog.selected_plates

            # Log experiment configuration
            self.update_status(
                f"Experiment configured:\n"
                f"Duration: {duration_days} days\n"
                f"Frequency: every {frequency_minutes} min\n"
                f"Plates: {', '.join(selected_plates)}"
            )

    def update_camera_frame(self):
        frame = camera.get_frame()
        pixmap = QPixmap.fromImage(frame)
        self.camera_label.setPixmap(pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio))

    def closeEvent(self, event):
        for thread in self.threads:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        if led_request:
            led_request.set_value(LED_PIN, gpiod.line.Value.INACTIVE)
        event.accept()



















