# motor_control.py
import time
import gpiod
from gpiod.line import Direction, Value, Bias

CHIP = "/dev/gpiochip0"
EN_PIN = 21
STEP_PIN = 20
DIR_PIN = 16
SWITCH_PIN = 26   # Hall effect sensor
OPTICAL_PIN = 19  # Optical sensor (ITR20001)

steps_per_60_deg = 800
calibration_offset_steps = 395
current_plate = 0

request = gpiod.request_lines(
    CHIP,
    consumer="seedling_imager",
    config={
        EN_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),  # EN low = enabled
        DIR_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),   # Clockwise
        STEP_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
        SWITCH_PIN: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP),
        OPTICAL_PIN: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP)
    }
)

def driver_enable():
    """Drive EN low (enable output stages)."""
    request.set_value(EN_PIN, Value.INACTIVE)

def driver_disable():
    """Drive EN high (disable output stages)."""
    request.set_value(EN_PIN, Value.ACTIVE)

def step_motor(steps, delay=0.0025, should_abort=None):
    """
    Step the motor a given number of steps. If should_abort() becomes True,
    exit early and return False; otherwise return True on normal completion.
    """
    for _ in range(steps):
        if callable(should_abort) and should_abort():
            return False
        request.set_value(STEP_PIN, Value.ACTIVE)
        time.sleep(delay)
        request.set_value(STEP_PIN, Value.INACTIVE)
        time.sleep(delay)
    return True

def home(timeout=60, status_callback=None, should_abort=None):
    """
    Homing routine: seek hall sensor, then align with optical sensor.
    Returns current plate index (1) on success, or None on failure/abort.

    - timeout: seconds before giving up
    - status_callback: optional callable(str) for UI logging
    - should_abort: optional callable() -> bool to request emergency stop
    """
    global current_plate
    start_time = time.time()
    if status_callback:
        status_callback("Starting homing... Fast rotation")
    print("DEBUG: Homing started", flush=True)

    # Rotate until hall sensor triggers
    while request.get_value(SWITCH_PIN) == Value.ACTIVE:
        if not step_motor(10, delay=0.001, should_abort=should_abort):
            if status_callback:
                status_callback("Homing aborted by user.")
            print("DEBUG: Homing aborted (fast rotation)", flush=True)
            return None
        if status_callback:
            status_callback("Searching for home...")
        if time.time() - start_time > timeout:
            if status_callback:
                status_callback("Homing timeout! Switch not detected.")
            print("DEBUG: Timeout occurred", flush=True)
            return None
        if callable(should_abort) and should_abort():
            if status_callback:
                status_callback("Homing aborted by user.")
            print("DEBUG: Homing aborted (timeout loop)", flush=True)
            return None

    if status_callback:
        status_callback("Hall sensor triggered! Checking optical sensor...")
    print("DEBUG: Hall sensor triggered", flush=True)

    # Count steps until optical sensor goes LOW
    steps_after_hall = 0
    while request.get_value(OPTICAL_PIN) == Value.ACTIVE:
        if not step_motor(1, delay=0.0025, should_abort=should_abort):
            if status_callback:
                status_callback("Homing aborted by user.")
            print("DEBUG: Homing aborted (optical seek)", flush=True)
            return None
        steps_after_hall += 1
        if steps_after_hall > 2000:
            msg = "Optical sensor NOT detected within limit"
            print(msg, flush=True)
            if status_callback:
                status_callback(msg)
            break
        if callable(should_abort) and should_abort():
            if status_callback:
                status_callback("Homing aborted by user.")
            print("DEBUG: Homing aborted (optical loop)", flush=True)
            return None

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
    # NOTE: callers should ensure driver is enabled before calling advance()
    if not step_motor(steps_per_60_deg):
        if status_callback:
            status_callback("Advance aborted.")
        print("DEBUG: Advance aborted", flush=True)
        return current_plate
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
            if not step_motor(1, delay=0.0025):
                if status_callback:
                    status_callback("Drift correction aborted.")
                print("DEBUG: Drift correction aborted", flush=True)
                break
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