import json
import base64
import time
from utilities.mediapipeline import MedaiPipeline, human
from matplotlib import pyplot as plt
import numpy as np
import os
import cv2
import socket
from utilities.video_mediapipeline import human_analysis_segmentation, vect_to_dict, quat_to_dict
import websockets
from utilities.dtw_scoring import score_transition, format_score_display
from utilities.handrecognizer import HandRecognizer
import time

MATCH_THRESHOLD = 16.0
NEAR_MATCH_THRESHOLD = 24.0
REQUIRED_HOLD_FRAMES = 8
JOINT_DEADZONE = 7.0
SCORE_EMA_ALPHA = 0.35
OPENCV_FRAME_FPS = 10
OPENCV_FRAME_INTERVAL = 1.0 / OPENCV_FRAME_FPS
OPENCV_FRAME_MAX_WIDTH = 720
OPENCV_FRAME_JPEG_QUALITY = 60


def encode_opencv_frame(frame):
    if frame is None:
        return None

    height, width = frame.shape[:2]
    frame_to_send = frame
    if width > OPENCV_FRAME_MAX_WIDTH:
        scale = OPENCV_FRAME_MAX_WIDTH / width
        frame_to_send = cv2.resize(
            frame,
            (OPENCV_FRAME_MAX_WIDTH, int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    success, encoded = cv2.imencode(
        ".jpg",
        frame_to_send,
        [int(cv2.IMWRITE_JPEG_QUALITY), OPENCV_FRAME_JPEG_QUALITY],
    )
    if not success:
        return None

    return base64.b64encode(encoded.tobytes()).decode("ascii")


async def send_opencv_overlay_frame(websocket, frame):
    encoded_frame = encode_opencv_frame(frame)
    if not encoded_frame:
        return

    await websocket.send(json.dumps({
        "type": "OPENCV_FRAME",
        "image": encoded_frame,
        "timestamp": time.time(),
    }))


def calculate_pose_match_score(target_angles, student_angles, joint_weights):
    weighted_error = 0.0
    total_weight = 0.0
    joint_errors = []

    for joint, target_angle in target_angles.items():
        student_angle = student_angles.get(joint)
        if target_angle is None or student_angle is None:
            continue

        raw_diff = abs(target_angle - student_angle)
        adjusted_diff = 0.0 if raw_diff < JOINT_DEADZONE else raw_diff
        weight = joint_weights.get(joint, 1.0)

        weighted_error += adjusted_diff * weight
        total_weight += weight
        joint_errors.append((joint, raw_diff))

    if total_weight == 0.0:
        return None, []

    joint_errors.sort(key=lambda item: item[1], reverse=True)
    return weighted_error / total_weight, joint_errors[:2]


def update_hold_progress(smoothed_score, match_hold_frames):
    if smoothed_score < MATCH_THRESHOLD:
        return match_hold_frames + 1, True
    if smoothed_score < NEAR_MATCH_THRESHOLD:
        return max(match_hold_frames - 1, 0), False
    return max(match_hold_frames - 3, 0), False

pose_id = 0
action = None
state = None

import asyncio
async def interactive_training_session(websocket, timestamps:dict, video_name:str= "video",checkpoint_poses:int=5, student_camera=0):
    global action
    global pose_id
    global timestamp
    global state

    pipeline = MedaiPipeline(enable_ble=True, ema_alpha=0.65)
    session_record = {}
    hand_recognizer = HandRecognizer()
    


    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    segment_address = ("127.0.0.1", 5052)    #  RigManager.cs (drives avatar)
    correction_address = ("127.0.0.1", 5053)  #  Spawner.cs (correction arrows)
    
    # 1. Load database
    try:
        with open("./keyposes/teacher_keyposes.json", "r") as f:
            stored_poses = json.load(f)
    except FileNotFoundError:
        print("Error: teacher_keyposes.json not found")
        return


    teacher_trajectories = {}
    try:
        with open("./keyposes/teacher_trajectories.json", "r") as f:
            teacher_trajectories = json.load(f)
        print(f"Loaded {len(teacher_trajectories)} teacher trajectories for DTW scoring")
    except FileNotFoundError:
        print("Warning: teacher_trajectories.json not found — DTW scoring disabled")

    last_dtw_score = None  # Store last DTW score for display
    student_transition_poses = []  # Record student poses during PLAYING state


    target_angles_db = {}
    target_normalized_db = {}

    for key, pose_dict in stored_poses.items():
        angles, _ = pipeline.human_analysis(pose_dict)
        target_angles_db[key] = angles
        normalized_pts, _ = pipeline.normalize_pose(pose_dict)
        target_normalized_db[key] = normalized_pts

    pose_id = 0
    # Make sure to handle if it's string key or int index
    timestamp = timestamps.get(str(pose_id), 0.0) 
    
    # Initial Seek & Pause
    await websocket.send(json.dumps({"action": "seek", "seek_time": timestamp}))
    await websocket.send(json.dumps({"action": "pause"}))
    state = "PAUSED"

    current_pose_sequence=[]
    current_target_pose = str(pose_id)

    cap_student = cv2.VideoCapture(student_camera)
    if not cap_student.isOpened():
        print("Error: Could not open video streams.")
        return
        
    match_hold_frames = 0
    score_ema = None
    skip_pose = False
    last_overlay_frame_sent = 0.0
    checkpoint_waiting_paused = False

    while True:
        ret,student_frame = cap_student.read()

        if not ret:
            break
        

        display_student = student_frame # Initialize by default
        
        #paused state, where we have checking the users logic
        if state == "PAUSED" or state == "CHECKPOINT":
            #mark frame
            annotated_student, pose, world_pose, smoothed_world = pipeline.mark_frame(student_frame)
            action = hand_recognizer.mark_frame(student_frame, int(time.time() * 1000))
            display_student = annotated_student if pose else student_frame

            if world_pose is not None and smoothed_world is not None:
                try:
                    segments = human_analysis_segmentation(world_pose)
                    segment_payload = {
                        "segments": {k: quat_to_dict(v) if k == "head_tilt" else vect_to_dict(v)
                                    for k, v in segments.items() if v is not None}
                    }
                    sock.sendto(json.dumps(segment_payload).encode(), segment_address)
                except Exception as e:
                    print(f"Segment send error: {e}")

                current_pose_sequence.append(pipeline.serialize_pose(smoothed_world))
                student_angles, _ = pipeline.human_analysis(smoothed_world)
                student_normalized, student_transform = pipeline.normalize_pose(smoothed_world)
                student_screen_normalized, student_screen_transform = pipeline.normalize_pose(pose)

                target_angles = target_angles_db.get(current_target_pose)
                target_normalized = target_normalized_db.get(current_target_pose)

                if target_angles:
                    average_score, worst_joints = calculate_pose_match_score(
                        target_angles,
                        student_angles,
                        pipeline.joint_weights,
                    )

                    if average_score is not None:
                        if score_ema is None:
                            score_ema = average_score
                        else:
                            score_ema = (
                                SCORE_EMA_ALPHA * average_score
                                + (1.0 - SCORE_EMA_ALPHA) * score_ema
                            )
                        
                        # Draw Euclidean Arrows
                        correction_landmarks = [
                            pipeline.joint_bone[joint]["point"]
                            for joint, _ in worst_joints
                            if joint in pipeline.joint_bone
                        ]
                        corrections = pipeline.euclidean_distance(
                            teacher=target_normalized, #type: ignore
                            student=student_normalized, 
                            student_params=student_transform, 
                            image=display_student,
                            render_pose=pose,
                            render_student=student_screen_normalized,
                            render_params=student_screen_transform,
                            allowed_landmarks=correction_landmarks,
                            max_corrections=2,
                        )
                        display_student = pipeline.draw_arrow(display_student, corrections)

                        correction_payload = pipeline.corrections_to_unity_format(corrections)
                        if any(v is not None for v in correction_payload["corrections"].values()):
                            try:
                                sock.sendto(json.dumps(correction_payload).encode(), correction_address)
                            except Exception as e:
                                print(f"Correction send error: {e}")
                        
                        # Match Logic
                        match_hold_frames, is_match = update_hold_progress(score_ema, match_hold_frames)
                        if is_match:
                            cv2.putText(display_student, f"HOLD IT! ({match_hold_frames}/{REQUIRED_HOLD_FRAMES}) Error: {score_ema:.1f}",
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3, cv2.LINE_AA)
                            
                            if match_hold_frames >= REQUIRED_HOLD_FRAMES:
                                print(f"Pose {current_target_pose} matched! Resuming video...")
                                pose_is_matched = True
                                session_record[current_target_pose] = {
                                    "score": average_score,
                                    "worst_joints": [joint for joint, _ in worst_joints],
                                    "dtw_score": last_dtw_score["overall_score"] if last_dtw_score else None,
                                    "dtw_limb_scores": last_dtw_score["limb_scores"] if last_dtw_score else {},
                                }
                                student_transition_poses = []  # Reset for next transition

                                next_timestamp = timestamps.get(str(pose_id+1))

                                if pose_is_matched and ((pose_id + 1) % checkpoint_poses) == 0:
                                    state = "CHECKPOINT"
                                    checkpoint_waiting_paused = False
                                    match_hold_frames = 0
                                    score_ema = None
                                    action = None

                                elif next_timestamp:
                                    await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                                    state = "PLAYING"
                                    pose_id += 1
                                    current_target_pose = str(pose_id)
                                    timestamp = timestamps.get(str(pose_id))
                                    match_hold_frames = 0
                                    score_ema = None
                                else: break
                        else:
                            cv2.putText(display_student, f"Match this pose! (Error: {score_ema:.1f})",
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                            if match_hold_frames > 0:
                                cv2.putText(display_student, f"Almost there ({match_hold_frames}/{REQUIRED_HOLD_FRAMES})",
                                            (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
                            if worst_joints:
                                joint_text = ", ".join(joint for joint, _ in worst_joints)
                                cv2.putText(display_student, f"Adjust: {joint_text}",
                                            (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
                            cv2.putText(display_student, "Press 's' to SKIP", 
                                        (20, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Quitting application.")
            
        elif key == ord("s") and state == "PAUSED":
            print(f"Skipped Pose {current_target_pose}! Resuming video...")
            skip_pose = True
            next_timestamp = timestamps.get(str(pose_id+1))
            if ((pose_id + 1) % checkpoint_poses) == 0:
                state = "CHECKPOINT"
                checkpoint_waiting_paused = False
                match_hold_frames = 0
                score_ema = None
                action = None
            elif next_timestamp:
                await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                state = "PLAYING"
                pose_id += 1
                current_target_pose = str(pose_id)
                timestamp = timestamps.get(str(pose_id))
                match_hold_frames = 0
                score_ema = None
            else:
                print("Last keypose achieved")
                break

        #checkpoint logic
        if state == "CHECKPOINT":
            if not checkpoint_waiting_paused:
                await websocket.send(json.dumps({"action": "pause"}))
                checkpoint_waiting_paused = True
            cv2.putText(display_student, f"CHECKPOINT REACHED, continue? Victory Sign or not", 
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3, cv2.LINE_AA)

        if state == "CHECKPOINT" and action == "Thumb_Up":
            next_timestamp = timestamps.get(str(pose_id+1))
            if next_timestamp:
                await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                state = "PLAYING"
                checkpoint_waiting_paused = False
                pose_id += 1
                current_target_pose = str(pose_id)
                timestamp = timestamps.get(str(pose_id))
                match_hold_frames = 0
                score_ema = None
                action = None

        elif state == "CHECKPOINT" and action == "Thumb_Down":
            pose_id = max(0, pose_id - checkpoint_poses + 1)
            next_timestamp = timestamps.get(str(pose_id))
            if next_timestamp is not None:
                await websocket.send(json.dumps({"action": "seek","seek_time":next_timestamp}))
                await websocket.send(json.dumps({"action": "pause"}))
                current_target_pose = str(pose_id)
                timestamp = next_timestamp
                match_hold_frames = 0
                score_ema = None
                student_transition_poses = []
                action = None

                await asyncio.sleep(2)

                replay_target = timestamps.get(str(pose_id + 1))
                if replay_target is not None:
                    await websocket.send(json.dumps({"action": "play_until","target_time":replay_target}))
                    state = "PLAYING"
                    checkpoint_waiting_paused = False
                    pose_id += 1
                    current_target_pose = str(pose_id)
                    timestamp = timestamps.get(str(pose_id))
                else:
                    state = "PAUSED"
                    checkpoint_waiting_paused = False


        if state == "PLAYING":
            annotated_student, pose, world_pose, smoothed_world = pipeline.mark_frame(student_frame)
            if smoothed_world is not None:
                student_transition_poses.append(pipeline.serialize_pose(smoothed_world))
            # Listen to the websocket for TIME_UPDATE without blocking the webcam feed
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                data = json.loads(message)
                
                if data.get("type") == "ARRIVED":
                    print("Chrome arrived perfectly at the next keypose!")
                    # AI GENERATED START — DTW scoring on arrival
                    transition_key = str(pose_id - 1)  # Trajectory from prev keypose to current
                    teacher_traj = teacher_trajectories.get(transition_key, [])
                    if teacher_traj and len(student_transition_poses) >= 2:
                        last_dtw_score = score_transition(teacher_traj, student_transition_poses)
                        print(f"  Movement score: {last_dtw_score['overall_score']:.0f}%")
                        for limb, score in last_dtw_score['limb_scores'].items():
                            print(f"    {limb}: {score:.0f}%")
                    else:
                        last_dtw_score = None
                    student_transition_poses = []  # Reset for next transition
                    # AI GENERATED END
                    state = "PAUSED"
                        
            except asyncio.TimeoutError:
                pass # No message received, just continue loop
            except websockets.exceptions.ConnectionClosed:
                print("Extension disconnected.")
                break


        now = time.monotonic()
        if now - last_overlay_frame_sent >= OPENCV_FRAME_INTERVAL:
            try:
                await send_opencv_overlay_frame(websocket, display_student)
                last_overlay_frame_sent = now
            except websockets.exceptions.ConnectionClosed:
                print("Extension disconnected.")
                break
            except Exception as e:
                print(f"OpenCV overlay frame send error: {e}")
                last_overlay_frame_sent = now

        cv2.namedWindow('Pose Estimation', cv2.WINDOW_NORMAL)
        cv2.imshow('Pose Estimation', display_student)

    cap_student.release()
    cv2.destroyAllWindows()

    sock.close()
    if session_record:
        print("Saving session data...")
        saved_path = pipeline.save_student_record(video_name,session_record)
        print(f"Session data saved to: {saved_path}")

    


