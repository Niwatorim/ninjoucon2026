import cv2
import numpy as np
import socket
import json
import os
import sys

from rfdetr import RFDETRKeypointPreview
import supervision as sv

# Add freemocap to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
freemocap_dir = os.path.join(parent_dir, 'freemocap')
if freemocap_dir not in sys.path:
    sys.path.insert(0, freemocap_dir)

from freemocap.core_processes.post_process_skeleton_data.enforce_rigid_bones import (
    calculate_bone_lengths_and_statistics,
    enforce_rigid_bones
)
from freemocap.data_layer.skeleton_models.segments import Segment

segment_connections = {
    "hip_width": Segment(proximal="12", distal="11"),
    "right_torso": Segment(proximal="12", distal="6"),
    "shoulder_width": Segment(proximal="6", distal="5"),
    "R_thigh": Segment(proximal="12", distal="14"),
    "R_calf": Segment(proximal="14", distal="16"),
    "L_thigh": Segment(proximal="11", distal="13"),
    "L_calf": Segment(proximal="13", distal="15"),
    "R_upper_arm": Segment(proximal="6", distal="8"),
    "R_forearm": Segment(proximal="8", distal="10"),
    "L_upper_arm": Segment(proximal="5", distal="7"),
    "L_forearm": Segment(proximal="7", distal="9"),
}

joint_hierarchy = {
    "12": ["11", "6", "14"], 
    "11": ["13"],             
    "6": ["5", "8"],       
    "5": ["7"],             
    "14": ["16"],             
    "13": ["15"],             
    "8": ["10"],             
    "7": ["9"],             
}

# COCO 17 Keypoint Edges
COCO_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),             # Face
    (5, 6), (5, 11), (6, 12), (11, 12),         # Torso
    (5, 7), (7, 9),                             # Left Arm
    (6, 8), (8, 10),                            # Right Arm
    (11, 13), (13, 15),                         # Left Leg
    (12, 14), (14, 16)                          # Right Leg
]

def draw_keypoints(frame, keypoints_obj):
    """
    Custom drawer to draw COCO keypoints and edges on the frame.
    """
    if not keypoints_obj or len(keypoints_obj) == 0:
        return frame
    
    xy = keypoints_obj.xy
    confidence = keypoints_obj.confidence if hasattr(keypoints_obj, 'confidence') else None

    for i in range(len(xy)):
        pts = xy[i]
        conf = confidence[i] if confidence is not None else np.ones(17)

        # Draw vertices
        for j in range(len(pts)):
            x, y = int(pts[j][0]), int(pts[j][1])
            if conf[j] > 0.5 and (x > 0 and y > 0):
                cv2.circle(frame, (x, y), 4, (0, 0, 255), -1)

        # Draw edges
        for edge in COCO_EDGES:
            pt1_idx, pt2_idx = edge
            x1, y1 = int(pts[pt1_idx][0]), int(pts[pt1_idx][1])
            x2, y2 = int(pts[pt2_idx][0]), int(pts[pt2_idx][1])

            valid_1 = conf[pt1_idx] > 0.5 and (x1 > 0 and y1 > 0)
            valid_2 = conf[pt2_idx] > 0.5 and (x2 > 0 and y2 > 0)

            if valid_1 and valid_2:
                cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    return frame

def load_calibration():
    # Load calibration from the parent directory
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "UNITY_TEST", "camera_parameters.json")
    if not os.path.exists(path):
        print(f"Error: Could not find {path}. Please run calibrate_cameras.py first.")
        sys.exit(1)
    with open(path, 'r') as f:
        data = json.load(f)
    return np.array(data["P1"]), np.array(data["P2"])

