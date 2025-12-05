
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPalette, QColor
import motor_control
import gpiod
import time

# GPIO for LED
LED_PIN = 12
LED_ON = 10  # seconds

# Prepare LED control
chip = "/dev/gpiochip0"
led_request = gpiod.request_lines(
    chip,
    consumer="seedling_led",
    config={
        LED_PIN: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT, output_value=gpiod.line.Value.INACTIVE)
    }
)

class MotorWorker(QThread):
    status_signal = Signal(str)

    def __init__(self, action):
        super().__init__()
        self.action = action

    def run(self):
        try:
            print(f"DEBUG: MotorWorker started for {self.action}", flush=True)
            if self.action == "calibrate":
                plate = motor_control.calibrate(status_callback=self.status_signal.emit)
                if plate:
                    self.status_signal.emit(f"Calibration finished. Plate #{plate}")
                else:
                    self.status_signal.emit("Calibration failed")
            elif self.action == "advance":
                self.status_signal.emit("Advancing to next plate...")
                plate = motor_control.advance()
                self.status_signal.emit(f"Moved to Plate #{plate}")

                # Turn LED ON for LED_ON seconds
                self.status_signal.emit("Turning LED ON for imaging...")
                led_request.set_value(LED_PIN, gpiod.line.Value.ACTIVE)  # HIGH = LED ON
                print("DEBUG: LED ON", flush=True)
                time.sleep(LED_ON)
                led_request.set_value(LED_PIN, gpiod.line.Value.INACTIVE)  # LOW = LED OFF
                self.status_signal.emit("LED OFF after imaging")
                print("DEBUG: LED OFF", flush=True)

        except Exception as e:
            err_msg = f"Error: {e}"
            print(err_msg, flush=True)
            self.status_signal.emit(err_msg)

class SeedlingImagerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arabidopsis Seedling Imager")
        self.setFixedSize(800, 480)

        # Apply dark mode palette
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(18, 18, 18))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(30, 136, 229))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        self.setPalette(dark_palette)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignTop)

        # Status label for latest message
        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.status_label)

        # Scrollable log panel
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setStyleSheet("background-color: #121212; color: #FFFFFF; font-size: 16px;")
        layout.addWidget(self.log_panel)

        # Buttons
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setStyleSheet("background-color: #1E88E5; color: white; font-size: 20px; padding: 12px; border-radius: 8px;")
        self.calibrate_btn.clicked.connect(lambda: self.run_motor_action("calibrate"))

        self.advance_btn = QPushButton("Advance")
        self.advance_btn.setStyleSheet("background-color: #1E88E5; color: white; font-size: 20px; padding: 12px; border-radius: 8px;")
        self.advance_btn.clicked.connect(lambda: self.run_motor_action("advance"))

        layout.addWidget(self.calibrate_btn)
        layout.addWidget(self.advance_btn)

        self.setLayout(layout)

    def run_motor_action(self, action):
        self.worker = MotorWorker(action)
        self.worker.status_signal.connect(self.update_status)
        self.worker.start()

    def update_status(self, text):
        # Update main status label and append to log panel
        self.status_label.setText(text)
        self.log_panel.append(text)
        print(f"GUI Status: {text}", flush=True)
