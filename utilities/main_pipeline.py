import json
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

MATCH_THRESHOLD = 10.0
REQUIRED_HOLD_FRAMES = 15
JOINT_DEADZONE = 5.0

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
    skip_pose = False

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
                target_angles = target_angles_db.get(current_target_pose)
                target_normalized = target_normalized_db.get(current_target_pose)

                if target_angles:
                    current_score = 0
                    valid_joints = 0
                    

                    limb_joint_map = {
                        "R.Arm": ["R_armpit", "R_elbow"],
                        "L.Arm": ["L_armpit", "L_elbow"],
                        "R.Leg": ["R_pelvis", "R_knee"],
                        "L.Leg": ["L_pelvis", "L_knee"],
                        "Torso": ["chest_tilt", "hip_tilt"],
                    }
                    limb_scores = {}
                    limb_counts = {}

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


                            for limb_name, limb_joints in limb_joint_map.items():
                                if joint in limb_joints:
                                    limb_scores[limb_name] = limb_scores.get(limb_name, 0) + (diff * weight)
                                    limb_counts[limb_name] = limb_counts.get(limb_name, 0) + 1

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
                        

                        y_offset = 180
                        for limb_name in ["R.Arm", "L.Arm", "R.Leg", "L.Leg", "Torso"]:
                            if limb_name in limb_scores and limb_counts.get(limb_name, 0) > 0:
                                avg_limb = limb_scores[limb_name] / limb_counts[limb_name]
                                # Convert error to percentage (lower error = higher %)
                                pct = max(0, min(100, 100 - (avg_limb / MATCH_THRESHOLD) * 100))
                                color = (0, 255, 0) if pct >= 80 else (0, 255, 255) if pct >= 50 else (0, 0, 255)
                                bar_len = int(pct / 10)
                                bar = "\u2588" * bar_len + "\u2591" * (10 - bar_len)
                                cv2.putText(display_student, f"{limb_name}: {bar} {pct:.0f}%",
                                            (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                                y_offset += 25


                        if last_dtw_score is not None:
                            dtw_lines = format_score_display(last_dtw_score)
                            dtw_y = y_offset + 10
                            for line in dtw_lines:
                                cv2.putText(display_student, line,
                                            (20, dtw_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1, cv2.LINE_AA)
                                dtw_y += 22


                        if average_score < MATCH_THRESHOLD:
                            match_hold_frames += 1
                            cv2.putText(display_student, f"HOLD IT! ({match_hold_frames}/{REQUIRED_HOLD_FRAMES})", 
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3, cv2.LINE_AA)
                            
                            if match_hold_frames >= REQUIRED_HOLD_FRAMES:
                                print(f"Pose {current_target_pose} matched! Resuming video...")
                                pose_is_matched = True
                                session_record[current_target_pose] = {
                                    "score": average_score,
                                    "limb_scores": {k: limb_scores.get(k, 0) / max(limb_counts.get(k, 1), 1) for k in limb_joint_map},
                                    "dtw_score": last_dtw_score["overall_score"] if last_dtw_score else None,
                                }
                                student_transition_poses = []  # Reset for next transition

                                next_timestamp = timestamps.get(str(pose_id+1))

                                if pose_is_matched and ((pose_id + 1) % checkpoint_poses) == 0:
                                    state = "CHECKPOINT"

                                elif next_timestamp:
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
            
        elif key == ord("s") and state == "PAUSED":
            print(f"Skipped Pose {current_target_pose}! Resuming video...")
            skip_pose = True
            next_timestamp = timestamps.get(str(pose_id+1))
            if ((pose_id + 1) % checkpoint_poses) == 0:
                state = "CHECKPOINT"
            elif next_timestamp:
                await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                state = "PLAYING"
                pose_id += 1
                current_target_pose = str(pose_id)
                timestamp = timestamps.get(str(pose_id))
            else:
                print("Last keypose achieved")
                break

        #checkpoint logic
        if state == "CHECKPOINT":
            cv2.putText(display_student, f"CHECKPOINT REACHED, continue? Victory Sign or not", 
                                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3, cv2.LINE_AA)

        if state == "CHECKPOINT" and action == "Thumb_Up":
            next_timestamp = timestamps.get(str(pose_id+1))
            if next_timestamp:
                await websocket.send(json.dumps({"action": "play_until","target_time":next_timestamp}))
                state = "PLAYING"
                pose_id += 1
                current_target_pose = str(pose_id)
                timestamp = timestamps.get(str(pose_id))

        elif state == "CHECKPOINT" and action == "Thumb_Down":
            pose_id = max(0, pose_id - checkpoint_poses + 1)
            next_timestamp = timestamps.get(str(pose_id))
            if next_timestamp is not None:
                await websocket.send(json.dumps({"action": "seek","seek_time":next_timestamp}))
                await websocket.send(json.dumps({"action": "pause"}))
                state = "PAUSED"
                current_target_pose = str(pose_id)
                timestamp = next_timestamp


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


        cv2.namedWindow('Pose Estimation', cv2.WINDOW_NORMAL)
        cv2.imshow('Pose Estimation', display_student)

    cap_student.release()
    cv2.destroyAllWindows()

    sock.close()
    if session_record:
        print("Saving session data...")
        saved_path = pipeline.save_student_record(video_name,session_record)
        print(f"Session data saved to: {saved_path}")

    


