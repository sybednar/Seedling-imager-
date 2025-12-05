#experiment_setup.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QGridLayout, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt
from styles import dark_style

class ExperimentSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Experiment Setup")
        self.setMinimumWidth(600)

        # Apply dark mode styling for overall dialog
        self.setStyleSheet(dark_style)

        # Main layout
        main_layout = QVBoxLayout()

        # Duration input
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Duration (days):")
        duration_label.setStyleSheet("font-size: 18px; color: white;")
        self.duration_value = QLineEdit("1")
        self.duration_value.setAlignment(Qt.AlignCenter)
        self.duration_value.setFixedSize(120, 70)
        self.duration_value.setStyleSheet("background-color: white; color: black; font-size: 24px;")

        duration_up = QPushButton("▲")
        duration_down = QPushButton("▼")
        for btn in (duration_up, duration_down):
            btn.setFixedSize(70, 70)
            btn.setStyleSheet("background-color: #ccc; font-size: 28px; font-weight: bold;")

        duration_up.clicked.connect(lambda: self.adjust_value(self.duration_value, 1, 1, 7))
        duration_down.clicked.connect(lambda: self.adjust_value(self.duration_value, -1, 1, 7))

        duration_layout.addWidget(duration_label)
        duration_layout.addStretch()
        duration_layout.addWidget(duration_up)
        duration_layout.addWidget(self.duration_value)
        duration_layout.addWidget(duration_down)
        main_layout.addLayout(duration_layout)

        # Acquisition Frequency input
        freq_layout = QHBoxLayout()
        freq_label = QLabel("Acquisition Frequency (minutes):")
        freq_label.setStyleSheet("font-size: 18px; color: white;")
        self.freq_value = QLineEdit("30")
        self.freq_value.setAlignment(Qt.AlignCenter)
        self.freq_value.setFixedSize(120, 70)
        self.freq_value.setStyleSheet("background-color: white; color: black; font-size: 24px;")

        freq_up = QPushButton("▲")
        freq_down = QPushButton("▼")
        for btn in (freq_up, freq_down):
            btn.setFixedSize(70, 70)
            btn.setStyleSheet("background-color: #ccc; font-size: 28px; font-weight: bold;")

        freq_up.clicked.connect(lambda: self.adjust_value(self.freq_value, 30, 30, 360))
        freq_down.clicked.connect(lambda: self.adjust_value(self.freq_value, -30, 30, 360))

        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_up)
        freq_layout.addWidget(self.freq_value)
        freq_layout.addWidget(freq_down)
        main_layout.addLayout(freq_layout)

        # Add extra space below Acquisition Frequency
        main_layout.addSpacing(20)

        # Instruction label
        instruction_label = QLabel("Select plates for experiment:")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet("font-size: 18px; color: white;")
        main_layout.addWidget(instruction_label)

        # Add extra space above plate grid
        main_layout.addSpacing(20)

        # Hexagonal layout for plate selection
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(20)
        grid_layout.setVerticalSpacing(15)

        self.plate_checkboxes = {}
        positions = {
            (0, 1): "Plate 6",
            (0, 2): "Plate 5",
            (1, 0): "Plate 1",
            (1, 3): "Plate 4",
            (2, 1): "Plate 2",
            (2, 2): "Plate 3"
        }

        for pos, name in positions.items():
            checkbox = QCheckBox(name)
            checkbox.setStyleSheet("color: white; font-size: 18px;")
            self.plate_checkboxes[name] = checkbox
            grid_layout.addWidget(checkbox, pos[0], pos[1])

        main_layout.addLayout(grid_layout)

        # Add extra space below plate grid
        main_layout.addSpacing(30)

        # Buttons layout
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Experiment")
        self.exit_button = QPushButton("Exit")

        self.start_button.setStyleSheet("background-color: #43A047; color: white; font-weight: bold; padding: 12px; font-size: 20px;")
        self.exit_button.setStyleSheet("background-color: #E53935; color: white; font-weight: bold; padding: 12px; font-size: 20px;")

        self.start_button.clicked.connect(self.validate_and_start)
        self.exit_button.clicked.connect(self.reject)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.exit_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def adjust_value(self, line_edit, step, min_val, max_val):
        try:
            current = int(line_edit.text())
        except ValueError:
            current = min_val
        new_val = max(min_val, min(max_val, current + step))
        line_edit.setText(str(new_val))

    def validate_and_start(self):
        selected = [name for name, cb in self.plate_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Validation Error", "Please select at least one plate before starting the experiment.")
            return
        self.selected_plates = selected
        self.duration_days = int(self.duration_value.text())
        self.frequency_minutes = int(self.freq_value.text())
        self.accept()

