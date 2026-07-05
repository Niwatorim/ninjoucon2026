import cv2
import json
from utilities.mediapipeline import MedaiPipeline

def generate_keyframes(video_path, output_path="teacher_keyframes.json"):
    """
    Scans a teacher video and automatically identifies which frames 
    contain the target keyposes from your database.
    """
    pipeline = MedaiPipeline()

    print("Loading database...")
    with open("./keyposes/poses.json", "r") as f:
        stored_poses = json.load(f)

    # We only need angles to identify the pose
    target_angles_db = {}
    for key, pose_dict in stored_poses.items():
        angles, _ = pipeline.human_analysis(pose_dict)
        target_angles_db[key] = angles

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open {video_path}")
        return

    frame_count = 0
    keyframes = {}
    last_pose_logged = None
    
    # Settings
    MATCH_THRESHOLD = 15.0 # How strict the teacher needs to be to trigger a keyframe
    COOLDOWN_FRAMES = 30   # Wait at least 30 frames (~1 sec) before logging another pose

    cooldown_timer = 0
    print(f"Scanning {video_path} for keyposes... This may take a minute.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Count down the cooldown timer
        if cooldown_timer > 0:
            cooldown_timer -= 1
            continue # Skip processing until cooldown finishes to save CPU

        # Process frame
        _, pose = pipeline.mark_frame(frame) #type:ignore
        
        if pose:
            teacher_angles, _ = pipeline.human_analysis(pose)
            
            best_match = None
            best_score = float("inf")

            # Check against all known poses
            for key, target_angles in target_angles_db.items():
                current_score = 0
                valid_joints = 0

                for joint, t_angle in target_angles.items():
                    s_angle = teacher_angles.get(joint)
                    if t_angle is not None and s_angle is not None:
                        diff = abs(t_angle - s_angle)
                        weight = pipeline.joint_weights.get(joint, 1.0)
                        current_score += (diff * weight)
                        valid_joints += 1

                if valid_joints > 0:
                    average_score = current_score / valid_joints
                    if average_score < best_score:
                        best_match = key
                        best_score = average_score

            # If we found a match and it's a NEW pose
            if best_score < MATCH_THRESHOLD:
                if best_match != last_pose_logged:
                    keyframes[frame_count] = best_match
                    last_pose_logged = best_match
                    cooldown_timer = COOLDOWN_FRAMES
                    print(f"✓ Frame {frame_count}: Logged Pose '{best_match}' (Accuracy: {best_score:.1f})")

    cap.release()

    # Save to file
    with open(output_path, "w") as f:
        json.dump(keyframes, f, indent=4)
        
    print(f"\nSuccess! Saved {len(keyframes)} keyframes to {output_path}.")

generate_keyframes("captured_vid.mp4")