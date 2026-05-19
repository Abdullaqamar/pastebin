import requests
from picamera2 import Picamera2
from datetime import datetime
import time
import serial
import RPi.GPIO as GPIO
import os

def upload_image(file_path, api_url="https://aiot.pipescanai.com/api/upload"):
    """
    Upload an image file to the specified API endpoint
    
    Args:
        file_path (str): Path to the image file to upload
        api_url (str): URL of the upload API endpoint
        
    Returns:
        dict: Response from the server containing uploaded image URL
    """
    try:
        with open(file_path, 'rb') as image_file:
            file_name = os.path.basename(file_path)
            form_data = {
                'image': (file_name, image_file, 'image/jpeg')
            }

            # Send POST request to upload the image
            response = requests.post(api_url, files=form_data, timeout=30)
        
        if response.status_code == 200:
            print("Image uploaded successfully")
            return response.json()
        else:
            print(f"Failed to upload image. Status code: {response.status_code}")
            print(response.text[:500])
            return None
            
    except Exception as e:
        print(e)
        print(f"Error uploading image: {str(e)}")
        return None

def submit_water_data(image_url, depth, api_url="https://aiot.pipescanai.com/api/water-data"):
    """
    Submit water data including image URL and depth measurement
    
    Args:
        image_url (str): URL of the uploaded image
        depth (float): Water depth measurement
        api_url (str): URL of the water data API endpoint
    """
    try:
        data = {
            'image': image_url,
            'depth': depth
        }

        print(data)
        
        response = requests.post(
            api_url,
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("Water data submitted successfully")
            return response.json()
        else:
            print(f"Failed to submit water data. Status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error submitting water data: {str(e)}")
        return None

def capture_and_upload_image(file_name="image.jpg", picam2=None):
    owns_camera = picam2 is None

    if owns_camera:
        # Initialize camera
        picam2 = Picamera2()

        # Configure the camera
        config = picam2.create_still_configuration()
        picam2.configure(config)

        # Start the camera
        picam2.start()

        # Wait for camera to initialize
        time.sleep(2)

    # Capture and save the image
    picam2.capture_file(file_name)
    
    dt = int(datetime.now().timestamp()*1000)

    if owns_camera:
        # Close the camera
        picam2.close()
    
    print(f"Image saved as {file_name}")
    
    # Upload image to API endpoint
    try:
        upload_result = upload_image(file_name)
        if upload_result and 'url' in upload_result:
            return {"url": upload_result['url'], "timestamp": dt}
    except Exception as e:
        print(f"Error uploading image: {str(e)}")

def get_ultrasound_data(port="/dev/ttyS0", timeout_seconds=None):
    # Set up GPIO mode
    GPIO.setmode(GPIO.BCM)
    
    dev = None  # Initialize dev to None

    try:

        POWER_PIN = 2

        GPIO.cleanup()

        # Power on the sensor
        GPIO.setup(POWER_PIN, GPIO.OUT)
        GPIO.output(POWER_PIN, GPIO.HIGH)

        print(f"Powering on the sensor on port {port}")

        dev = serial.Serial(
            # port="/dev/tty.usbserial-B003A43F",
            port=port,
            baudrate="9600",
            bytesize=8,
            stopbits=1
        )

        payload = {}

        started_at = time.time()

        while True:
            if timeout_seconds and time.time() - started_at > timeout_seconds:
                dt = int(datetime.now().timestamp()*1000)
                payload = {
                    "msg": "timeout",
                    "distance": None,
                    "unit": "mm",
                    "timestamp": dt,
                }
                break

            if dev.in_waiting <= 1:
                print(f"Waiting for data on port {port}")
                time.sleep(0.1)
                pass
            elif dev.read(size=1) == b'\xff':
                hByte = dev.read(size=1)
                lByte = dev.read(size=1)
                dist = int.from_bytes(hByte) * 256 + int.from_bytes(lByte)

                # if dist is 0, then the sensor is not working, get the data again
                if dist > 0 and dist < 8000:
                    dt = int(datetime.now().timestamp()*1000)
                    payload = {"msg": "success", "distance": dist,"unit": "mm", "timestamp": dt}
                    break

        GPIO.cleanup()

        # clear queue
        dev.close()

        return payload

    except Exception as e:
        print(f"Error in UART communication: {e}")

if __name__ == "__main__":
    # Example usage
    image_path = "./test_image.png"
    
    # Upload image
    upload_result = upload_image(image_path)
    
    if upload_result and 'url' in upload_result:
        # Submit water data with image URL
        submit_water_data(upload_result['url'], depth=120)
