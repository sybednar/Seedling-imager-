
# motor_control.py (replace calibrate() with home())
import time
import gpiod
from gpiod.line import Direction, Value, Bias

CHIP = "/dev/gpiochip0"
EN_PIN = 21
STEP_PIN = 20
DIR_PIN = 16
SWITCH_PIN = 26  # Hall effect sensor
OPTICAL_PIN = 19 # Optical sensor (ITR20001)

steps_per_60_deg = 800
calibration_offset_steps = 395
current_plate = 0

request = gpiod.request_lines(
    CHIP,
    consumer="seedling_imager",
    config={
        EN_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        DIR_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE), # Clockwise
        STEP_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        SWITCH_PIN: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP),
        OPTICAL_PIN: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP)
    }
)

def step_motor(steps, delay=0.0025):
    for _ in range(steps):
        request.set_value(STEP_PIN, Value.ACTIVE)
        time.sleep(delay)
        request.set_value(STEP_PIN, Value.INACTIVE)
        time.sleep(delay)

def home(timeout=60, status_callback=None):
    """
    Homing routine: seek hall sensor, then align with optical sensor.
    Returns current plate index (1) or None on failure.
    """
    global current_plate
    start_time = time.time()
    if status_callback:
        status_callback("Starting homing... Fast rotation")
    print("DEBUG: Homing started", flush=True)

    # Rotate until hall sensor triggers
    while request.get_value(SWITCH_PIN) == Value.ACTIVE:
        step_motor(10, delay=0.001)
        if status_callback:
            status_callback("Searching for home...")
        if time.time() - start_time > timeout:
            if status_callback:
                status_callback("Homing timeout! Switch not detected.")
            print("DEBUG: Timeout occurred", flush=True)
            return None

    if status_callback:
        status_callback("Hall sensor triggered! Checking optical sensor...")
    print("DEBUG: Hall sensor triggered", flush=True)

    # Count steps until optical sensor goes LOW
    steps_after_hall = 0
    while request.get_value(OPTICAL_PIN) == Value.ACTIVE:
        step_motor(1, delay=0.0025)
        steps_after_hall += 1
        if steps_after_hall > 2000:
            msg = "Optical sensor NOT detected within limit"
            print(msg, flush=True)
            if status_callback:
                status_callback(msg)
            break

    if request.get_value(OPTICAL_PIN) == Value.INACTIVE:
        msg = f"Optical sensor triggered after {steps_after_hall} steps"
        print(msg, flush=True)
        if status_callback:
            status_callback(msg)

    if status_callback:
        status_callback("Homing complete. Plate #1 aligned.")
    current_plate = 1
    return current_plate


def advance(status_callback=None):
    global current_plate
    step_motor(steps_per_60_deg)
    current_plate = (current_plate % 6) + 1
    msg = f"Moved to Plate #{current_plate}"
    if status_callback:
        status_callback(msg)
    print(f"DEBUG: {msg}", flush=True)

    # Drift correction when returning to Plate #1
    if current_plate == 1:
        if status_callback:
            status_callback("Checking optical sensor for drift correction...")
        print("DEBUG: Checking optical sensor for drift correction...", flush=True)

        extra_steps = 0
        while request.get_value(OPTICAL_PIN) == Value.ACTIVE:
            step_motor(1, delay=0.0025)
            extra_steps += 1
            if extra_steps > 500:  # safety limit
                msg = "Optical sensor not detected within limit!"
                if status_callback:
                    status_callback(msg)
                print(f"DEBUG: {msg}", flush=True)
                break

        # Reset plate count after correction
        current_plate = 1

        # Always report correction, even if 0 steps were needed
        if extra_steps == 0 and request.get_value(OPTICAL_PIN) == Value.INACTIVE:
            msg = "Drift correction: already aligned at Plate #1 (0 extra steps)"
        else:
            msg = f"Drift correction applied with {extra_steps} extra steps. Plate reset to #1"

        if status_callback:
            status_callback(msg)
        print(f"DEBUG: {msg}", flush=True)

    return current_plate


def goto_plate(target_plate, status_callback=None):
    """
    Move to the specified target plate (1..6) using repeated advance().
    """
    global current_plate
    target_plate = int(target_plate)
    if target_plate < 1 or target_plate > 6:
        if status_callback:
            status_callback(f"goto_plate: invalid target {target_plate}")
        return current_plate

    if status_callback:
        status_callback(f"Moving to Plate #{target_plate} from #{current_plate}")

    max_steps = 6
    while current_plate != target_plate and max_steps > 0:
        advance(status_callback=status_callback)
        max_steps -= 1
    return current_plate

