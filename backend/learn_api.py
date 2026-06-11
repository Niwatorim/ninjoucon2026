from flask import Blueprint, Response, jsonify
import cv2
import threading
import time
import json
import numpy as np
import os

# Import directly from your pipeline
from mediapipeline import MedaiPipeline, human

learn_bp = Blueprint('learn', __name__)

# --- GLOBAL VARIABLES ---
latest_teacher_frame = None
latest_student_frame = None
latest_unity_frame = None

# Global control flags for web interaction
skip_requested = False
stop_pipeline = False

# --- BACKGROUND PIPELINE THREAD ---
def run_background_pipeline():
    global latest_teacher_frame, latest_student_frame, skip_requested, stop_pipeline
    
    pipeline = MedaiPipeline()
    session_record = {}

    MATCH_THRESHOLD = 20.0
    REQUIRED_HOLD_FRAMES = 5
    JOINT_DEADZONE = 10.0
    TEACHER_VIDEO = "captured_vid.mp4"
    STUDENT_CAMERA = 0

    # 1. Load database
    try:
        with open("./keyposes/poses.json", "r") as f:
            stored_poses = json.load(f)
    except FileNotFoundError:
        print("Error: ./keyposes/poses.json not found.")
        return

    target_angles_db = {}
    target_normalized_db = {}

    for key, pose_dict in stored_poses.items():
        angles, _ = pipeline.human_analysis(pose_dict)
        target_angles_db[key] = angles
        normalized_pts, _ = pipeline.normalize_pose(pose_dict)
        target_normalized_db[key] = normalized_pts

    # 2. Load auto-generated keyframes
    try:
        with open("teacher_keyframes.json", "r") as f:
            raw_keyframes = json.load(f)
            teacher_keyframes = {int(frame): pose_id for frame, pose_id in raw_keyframes.items()}
    except FileNotFoundError:
        print("Error: teacher_keyframes.json not found.")
        return

    # 3. Initialize Video Streams
    cap_teacher = cv2.VideoCapture(TEACHER_VIDEO)
    cap_student = cv2.VideoCapture(STUDENT_CAMERA)

    if not cap_teacher.isOpened() or not cap_student.isOpened():
        print("Error: Could not open video streams.")
        return

    # State Machine Variables
    state = "PLAYING" 
    current_target_pose = None
    teacher_frame_count = 0
    current_teacher_frame = None  
    match_hold_frames = 0 
    current_pose_sequence = []

    print("Background training pipeline started.")

    while not stop_pipeline:
        pose_is_matched = False

        # --- TEACHER LOGIC ---
        if state == "PLAYING":
            ret_t, teacher_frame = cap_teacher.read()

            if not ret_t:
                print("Training complete! Teacher video ended.")
                # Save session data and exit thread gracefully
                if session_record:
                    pipeline.save_student_record(TEACHER_VIDEO, session_record)
                break
            
            teacher_frame_count += 1
            current_teacher_frame = teacher_frame 
            
            if teacher_frame_count in teacher_keyframes:
                current_target_pose = teacher_keyframes[teacher_frame_count]
                state = "PAUSED"
                match_hold_frames = 0 
                current_pose_sequence = []

        # --- STUDENT LOGIC ---
        ret_s, student_frame = cap_student.read()
        if not ret_s:
            time.sleep(0.1) # Wait for camera to recover
            continue
            
        annotated_student, pose = pipeline.mark_frame(student_frame)
        display_student = annotated_student if pose else student_frame

        if state == "PAUSED" and pose:
            current_pose_sequence.append(pipeline.serialize_pose(pose))

            student_angles, _ = pipeline.human_analysis(pose)
            student_normalized, student_transform = pipeline.normalize_pose(pose)
            
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
                        
                        if diff < JOINT_DEADZONE:
                            diff = 0.0 
                            
                        weight = pipeline.joint_weights.get(joint, 1.0)
                        current_score += (diff * weight)
                        valid_joints += 1

                if valid_joints > 0:
                    average_score = current_score / valid_joints
                    
                    corrections = pipeline.euclidean_distance(
                        teacher=target_normalized, 
                        student=student_normalized, 
                        student_params=student_transform, 
                        image=display_student
                    )
                    display_student = pipeline.draw_arrow(display_student, corrections)

                    # Match Logic
                    if average_score < MATCH_THRESHOLD:
                        match_hold_frames += 1
                        cv2.putText(display_student, f"HOLD IT! ({match_hold_frames}/{REQUIRED_HOLD_FRAMES})", 
                                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3, cv2.LINE_AA)
                        
                        if match_hold_frames >= REQUIRED_HOLD_FRAMES:
                            print(f"Pose {current_target_pose} matched!")
                            pose_is_matched = True
                    else:
                        match_hold_frames = 0 
                        cv2.putText(display_student, f"Match this pose! (Error: {average_score:.1f})", 
                                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)

        # --- PREPARE FRAMES FOR STREAMING ---
        teacher_display = current_teacher_frame.copy() if current_teacher_frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        
        cv2.putText(teacher_display, f"Teacher (Frame {teacher_frame_count})", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
        
        status_text = "Watch Teacher" if state == "PLAYING" else "YOUR TURN!"
        status_color = (0, 255, 0) if state == "PLAYING" else (0, 0, 255)
        cv2.putText(display_student, status_text, (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 3, cv2.LINE_AA)

        # Safely update the global variables for Flask to stream
        latest_teacher_frame = teacher_display
        latest_student_frame = display_student

        # --- STATE MACHINE TRANSITIONS ---
        if pose_is_matched or skip_requested:
            session_record[current_target_pose] = {
                "teacher_frame_count": teacher_frame_count,
                "status": "Matched" if pose_is_matched else "Skipped",
                "student_sequence": current_pose_sequence
            }
            
            state = "PLAYING"
            current_target_pose = None
            match_hold_frames = 0
            current_pose_sequence = []
            skip_requested = False # Reset the flag after skipping

        # Small sleep to prevent the loop from hogging 100% of the CPU
        time.sleep(0.01)

    cap_teacher.release()
    cap_student.release()


# Start the pipeline thread immediately when the module loads
thread = threading.Thread(target=run_background_pipeline, daemon=True)
thread.start()


# --- STREAMING GENERATOR ---
def generate_frames(stream_type):
    global latest_teacher_frame, latest_student_frame, latest_unity_frame
    
    while True:
        frame_to_stream = None
        
        if stream_type == 'teacher':
            frame_to_stream = latest_teacher_frame
        elif stream_type == 'livecam':
            frame_to_stream = latest_student_frame
        elif stream_type == 'unity':
            # Fallback if Unity frame isn't implemented yet
            frame_to_stream = latest_unity_frame if latest_unity_frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
            
        if frame_to_stream is not None:
            ret, buffer = cv2.imencode('.jpg', frame_to_stream)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.03) # Limit stream rate to ~30 FPS to save network bandwidth

# --- ROUTES ---

@learn_bp.route('/teacher_only', methods=['GET'])
def stream_teacher():
    return Response(generate_frames('teacher'), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@learn_bp.route('/livecam_only', methods=['GET'])
def stream_livecam():
    return Response(generate_frames('livecam'), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@learn_bp.route('/unity_3dmocap_only', methods=['GET'])
def stream_unity():
    return Response(generate_frames('unity'), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# New route to replace keyboard control
@learn_bp.route('/skip_pose', methods=['POST'])
def skip_current_pose():
    global skip_requested
    skip_requested = True
    return jsonify({"status": "Skip requested"}), 200