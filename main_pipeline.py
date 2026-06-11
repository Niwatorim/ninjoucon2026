import json
from mediapipeline import MedaiPipeline, human
from matplotlib import pyplot as plt
import numpy as np
import os
import cv2

MATCH_THRESHOLD = 20.0
REQUIRED_HOLD_FRAMES = 5
JOINT_DEADZONE = 10.0

def interactive_training_session(teacher_video_path, student_camera=0):
    pipeline = MedaiPipeline()
    session_record = {}

    # 1. Load database
    with open("./keyposes/poses.json", "r") as f:
        stored_poses = json.load(f)

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
            # Keys in JSON strings need to be converted to int
            teacher_keyframes = {int(frame): pose_id for frame, pose_id in raw_keyframes.items()}
    except FileNotFoundError:
        print("Error: teacher_keyframes.json not found. Please run the pre-processing script first.")
        return

    # 3. Initialize Video Streams
    cap_teacher = cv2.VideoCapture(teacher_video_path)
    cap_student = cv2.VideoCapture(student_camera)

    if not cap_teacher.isOpened() or not cap_student.isOpened():
        print("Error: Could not open video streams.")
        return

    # --- STATE MACHINE VARIABLES ---
    state = "PLAYING" 
    current_target_pose = None
    teacher_frame_count = 0
    current_teacher_frame = None  
    match_hold_frames = 0 
    
    # Initialize the array to hold the recording
    current_pose_sequence = []

    print("Controls: Press 'q' to quit, 's' to skip a pose.")

    while True:
        # Flags for the end-of-loop state transition
        pose_is_matched = False
        skip_pose = False

        # --- TEACHER LOGIC ---
        if state == "PLAYING":
            ret_t, teacher_frame = cap_teacher.read()

            if not ret_t:
                print("Training complete! Teacher video ended.")
                break # Exit the main loop when video is done
            
            teacher_frame_count += 1
            current_teacher_frame = teacher_frame 
            
            # Check if we hit a keyframe
            if teacher_frame_count in teacher_keyframes:
                current_target_pose = teacher_keyframes[teacher_frame_count]
                state = "PAUSED"
                match_hold_frames = 0 
                current_pose_sequence = [] # Reset recording array for the new pose

        # --- STUDENT LOGIC ---
        ret_s, student_frame = cap_student.read()
        if not ret_s:
            break
            
        annotated_student, pose = pipeline.mark_frame(student_frame)
        display_student = annotated_student if pose else student_frame

        if state == "PAUSED" and pose:
            # 1. Record the frame immediately
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
                            print(f"Pose {current_target_pose} matched! Resuming video...")
                            pose_is_matched = True
                    else:
                        match_hold_frames = 0 
                        cv2.putText(display_student, f"Match this pose! (Error: {average_score:.1f})", 
                                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                        cv2.putText(display_student, "Press 's' to SKIP", 
                                    (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        # --- DISPLAY PREPARATION ---
        # Ensure we have a teacher frame to display before attempting to resize
        if current_teacher_frame is not None:
            resized_teacher = cv2.resize(current_teacher_frame, (display_student.shape[1], display_student.shape[0]))
            cv2.putText(resized_teacher, f"Teacher (Frame {teacher_frame_count})", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
            
            status_text = "Watch Teacher" if state == "PLAYING" else "YOUR TURN!"
            status_color = (0, 255, 0) if state == "PLAYING" else (0, 0, 255)
            cv2.putText(display_student, status_text, (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 3, cv2.LINE_AA)

            combined_frame = np.hstack((resized_teacher, display_student))
            cv2.imshow('Interactive Dojo', combined_frame)

        # --- KEYBOARD CONTROL LOGIC ---
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Quitting application.")
            break
        elif key == ord('s') and state == "PAUSED":
            print(f"Skipped Pose {current_target_pose}! Resuming video...")
            skip_pose = True

        # --- STATE MACHINE TRANSITIONS ---
        if pose_is_matched or skip_pose:
            # Save the sequence into the dictionary keyed by the pose name (e.g., "pose_1")
            session_record[current_target_pose] = {
                "teacher_frame_count": teacher_frame_count,
                "status": "Matched" if pose_is_matched else "Skipped",
                "student_sequence": current_pose_sequence
            }
            print(f"Recorded {len(current_pose_sequence)} frames of progress for {current_target_pose}")
            
            # Reset variables and resume playing the teacher video
            state = "PLAYING"
            current_target_pose = None
            match_hold_frames = 0
            current_pose_sequence = []

    # --- CLEANUP AND SAVING ---
    cap_teacher.release()
    cap_student.release()
    cv2.destroyAllWindows()

    # Save the gathered data to the organized file structure
    if session_record:
        print("Saving session data...")
        saved_path = pipeline.save_student_record(teacher_video_path, session_record)
        print(f"Session data saved to: {saved_path}")

if __name__ == "__main__":
    interactive_training_session("captured_vid.mp4")