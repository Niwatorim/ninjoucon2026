import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import time
import asyncio
import time

base_options = python.BaseOptions(model_asset_path='./gesture_recognizer.task')
options = vision.GestureRecognizerOptions(base_options=base_options,running_mode=vision.RunningMode.VIDEO)
recognizer = vision.GestureRecognizer.create_from_options(options)

with recognizer:
    cap = cv2.VideoCapture(0)
    start_time = time.time()
    last_timestamp_ms = -1


    while cap.isOpened():
        ret, frame = cap.read() 
        if not ret:
            print("exiting..") 
            continue

        timestamp_ms = int((time.time() - start_time) * 1000)
        if timestamp_ms <= last_timestamp_ms:
            timestamp_ms = last_timestamp_ms + 1
        last_timestamp_ms = timestamp_ms

        if len(frame.shape) == 2:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB) # if the image is 2D (grayscale), convert GRAY to RGB
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # if the image is 3D (standard color), convert BGR to RGB

        mediapipe_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame) # convert np array to mediapipe Image object

        try: 
            detection_result = recognizer.recognize_for_video(mediapipe_frame,timestamp_ms) # tracks landmarks across time
            if detection_result.gestures:
                action = detection_result.gestures[0][0].category_name

        except Exception as e:
                print("Error as ", e)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Exiting...")
            break

cap.release()
cv2.destroyAllWindows()