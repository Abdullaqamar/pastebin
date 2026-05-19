import time
from threading import Lock, Thread

from core import (
    capture_and_upload_image,
    create_camera,
    get_ultrasound_data,
    submit_water_data,
)


TARGET_FPS = 1
FRAME_INTERVAL_SECONDS = 1 / TARGET_FPS
ULTRASOUND_TIMEOUT_SECONDS = 20


latest_depth = None
latest_depth_at = None
depth_lock = Lock()
running = True


def ultrasound_loop():
    global latest_depth, latest_depth_at

    while running:
        depth = get_ultrasound_data(timeout_seconds=ULTRASOUND_TIMEOUT_SECONDS)

        if depth and depth.get("distance") is not None:
            with depth_lock:
                latest_depth = depth["distance"]
                latest_depth_at = time.time()
            print(f"Updated ultrasound depth: {latest_depth} mm")
        else:
            print("Ultrasound still waiting for a valid reading")


def get_latest_depth():
    with depth_lock:
        return latest_depth, latest_depth_at

if __name__ == "__main__":
    picam2 = create_camera()
    ultrasound_thread = Thread(target=ultrasound_loop, daemon=True)
    ultrasound_thread.start()

    try:
        while True:
            started_at = time.time()

            image = capture_and_upload_image(picam2=picam2)
            depth, depth_at = get_latest_depth()

            if image:
                submit_water_data(image["url"], depth=depth)
            else:
                print("Failed to upload image")

            if depth_at:
                age = time.time() - depth_at
                print(f"Using ultrasound depth {depth} mm from {age:.1f}s ago")
            else:
                print("No ultrasound reading yet; sent camera frame without depth")

            elapsed = time.time() - started_at
            print(f"Frame cycle completed in {elapsed:.2f}s")
            time.sleep(max(0, FRAME_INTERVAL_SECONDS - elapsed))
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        running = False
        picam2.close()