def triangulate_person(kp0_xy, kp1_xy, w, h, P1, P2, last_pts0, last_pts1):
    """
    kp0_xy, kp1_xy: arrays of shape (17, 2)
    last_pts0, last_pts1: dictionaries storing the last valid (x,y) for each point
    """
    pts0 = []
    pts1 = []
    
    # 17 keypoints for COCO
    for i in range(17):
        x0, y0 = kp0_xy[i][0], kp0_xy[i][1]
        x1, y1 = kp1_xy[i][0], kp1_xy[i][1]
        
        # Fallback to last valid point if RF-DETR outputs 0,0 (occluded/undetected)
        if x0 <= 0 or y0 <= 0:
            x0, y0 = last_pts0.get(i, (w/2, h/2))
        else:
            last_pts0[i] = (x0, y0)
            
        if x1 <= 0 or y1 <= 0:
            x1, y1 = last_pts1.get(i, (w/2, h/2))
        else:
            last_pts1[i] = (x1, y1)

        pts0.append([x0, y0])
        pts1.append([x1, y1])
        
    pts0 = np.array(pts0, dtype=np.float64).T
    pts1 = np.array(pts1, dtype=np.float64).T
    
    points_4d = cv2.triangulatePoints(P1, P2, pts0, pts1)
    points_3d = points_4d[:3, :] / points_4d[3, :]
    
    # Return dictionary mapping string index to [x, y, z]
    return {str(i): points_3d[:, i] for i in range(17)}

def get_segment(stabilized_points, p1_id, p2_id):
    p1 = stabilized_points.get(str(p1_id))
    p2 = stabilized_points.get(str(p2_id))
    
    if p1 is None or p2 is None:
        return None
        
    diff = p2 - p1
    norm = np.linalg.norm(diff)
    if norm > 1e-6:
        vec = diff / norm
        return {"x": float(vec[0]), "y": float(vec[1]), "z": float(vec[2])}
    return None

def match_people(kp_obj0, kp_obj1):
    """
    Matches people between two camera views.
    For simplicity, we sort by the X coordinate of the bounding box center or nose.
    A more robust matching algorithm (like epipolar distance) could be used here.
    """
    if not kp_obj0 or not kp_obj1 or len(kp_obj0) == 0 or len(kp_obj1) == 0:
        return []

    def get_centers(kp_obj):
        # We can use the mean X of the keypoints as a rough horizontal center
        centers = []
        for i in range(len(kp_obj.xy)):
            # Average X of valid keypoints
            valid_x = [pt[0] for pt in kp_obj.xy[i] if pt[0] > 0]
            if valid_x:
                centers.append(np.mean(valid_x))
            else:
                centers.append(0)
        return centers

    centers0 = get_centers(kp_obj0)
    centers1 = get_centers(kp_obj1)

    # Sort indices left-to-right
    indices0 = np.argsort(centers0)
    indices1 = np.argsort(centers1)

    matched_pairs = []
    # Match pairs based on horizontal ordering
    min_len = min(len(indices0), len(indices1))
    for i in range(min_len):
        idx0 = indices0[i]
        idx1 = indices1[i]
        matched_pairs.append((kp_obj0.xy[idx0], kp_obj1.xy[idx1]))

    return matched_pairs

