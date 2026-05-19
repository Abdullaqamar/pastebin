import os
import time
from datetime import datetime

import requests
import serial
from picamera2 import Picamera2
import RPi.GPIO as GPIO


UPLOAD_API_URL = "https://aiot.pipescanai.com/api/upload"
WATER_DATA_API_URL = "https://aiot.pipescanai.com/api/water-data"


def upload_image(file_path, api_url=UPLOAD_API_URL):
    try:
        with open(file_path, "rb") as image_file:
            file_name = os.path.basename(file_path)
            files = {
                "image": (file_name, image_file, "image/jpeg"),
            }
            response = requests.post(api_url, files=files, timeout=30)

        if response.status_code == 200:
            print("Image uploaded successfully")
            return response.json()

        print(f"Failed to upload image. Status code: {response.status_code}")
        print(response.text[:500])
        return None
    except Exception as error:
        print(f"Error uploading image: {error}")
        return None


def submit_water_data(image_url, depth=None, api_url=WATER_DATA_API_URL):
    try:
        data = {
            "image": image_url,
        }
        if depth is not None:
            data["depth"] = depth
        print(data)

        response = requests.post(
            api_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 200:
            print("Water data submitted successfully")
            return response.json()

        print(f"Failed to submit water data. Status code: {response.status_code}")
        print(response.text[:500])
        return None
    except Exception as error:
        print(f"Error submitting water data: {error}")
        return None


def create_camera():
    picam2 = Picamera2()
    config = picam2.create_still_configuration()
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    return picam2


def capture_and_upload_image(file_name="image.jpg", picam2=None):
    owns_camera = picam2 is None

    if owns_camera:
        picam2 = create_camera()

    try:
        picam2.capture_file(file_name)
        timestamp = int(datetime.now().timestamp() * 1000)
        print(f"Image saved as {file_name}")

        upload_result = upload_image(file_name)
        if upload_result and "url" in upload_result:
            return {"url": upload_result["url"], "timestamp": timestamp}

        return None
    finally:
        if owns_camera and picam2:
            picam2.close()


def get_ultrasound_data(port="/dev/ttyS0", timeout_seconds=None):
    GPIO.setmode(GPIO.BCM)
    power_pin = 2
    dev = None

    try:
        GPIO.setup(power_pin, GPIO.OUT)
        GPIO.output(power_pin, GPIO.HIGH)

        print(f"Powering on the sensor on port {port}")

        dev = serial.Serial(
            port=port,
            baudrate="9600",
            bytesize=8,
            stopbits=1,
            timeout=0.1,
        )

        started_at = time.time()

        while True:
            if timeout_seconds and time.time() - started_at > timeout_seconds:
                return {
                    "msg": "timeout",
                    "distance": None,
                    "unit": "mm",
                    "timestamp": int(datetime.now().timestamp() * 1000),
                }

            if dev.in_waiting <= 1:
                time.sleep(0.05)
                continue

            if dev.read(size=1) != b"\xff":
                continue

            h_byte = dev.read(size=1)
            l_byte = dev.read(size=1)
            dist = int.from_bytes(h_byte) * 256 + int.from_bytes(l_byte)

            if 0 < dist < 8000:
                payload = {
                    "msg": "success",
                    "distance": dist,
                    "unit": "mm",
                    "timestamp": int(datetime.now().timestamp() * 1000),
                }
                print(payload)
                return payload
    except PermissionError:
        print(
            f"Permission denied opening {port}. Add this user to the dialout group "
            "or run with sudo for a quick test."
        )
        return None
    except Exception as error:
        print(f"Error in UART communication: {error}")
        return None
    finally:
        if dev:
            dev.close()
        GPIO.cleanup()


if __name__ == "__main__":
    upload_result = upload_image("./test_image.png")

    if upload_result and "url" in upload_result:
        submit_water_data(upload_result["url"], depth=120)
