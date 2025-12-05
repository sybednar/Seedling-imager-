#camera.py
from picamera2 import Picamera2
from PySide6.QtGui import QImage
import cv2
import numpy as np

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
