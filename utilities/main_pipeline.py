import json
from utilities.mediapipeline import MedaiPipeline, human
from matplotlib import pyplot as plt
import numpy as np
import os
import cv2
import socket
from video_mediapipeline import human_analysis_segmentation, vect_to_dict, quat_to_dict
import websockets


MATCH_THRESHOLD = 10.0
REQUIRED_HOLD_FRAMES = 15
JOINT_DEADZONE = 5.0

pose_id = 0
action = None
state = None

import asyncio
async def interactive_training_session(websocket, timestamps:dict, video_name:str= "video", student_camera=0):
    global action
    global pose_id
    global timestamp
    global state

    pipeline = MedaiPipeline()
    session_record = {}

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
    skip_pose = False

    while True:
        ret,student_frame = cap_student.read()
        if not ret:
            break
        
        display_student = student_frame # Initialize by default
        
        if state == "PAUSED":
            annotated_student, pose, world_pose, smoothed_world = pipeline.mark_frame(student_frame)
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
                
                target_angles = target_angles_db.get(current_target_pose)
                target_normalized = target_normalized_db.get(current_target_pose)

                if target_angles:
                    current_score = 0
                    valid_joints = 0
                    
                    # Calculate Error
                    for joint, t_angle in target_angles.items():
                        s_angle = student_angles.get(joint)
                        if t_angle is not None and s_angle is not None:
                            diff = abs(t_angle - s_angle)
                            
                            # Apply Deadzone
                            if diff < JOINT_DEADZONE:
                                diff = 0.0 
                                
                            weight = pipeline.joint_weights.get(joint, 1.0)
                            current_score += (diff * weight)
                            valid_joints += 1

                    if valid_joints > 0:
                        average_score = current_score / valid_joints
                        
                        # Draw Euclidean Arrows
                        corrections = pipeline.euclidean_distance(
                            teacher=target_normalized, #type: ignore
                            student=student_normalized, 
                            student_params=student_transform, 
                            image=display_student
                        )
                        display_student = pipeline.draw_arrow(display_student, corrections)

                        
                        correction_payload = pipeline.corrections_to_unity_format(corrections)
                        if any(v is not None for v in correction_payload["corrections"].values()):
                            try:
                                sock.sendto(json.dumps(correction_payload).encode(), correction_address)
                            except Exception as e:
                                print(f"Correction send error: {e}")
                        
                        # Match Logic
                        if average_score < MATCH_THRESHOLD:
                            match_hold_frames += 1
                            cv2.putText(display_student, f"HOLD IT! ({match_hold_frames}/{REQUIRED_HOLD_FRAMES})", 
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3, cv2.LINE_AA)
                            
                            if match_hold_frames >= REQUIRED_HOLD_FRAMES:
                                print(f"Pose {current_target_pose} matched! Resuming video...")
                                pose_is_matched = True
                                next_timestamp = timestamps.get(str(pose_id+1))
                                if next_timestamp:
                                    await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                                    state = "PLAYING"
                                    pose_id += 1
                                    current_target_pose = str(pose_id)
                                    timestamp = timestamps.get(str(pose_id))
                                else: break
                        else:
                            match_hold_frames = 0 
                            cv2.putText(display_student, f"Match this pose! (Error: {average_score:.1f})", 
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                            cv2.putText(display_student, "Press 's' to SKIP", 
                                        (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Quitting application.")
            break
        elif key == ord('s') and state == "PAUSED":
            print(f"Skipped Pose {current_target_pose}! Resuming video...")
            skip_pose = True
            next_timestamp = timestamps.get(str(pose_id+1))
            if next_timestamp:
                await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                state = "PLAYING"
                pose_id += 1
                current_target_pose = str(pose_id)
                timestamp = timestamps.get(str(pose_id))
            else:
                print("Last keypose achieved")
                break
        if state == "PLAYING":
            # Listen to the websocket for TIME_UPDATE without blocking the webcam feed
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                data = json.loads(message)
                
                if data.get("type") == "ARRIVED":
                    print("Chrome arrived perfectly at the next keypose!")
                    state = "PAUSED"
                        
            except asyncio.TimeoutError:
                pass # No message received, just continue loop
            except websockets.exceptions.ConnectionClosed:
                print("Extension disconnected.")
                break


        cv2.namedWindow('Pose Estimation', cv2.WINDOW_NORMAL)
        cv2.imshow('Pose Estimation', display_student)

    cap_student.release()
    cv2.destroyAllWindows()

    sock.close()
    if session_record:
        print("Saving session data...")
        saved_path = pipeline.save_student_record(video_name,session_record)
        print(f"Session data saved to: {saved_path}")

    


