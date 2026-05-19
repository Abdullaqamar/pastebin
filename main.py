import time

from core import (
    capture_and_upload_image,
    create_camera,
    get_ultrasound_data,
    submit_water_data,
)


TARGET_FPS = 1
FRAME_INTERVAL_SECONDS = 1 / TARGET_FPS

if __name__ == "__main__":
    picam2 = create_camera()

    try:
        while True:
            started_at = time.time()

            image = capture_and_upload_image(picam2=picam2)
            depth = get_ultrasound_data(timeout_seconds=0.8)

            if image and depth and depth.get("distance") is not None:
                submit_water_data(image["url"], depth=depth["distance"])
            elif not image:
                print("Failed to upload image")
            else:
                print("Failed to read ultrasound data")

            elapsed = time.time() - started_at
            print(f"Frame cycle completed in {elapsed:.2f}s")
            time.sleep(max(0, FRAME_INTERVAL_SECONDS - elapsed))
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        picam2.close()
