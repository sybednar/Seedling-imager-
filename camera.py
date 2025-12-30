#camera.py (additons)
from picamera2 import Picamera2
from PySide6.QtGui import QImage
import cv2
import numpy as np
from pathlib import Path

picam = Picamera2()
config = picam.create_preview_configuration(main={"size": (640, 480)})  # Removed colour_space
picam.configure(config)
picam.set_controls({"AfMode": 2, "AwbEnable": True})

def start_camera():
    picam.start()

def stop_camera():
    picam.stop()

def get_frame():
    frame = picam.capture_array("main")
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = frame_rgb.shape
    return QImage(frame_rgb.data, w, h, QImage.Format_RGB888)


def save_image(path: str) -> bool:
    """
    Capture current frame and save to file (PNG/JPEG).
    Assumes camera.start_camera() has been called.
    """
    try:
        arr = picam.capture_array("main")   # typically RGB
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.imwrite(path, bgr)
    except Exception as e:
        print(f"save_image error: {e}", flush=True)
        return False
