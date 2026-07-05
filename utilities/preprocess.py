"""
Anything to do with preprocessing
"""
import os
import json
import cv2
import numpy as np
from video_mediapipeline import get_pose_difference, normalize_3d_landmarks
from utilities.mediapipeline import MedaiPipeline

def generate_keyposes(video_name:str, output_path:str = "keyposes/teacher_keyposes.json", output_path_time:str = "keyposes/teacher_timestamps.json") -> None:
    """
    Generates keyposes from a videopath and saves them in keyposes/teacher_keyposes
    
    :param video_name: Video path 
    :type video_name: str

    :param output_path: Path to output the keyposes json file 
    :type output_path: str
    """
    pipeline = MedaiPipeline()
    cap = cv2.VideoCapture(video_name)
    keyposes = {}
    timestamps = {}
    pose_id = 0
    last_saved_pose_landmarks = None

    DISTANCE = 0.30 # distance moved for new keypose to be made
    COOLDOWN = 30
    cooldown_timer = 0
    print("process video")
    while cap.isOpened():
        ret,frame = cap.read()
        if not ret:
            break

        time_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        timestamp_sec = time_ms / 1000.0

        if cooldown_timer > 0:
            cooldown_timer -=1
            continue

        #detect pose landmarks
        _, pose, world_pose, smoothed_world = pipeline.mark_frame(frame)

        if world_pose is not None and smoothed_world is not None:
            #normalize
            current_normalized = normalize_3d_landmarks(world_pose)

            #initial pose
            if last_saved_pose_landmarks is None:
                keyposes[str(pose_id)] = pipeline.serialize_pose(smoothed_world)
                timestamps[str(pose_id)] = timestamp_sec
                last_saved_pose_landmarks = current_normalized
                cv2.imwrite(f"keyposes/pose_{pose_id}.png", frame)
                print(f"Logged initial pose {pose_id}")
                pose_id+=1
                cooldown_timer = COOLDOWN
            
            #new poses
            else:
                #Calculate differece
                diff = get_pose_difference(last_saved_pose_landmarks, current_normalized)

                if diff>= DISTANCE:
                    keyposes[str(pose_id)] = pipeline.serialize_pose(smoothed_world)
                    last_saved_pose_landmarks = current_normalized
                    timestamps[str(pose_id)] = timestamp_sec
                    cv2.imwrite(f"keyposes/pose_{pose_id}.png", frame)
                    print("Logged pose id ",pose_id)
                    pose_id+=1
                    cooldown_timer = COOLDOWN

    cap.release()


    #save the content into files
    os.makedirs(os.path.dirname(output_path),exist_ok=True)
    os.makedirs(os.path.dirname(output_path_time),exist_ok=True)


    with open(output_path,"w") as f:
        json.dump(keyposes,f,indent=4)
    with open(output_path_time,"w") as f:
        json.dump(timestamps,f,indent=4)
    print("Keyposes created, number of keyposes: ",len(keyposes))

"""
For every frame, calculate joint angle velocity + location -> two dictionaries

Apply gaussian filtering

Normalize each value

Calculate energy from E = (w1 * vT) + (w2 * vJ)

Find local minima -> compare thru everything (linear search), if frame -1 > current frame < frame +1, its a local minima. If the change is of a value greater than threshold, its a keypose

"""

#Loop through video and per frame have all values for 33 points
