"""
check how to operate youtube API

check how to use mediapipe for hands

if arm move, move percentage of the bar
    - find total length of video, then use seekto to get to the point required


open palm -> seeking
fist -> stop seeking
thumbs up -> toggle pause
point right -> five seconds to the right
point left -> five seconds to the left

    
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles
from OneEuroFilter import OneEuroFilter
import time
import asyncio
import asyncio
import websockets
import json
import time

latest_seek_time = 0.0
action = None
is_seeking = False
mini_seeking = False
timestamp = None

#load time stamps:
with open("./keyposes/teacher_timestamps.json","r") as f:
    timestamps = json.dumps(f)

pose_id = 0


def draw_landmarks_on_image(rgb_image, detection_result):
  pose_landmarks_list = detection_result.pose_landmarks
  annotated_image = np.copy(rgb_image)

  pose_landmark_style = drawing_styles.get_default_pose_landmarks_style()
  pose_connection_style = drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=2)

  for pose_landmarks in pose_landmarks_list:
    drawing_utils.draw_landmarks(
        image=annotated_image,
        landmark_list=pose_landmarks,
        connections=vision.PoseLandmarksConnections.POSE_LANDMARKS,
        landmark_drawing_spec=pose_landmark_style,
        connection_drawing_spec=pose_connection_style)

  return annotated_image

class LandmarkSmoother:
    """
    1. define the filter transformation
    2. apply the transformation to each landmark

    1 pose has 33 landmarks, 1 landmark has 3 coordinates (x,y,z), so in total 99 filters
    """
    def __init__(self, freq=30.0, min_cutoff=1.0, beta=0.01):
        self.filters = {} # every coordinate has a unique filter value
        self.freq = freq
        self.min_cutoff = min_cutoff # decrease to reduce low-speed jitter
        self.beta = beta # increase to reduce high-speed lag

    def apply_to_world_landmarks(self, detection_result, timestamp_ms):
        t = timestamp_ms / 1000
        if not detection_result.pose_world_landmarks:
            return detection_result
        
        for p_idx, pose_landmarks in enumerate(detection_result.pose_world_landmarks):
            for lm_idx, landmark in enumerate(pose_landmarks):
                for coord in ['x', 'y', 'z']:
                    key = (p_idx, lm_idx, coord, 'world')
                    if key not in self.filters:
                        self.filters[key] = OneEuroFilter(freq=self.freq, mincutoff=self.min_cutoff, beta=self.beta)
                    setattr(landmark, coord, self.filters[key](getattr(landmark, coord), t))
        return detection_result

    def apply_to_landmarks(self, detection_result, timestamp_ms): # the parameters for the OneEuroFilter library
        t = timestamp_ms / 1000 # change to seconds
        if not detection_result.pose_landmarks:
            return detection_result
        
        for p_idx, pose_landmarks in enumerate(detection_result.pose_landmarks):
            for lm_idx, landmark in enumerate(pose_landmarks):
                x_key = (p_idx, lm_idx, 'x') # tuple as the key
                if x_key not in self.filters:
                    self.filters[x_key] = OneEuroFilter(freq=self.freq, mincutoff=self.min_cutoff, beta=self.beta) # initiated a unique filter as the value
                    landmark.x = self.filters[x_key](landmark.x, t) # pass the values to the filter, just like in the docs' minimal example
                else: # if the filter is already created, just pass the values directly
                    landmark.x = self.filters[x_key](landmark.x, t)
                
                y_key = (p_idx, lm_idx, 'y') # tuple as the key
                if y_key not in self.filters:
                    self.filters[y_key] = OneEuroFilter(freq=self.freq, mincutoff=self.min_cutoff, beta=self.beta) # initiated a unique filter as the value
                    landmark.y = self.filters[y_key](landmark.y, t) # pass the values to the filter, just like in the docs' minimal example
                else: # if the filter is already created, just pass the values directly
                    landmark.y = self.filters[y_key](landmark.y, t)
                
                z_key = (p_idx, lm_idx, 'z') # tuple as the key
                if z_key not in self.filters:
                    self.filters[z_key] = OneEuroFilter(freq=self.freq, mincutoff=self.min_cutoff, beta=self.beta) # initiated a unique filter as the value
                    landmark.z = self.filters[z_key](landmark.z, t) # pass the values to the filter, just like in the docs' minimal example
                else: # if the filter is already created, just pass the values directly
                    landmark.z = self.filters[z_key](landmark.z, t)
        return detection_result

def find_arm(detection_result):
    """
    Find angles between arms and make percentage between 0 -> 180 degrees
    """
    if not detection_result.pose_landmarks:
        return None
    
    pose_landmarks_list = detection_result.pose_landmarks[0]
    elbow = np.array([pose_landmarks_list[14].x,pose_landmarks_list[14].y])
    wrist = np.array([pose_landmarks_list[16].x,pose_landmarks_list[16].y])

    arm_vector = wrist - elbow
    horizontal_vector = np.array([1, 0])
    unit_arm = arm_vector / np.linalg.norm(arm_vector)
    unit_horiz = horizontal_vector / np.linalg.norm(horizontal_vector)    
    dot_product = np.clip(np.dot(unit_arm, unit_horiz), -1.0, 1.0)
    angle = np.rad2deg(np.arccos(dot_product))
    return angle

def find_fingy(hand_detection_result):
    if not hand_detection_result.hand_landmarks:
        return None
        
    landmarks_list =  hand_detection_result.hand_landmarks[0]
    elbow = np.array([landmarks_list[5].x,landmarks_list[5].y])
    wrist = np.array([landmarks_list[8].x,landmarks_list[8].y])

    arm_vector = wrist - elbow
    horizontal_vector = np.array([1, 0])
    unit_arm = arm_vector / np.linalg.norm(arm_vector)
    unit_horiz = horizontal_vector / np.linalg.norm(horizontal_vector)    
    dot_product = np.clip(np.dot(unit_arm, unit_horiz), -1.0, 1.0)
    angle = np.rad2deg(np.arccos(dot_product))
    return angle

async def stream_mini(websocket):
    global latest_seek_time
    global action
    global is_seeking
    global mini_seeking
    print("Chrome connected")
    pause = False
    command = None
    prev_action = None 
    try:
        while True:
            await asyncio.sleep(0.05) 
            
            command = None

            # Only process action if it just changed
            if action != prev_action:
                # Changed gesture names to exactly match MediaPipe output
                if action == "Thumb_Up":
                    pause = not pause
                    if pause:
                        command = "pause"
                    else: 
                        command = "play"
                    
                elif action == "Closed_Fist" and is_seeking == False:
                    is_seeking = True
                elif action == "Open_Palm" and is_seeking == True: # Assuming "Open_Palm" stops the seek mode
                    is_seeking = False
                elif action == "Victory":
                    mini_seeking = not mini_seeking
                    if mini_seeking:
                        command = "mini_seek"
                    else:
                        command = None
                    
            
            prev_action = action

            if is_seeking == True:
                command = "seek"
            elif mini_seeking == True:
                command = "mini_seek"
            

            payload = {
                "action":command,
                "timestamp":time.time(),
                "seek_time":latest_seek_time
            }

            await websocket.send(json.dumps(payload))
            
    except websockets.exceptions.ConnectionClosedOK:
        print("Chrome extension disconnected")

async def stream(websocket):
    """ For the main """
    global action
    global timestamp
    global pose_id
    global timestamps
    print("Chrome connected")
    pause = False
    command = None
    prev_action = None 
    try:
        while True:
            await asyncio.sleep(0.05) 
            
            command = None

            # Only process action if it just changed
            if action != prev_action:                
                if action == "play_until":
                    command = "play_until"
                    timestamp = timestamps[pose_id]
            payload = {
                "action":command,
                "timestamp":time.time(),
                "target_time":timestamp
            }
            await websocket.send(json.dumps(payload))
    except websockets.exceptions.ConnectionClosedOK:
        print("Chrome extension disconnected")


async def process_info():
    base_options = python.BaseOptions(model_asset_path='./gesture_recognizer.task')
    options = vision.GestureRecognizerOptions(base_options=base_options,running_mode=vision.RunningMode.VIDEO)
    recognizer = vision.GestureRecognizer.create_from_options(options)
    global action
    global latest_seek_time
    global is_seeking
    global mini_seeking

    # load the task (model)
    model_path = "../pose_landmarker_full.task"
    BaseOptions = python.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(
        base_options = BaseOptions(model_asset_path=model_path),
        running_mode = VisionRunningMode.VIDEO
        )

    cap = cv2.VideoCapture(0)
    start_time = time.time()
    smoother = LandmarkSmoother(min_cutoff=0.05, beta=0.80)

    with PoseLandmarker.create_from_options(options) as detector:
        with recognizer:
            while cap.isOpened():
                ret, frame = cap.read() # capture frame by frame, ret is return, will return True if frame is read
                if not ret:
                    print("exiting..") # ret will turn false when the video finished 
                    break
                if len(frame.shape) == 2:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB) # if the image is 2D (grayscale), convert GRAY to RGB
                else:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # if the image is 3D (standard color), convert BGR to RGB

                mediapipe_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame) # convert np array to mediapipe Image object
                current_time = time.time()
                timestamp_ms = int((current_time - start_time) * 1000)
                timestamp_ms += 1

                try:
                    hand_detection_result = recognizer.recognize_for_video(mediapipe_frame,timestamp_ms) # tracks landmarks across time
                    if hand_detection_result.gestures:
                        action = hand_detection_result.gestures[0][0].category_name
                        print(action)
                    else:
                        action = None

                    if is_seeking:
                        detection_result = detector.detect_for_video(mediapipe_frame, timestamp_ms)
                        filtered_result = smoother.apply_to_landmarks(detection_result, timestamp_ms)
                        annotated_frame = draw_landmarks_on_image(mediapipe_frame.numpy_view(), filtered_result)
                        bgr_annotated_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR)

                        angle = find_arm(filtered_result)
                        if angle is not None:
                            latest_seek_time = abs(angle/180)
                    
                    if mini_seeking:
                        angle = find_fingy(hand_detection_result)
                        if angle is not None:
                            latest_seek_time = (abs(angle/180)-0.5) * 5
                        else:
                            latest_seek_time = 0.0
                        


                except Exception as e:
                    print("Error as ", e)
                
                if cv2.waitKey(1) == ord('q'): # waitKey() receives int(delay)
                    break
                await asyncio.sleep(0.01)
    cap.release()
    cv2.destroyAllWindows()

async def main():
    server = await websockets.serve(stream_mini,"localhost",8765)
    await process_info()
    server.close()
    await server.wait_closed()    

if __name__ == "__main__":
    asyncio.run(main())