def main():
    print("Loading calibration...")
    P1, P2 = load_calibration()

    print("Initializing RF-DETR Model...")
    model = RFDETRKeypointPreview()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unity_address = ("127.0.0.1", 5052)

    cap0 = cv2.VideoCapture(0)
    cap1 = cv2.VideoCapture(1)

    if not cap0.isOpened() or not cap1.isOpened():
        print("Error: Could not open both cameras.")
        # If testing with just one camera, you can duplicate cap0 for debugging, but triangulation will be wrong.
        # return

    print("Cameras opened. Starting stream...")

    calibrating = True
    calibration_frames_needed = 60
    calibration_history = []
    bone_statistics = None
    
    # Maintain state to prevent 0,0 outliers
    last_pts0 = {}
    last_pts1 = {}

    print("Please stand in a T-Pose for 2 seconds to calibrate!")

    while True:
        ret0, frame0 = cap0.read()
        ret1, frame1 = cap1.read()
        
        if not ret0 or not ret1:
            break

        h, w, _ = frame0.shape

        # Run prediction on both frames
        # Note: running sequential prediction might drop FPS. 
        # For production, consider multithreading these predictions like in live_multicam_freemocap.py
        kp0 = model.predict(frame0, threshold=0.5)
        kp1 = model.predict(frame1, threshold=0.5)

        # Match people across views
        matched_people = match_people(kp0, kp1)

        if len(matched_people) > 0:
            person0_xy, person1_xy = matched_people[0]
            points_3d = triangulate_person(person0_xy, person1_xy, w, h, P1, P2, last_pts0, last_pts1)

            current_points = {k: points_3d[k] for k in ["5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16"]}

            if calibrating:
                calibration_history.append(current_points)
                cv2.putText(frame0, f"Calibrating: {len(calibration_history)}/{calibration_frames_needed}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)
                
                if len(calibration_history) >= calibration_frames_needed:
                    formatted_history = {key: np.array([fd[key] for fd in calibration_history]) for key in current_points}
                    try:
                        bone_statistics = calculate_bone_lengths_and_statistics(formatted_history, segment_connections)
                        calibrating = False
                        print("Calibration Complete!")
                    except Exception as e:
                        print(f"Calibration Error: {e}")
            else:
                cv2.putText(frame0, "STEREO TRACKING ACTIVE (RF-DETR)", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                live_marker_data = {key: np.array([val]) for key, val in current_points.items()}
                
                try:
                    live_bone_stats = calculate_bone_lengths_and_statistics(live_marker_data, segment_connections)
                    for segment_name in live_bone_stats:
                        live_bone_stats[segment_name]["median"] = bone_statistics[segment_name]["median"]

                    rigid_live_data = enforce_rigid_bones(
                        marker_data=live_marker_data,
                        segment_connections=segment_connections,
                        bone_lengths_and_statistics=live_bone_stats,
                        joint_hierarchy=joint_hierarchy
                    )

                    stabilized_points = {key: rigid_live_data[key][0] for key in rigid_live_data}
                except Exception as e:
                    print(f"Rigid Bone Error: {e}")
                    continue

                # Spine calculation using stabilized points
                mid_hip = (stabilized_points["11"] + stabilized_points["12"]) / 2
                mid_shoulder = (stabilized_points["5"] + stabilized_points["6"]) / 2
                spine_diff = mid_shoulder - mid_hip
                spine_norm = np.linalg.norm(spine_diff)
                spine = (spine_diff / spine_norm).tolist() if spine_norm > 1e-6 else None

                segment_payload = {
                    "segments": {
                        "R_upper_arm": get_segment(stabilized_points, 6, 8),
                        "L_upper_arm": get_segment(stabilized_points, 5, 7),
                        "R_forearm": get_segment(stabilized_points, 8, 10),
                        "L_forearm": get_segment(stabilized_points, 7, 9),
                        "R_thigh": get_segment(stabilized_points, 12, 14),
                        "L_thigh": get_segment(stabilized_points, 11, 13),
                        "R_shin": get_segment(stabilized_points, 14, 16),
                        "L_shin": get_segment(stabilized_points, 13, 15),
                        "spine": {"x": float(spine[0]), "y": float(spine[1]), "z": float(spine[2])} if spine else None
                    }
                }
                
                segment_payload["segments"] = {k: v for k, v in segment_payload["segments"].items() if v is not None}
                # Send to Unity
                try:
                    sock.sendto(json.dumps(segment_payload).encode(), unity_address)
                except Exception as e:
                    print(f"UDP Send Error: {e}")

        # Draw 2D keypoints for visualization
        annotated_frame0 = draw_keypoints(frame0, kp0)
        annotated_frame1 = draw_keypoints(frame1, kp1)
        
        cv2.imshow('Camera 0', annotated_frame0)
        cv2.imshow('Camera 1', annotated_frame1)
        
        if cv2.waitKey(1) == ord('q'):
            break

    cap0.release()
    cap1.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
