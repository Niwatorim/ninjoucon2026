import os
import json
import time
import threading
import socket
import sys
import numpy as np
import mediapipe as mp
import cv2 as cv
from scipy import linalg

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles
from utilities.video_mediapipeline import human_analysis_segmentation, vect_to_dict, quat_to_dict, LandmarkSmoother, draw_landmarks_on_image
from utilities.mediapipeline import MedaiPipeline

class MockLandmark:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = 1.0

# Load calibration data and build projection matrices
calib_path = os.path.join(os.path.dirname(__file__), "camera_parameters.json")
try:
    with open(calib_path, 'r') as f:
        calib_data = json.load(f)
    mtx0 = np.array(calib_data['mtx0'])
    dist0 = np.array(calib_data['dist0'])
    mtx1 = np.array(calib_data['mtx1'])
    dist1 = np.array(calib_data['dist1'])
    R = np.array(calib_data['R'])
    T = np.array(calib_data['T'])
except FileNotFoundError:
    print(f"Error: Could not find {calib_path}. Have you run calibration.py yet?")
    exit(1)

# Build projection matrices from intrinsics + extrinsics
P1 = mtx0 @ np.hstack([np.eye(3), np.zeros((3, 1))])
P2 = mtx1 @ np.hstack([R, T])

def DLT(P1, P2, point1, point2):
    A = [point1[1]*P1[2,:] - P1[1,:], #camera 1
        P1[0,:] - point1[0]*P1[2,:],
        point2[1]*P2[2,:] - P2[1,:], #camera 2
        P2[0,:] - point2[0]*P2[2,:],
        ]
    A = np.array(A).reshape((4,4))
    B = A.transpose() @ A
    U, s, Vh = linalg.svd(B, full_matrices=False)
    return Vh[3,0:3] / Vh[3,3]

def process(frame0, frame1, start_time, detector0, detector1, smoother0, smoother1):
    frame0_rgb = cv.cvtColor(frame0, cv.COLOR_BGR2RGB)
    frame1_rgb = cv.cvtColor(frame1, cv.COLOR_BGR2RGB)
    
    mp_image0 = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame0_rgb)
    mp_image1 = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame1_rgb)
    
    current_time = time.time()
    timestamp_ms = int((current_time - start_time) * 1000)
    # Ensure strictly monotonically increasing timestamps
    if not hasattr(process, "last_ts"): process.last_ts = -1
    if timestamp_ms <= process.last_ts: timestamp_ms = process.last_ts + 1
    process.last_ts = timestamp_ms

    res0 = detector0.detect_for_video(mp_image0, timestamp_ms)
    res1 = detector1.detect_for_video(mp_image1, timestamp_ms)
    
    filt0 = smoother0.apply_to_landmarks(res0, timestamp_ms)
    filt1 = smoother1.apply_to_landmarks(res1, timestamp_ms)
    
    h0, w0 = frame0.shape[:2]
    h1, w1 = frame1.shape[:2]

    frame0_keypoints = []
    frame1_keypoints = []

    if filt0.pose_landmarks and filt1.pose_landmarks:
        for lm in filt0.pose_landmarks[0]:
            frame0_keypoints.append([lm.x * w0, lm.y * h0])
            
        for lm in filt1.pose_landmarks[0]:
            frame1_keypoints.append([lm.x * w1, lm.y * h1])
            
        # Draw on frames
        annotated0 = draw_landmarks_on_image(frame0_rgb, filt0)
        out_frame0 = cv.cvtColor(annotated0, cv.COLOR_RGB2BGR)
        
        annotated1 = draw_landmarks_on_image(frame1_rgb, filt1)
        out_frame1 = cv.cvtColor(annotated1, cv.COLOR_RGB2BGR)
    else:
        out_frame0 = frame0.copy()
        out_frame1 = frame1.copy()
        
    points_3d = []
    if len(frame0_keypoints) > 0 and len(frame0_keypoints) == len(frame1_keypoints):
        kps0 = np.array(frame0_keypoints, dtype=np.float64).reshape(-1, 1, 2)
        kps1 = np.array(frame1_keypoints, dtype=np.float64).reshape(-1, 1, 2)

        kps0_undist = cv.undistortPoints(kps0, mtx0, dist0, P=mtx0)
        kps1_undist = cv.undistortPoints(kps1, mtx1, dist1, P=mtx1)

        for pt0, pt1 in zip(kps0_undist, kps1_undist):
            p3d = DLT(P1, P2, pt0[0], pt1[0])
            points_3d.append(p3d.tolist())

    return points_3d, out_frame0, out_frame1

