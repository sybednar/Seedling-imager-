
# experiment_setup.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QGridLayout, QCheckBox, QLineEdit, QWidget
)
from PySide6.QtCore import Qt
from styles import dark_style

ILLUM_GREEN = "Green"
ILLUM_IR = "Infrared"

SEA_FOAM_GREEN = "#26A69A"  # current green-ish teal
DEEP_RED = "#B71C1C"        # requested deep red for IR

class ExperimentSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Experiment Setup")
        # Keep width reasonable for 800x480 screen and reduce height to avoid cutoff
        self.setMinimumWidth(580)
        self.setStyleSheet(dark_style)

        self.selected_illum = ILLUM_GREEN  # default

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(18, 14, 18, 14)

        # --- Illumination selector row ---
        illum_row = QHBoxLayout()
        illum_label = QLabel("Illumination:")
        illum_label.setStyleSheet("font-size: 18px; color: white;")
        self.illum_toggle = QPushButton(self.selected_illum)
        self.illum_toggle.setFixedSize(160, 48)
        self.apply_illum_style()
        self.illum_toggle.clicked.connect(self.toggle_illum)
        illum_row.addWidget(illum_label, alignment=Qt.AlignLeft)
        illum_row.addStretch()
        illum_row.addWidget(self.illum_toggle, alignment=Qt.AlignRight)
        main_layout.addLayout(illum_row)

        # --- Duration input ---
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Duration (days):")
        duration_label.setStyleSheet("font-size: 18px; color: white;")
        self.duration_value = QLineEdit("1")
        self.duration_value.setAlignment(Qt.AlignCenter)
        self.duration_value.setFixedSize(110, 60)
        self.duration_value.setStyleSheet("background-color: white; color: black; font-size: 22px;")
        duration_up = QPushButton("▲")
        duration_down = QPushButton("▼")
        for btn in (duration_up, duration_down):
            btn.setFixedSize(58, 60)
            btn.setStyleSheet("background-color: #ccc; font-size: 24px; font-weight: bold;")
        duration_up.clicked.connect(lambda: self.adjust_value(self.duration_value, 1, 1, 7))
        duration_down.clicked.connect(lambda: self.adjust_value(self.duration_value, -1, 1, 7))
        duration_layout.addWidget(duration_label)
        duration_layout.addStretch()
        duration_layout.addWidget(duration_up)
        duration_layout.addWidget(self.duration_value)
        duration_layout.addWidget(duration_down)
        main_layout.addLayout(duration_layout)

        # --- Frequency input ---
        freq_layout = QHBoxLayout()
        freq_label = QLabel("Acquisition Frequency (minutes):")
        freq_label.setStyleSheet("font-size: 18px; color: white;")
        self.freq_value = QLineEdit("1") #changed value to 1 for testing, change back to 30 min for final version
        self.freq_value.setAlignment(Qt.AlignCenter)
        self.freq_value.setFixedSize(110, 60)
        self.freq_value.setStyleSheet("background-color: white; color: black; font-size: 22px;")
        freq_up = QPushButton("▲")
        freq_down = QPushButton("▼")
        for btn in (freq_up, freq_down):
            btn.setFixedSize(58, 60)
            btn.setStyleSheet("background-color: #ccc; font-size: 24px; font-weight: bold;")
        freq_up.clicked.connect(lambda: self.adjust_value(self.freq_value, 30, 1, 360)) #changed second argument (min value) to 1 for testing change back to 30 min for final version
        freq_down.clicked.connect(lambda: self.adjust_value(self.freq_value, -30, 1, 360)) #changed second argument (min value) to 1 for testing change back to 30 min for final version
        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_up)
        freq_layout.addWidget(self.freq_value)
        freq_layout.addWidget(freq_down)
        main_layout.addLayout(freq_layout)

        # --- Instruction ---
        instruction_label = QLabel("Select plates for experiment:")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet("font-size: 18px; color: white;")
        main_layout.addWidget(instruction_label)

        # --- Two centered rows of checkboxes with visible outlines ---
        # Row 1: Plate 1, 2, 3
        # Row 2: Plate 4, 5, 6
        plate_font_css = (
            "QCheckBox { color: white; font-size: 16px; } "
            "QCheckBox::indicator { width: 22px; height: 22px; } "
            "QCheckBox::indicator:unchecked { border: 2px solid #BBBBBB; background: #222222; } "
            "QCheckBox::indicator:checked { border: 2px solid #1E88E5; background: #1E88E5; } "
        )

        row1 = QHBoxLayout()
        row1.setSpacing(24)
        row1.setAlignment(Qt.AlignCenter)

        row2 = QHBoxLayout()
        row2.setSpacing(24)
        row2.setAlignment(Qt.AlignCenter)

        self.plate_checkboxes = {}
        for name in ["Plate 1", "Plate 2", "Plate 3"]:
            cb = QCheckBox(name)
            cb.setStyleSheet(plate_font_css)
            self.plate_checkboxes[name] = cb
            row1.addWidget(cb)

        for name in ["Plate 4", "Plate 5", "Plate 6"]:
            cb = QCheckBox(name)
            cb.setStyleSheet(plate_font_css)
            self.plate_checkboxes[name] = cb
            row2.addWidget(cb)

        main_layout.addLayout(row1)
        main_layout.addLayout(row2)

        # --- Buttons ---
        main_layout.addSpacing(8)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        self.start_button = QPushButton("Start Experiment")
        self.exit_button = QPushButton("Exit")
        self.start_button.setStyleSheet("background-color: #43A047; color: white; font-weight: bold; padding: 10px; font-size: 18px;")
        self.exit_button.setStyleSheet("background-color: #E53935; color: white; font-weight: bold; padding: 10px; font-size: 18px;")
        self.start_button.clicked.connect(self.validate_and_start)
        self.exit_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.exit_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # Compact the dialog to avoid cutoff and center on parent
        self.adjustSize()
        self.setFixedSize(self.sizeHint())
        self.center_on_parent()

    def center_on_parent(self):
        p = self.parent()
        if p and p.isVisible():
            # Center relative to parent window
            parent_geo = p.geometry()
            self.move(
                parent_geo.x() + (parent_geo.width() - self.width()) // 2,
                parent_geo.y() + (parent_geo.height() - self.height()) // 2
            )
        else:
            # Center on screen (fallback)
            screen = self.screen()
            if screen:
                scr_geo = screen.geometry()
                self.move(
                    scr_geo.x() + (scr_geo.width() - self.width()) // 2,
                    scr_geo.y() + (scr_geo.height() - self.height()) // 2
                )

    def apply_illum_style(self):
        """Set illumination toggle colors based on selection."""
        if self.selected_illum == ILLUM_GREEN:
            self.illum_toggle.setStyleSheet(
                f"background-color: {SEA_FOAM_GREEN}; color: white; font-size: 18px; font-weight: bold; border-radius: 8px;"
            )
        else:
            self.illum_toggle.setStyleSheet(
                f"background-color: {DEEP_RED}; color: white; font-size: 18px; font-weight: bold; border-radius: 8px;"
            )

    def toggle_illum(self):
        self.selected_illum = ILLUM_IR if self.selected_illum == ILLUM_GREEN else ILLUM_GREEN
        self.illum_toggle.setText(self.selected_illum)
        self.apply_illum_style()

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
        # illumination already tracked in self.selected_illum
        self.accept()