def capture_thread(cap, frame_list):
    while cap.isOpened():
        ret, frame = cap.read()
        if ret:
            frame_list[0] = frame

def angles(poses:list):
    pose_dict ={}
    for i,k in enumerate(poses):
        pose_dict[i] = k
    
    #normalize
    mid_hip = (pose_dict[24] + pose_dict[23])/2
    mid_shoulder = (pose_dict[12]+pose_dict[11])/2
    spine = mid_shoulder - mid_hip
    spine_angle = np.arctan2(spine[1], spine[0])
    target_angle = np.pi/2
    rotation_needed = target_angle-spine_angle
    cos_a, sin_a = np.cos(rotation_needed),np.sin(rotation_needed)
    
    rot = np.array([ 
        [cos_a, -sin_a, 0],
        [sin_a,  cos_a, 0],
        [0,      0,     1]
    ])
    centered = {k: v - mid_hip for k,v in pose_dict.items()}
    rotated = {k: rot @ v for k,v in centered.items()}

    def segment(n,a,b):
        difference = n[b] - n[a]
        norm = np.linalg.norm(difference)
        if norm > 0.00000001:
            return (difference/norm).tolist()
        return None
    
    n = rotated
    return {
        "R_upper_arm":  segment(n, 12, 14),
        "L_upper_arm":  segment(n, 11, 13),
        "R_forearm":    segment(n, 14, 16),
        "L_forearm":    segment(n, 13, 15),
        "R_thigh":  segment(n, 24, 26),
        "L_thigh":  segment(n, 23, 25),
        "R_shin":  segment(n, 26, 28),
        "L_shin":  segment(n, 25, 27),
    }
    


def main():
    pipeline = MedaiPipeline()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ("127.0.0.1", 5052)

    cap0 = cv.VideoCapture(0)
    cap1 = cv.VideoCapture(1)

    if not cap0.isOpened() or not cap1.isOpened():
        print("Error opening cameras")
        return
        
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pose_landmarker_full.task"))
    BaseOptions = python.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(
        base_options = BaseOptions(model_asset_path=model_path),
        running_mode = VisionRunningMode.VIDEO
    )
    
        #add pose marker
    with PoseLandmarker.create_from_options(options) as detector0, \
         PoseLandmarker.create_from_options(options) as detector1:
         
        smoother0 = LandmarkSmoother(min_cutoff=0.05, beta=0.80)
        smoother1 = LandmarkSmoother(min_cutoff=0.05, beta=0.80)

        frame0 = [None]
        frame1 = [None]
        t0 = threading.Thread(target=capture_thread, args=(cap0, frame0), daemon=True)
        t1 = threading.Thread(target=capture_thread, args=(cap1, frame1), daemon=True)
        t0.start()
        t1.start()

        print("Live tracking started. Press 'q' to quit and save recording. (Will auto-stop after 15 seconds)")
        
        recording = []
        start_time = time.time()

        while True:
            # --- if want 15 sec thingy ---
            # if time.time() - start_time > 15:
            #     print("15 seconds reached! Stopping automatically.")
            #     break

            if frame0[0] is None or frame1[0] is None:
                continue

            f0 = frame0[0].copy()
            f1 = frame1[0].copy()

            points_3d, out_frame0, out_frame1 = process(f0, f1, start_time, detector0, detector1, smoother0, smoother1)

            if points_3d:
                recording.append(points_3d)

                # Reuse the Unity formatting logic
                mock_pose = [MockLandmark(pt[0], pt[1], pt[2]) for pt in points_3d]
                try:
                    # segments = human_analysis_segmentation(mock_pose, normalize=False)
                    segments = angles(mock_pose)

                    payload = {
                        "segments": {k: quat_to_dict(v) if k == "head_tilt" else vect_to_dict(v) 
                                     for k, v in segments.items() if v is not None}
                    }

                    sock.sendto(json.dumps(payload).encode(), server_address)

                except Exception as e:
                    print(f"UDP send error: {e}")

            cv.imshow("Camera 0", out_frame0)
            cv.imshow("Camera 1", out_frame1)
            if cv.waitKey(1) & 0xFF == ord('q'):
                break

    cap0.release()
    cap1.release()
    cv.destroyAllWindows()
    sock.close()
    
    # Save recording
    if recording:
        out_file = os.path.join(os.path.dirname(__file__), "pose_recording.json")
        with open(out_file, 'w') as f:
            json.dump(recording, f, indent=4)
        print(f"Recording saved to {out_file} with {len(recording)} frames.")
    else:
        print("No valid frames recorded to save.")

if __name__ == "__main__":
    main()
