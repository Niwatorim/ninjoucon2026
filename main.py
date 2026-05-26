
import json
from mediapipeline import MedaiPipeline,human
from matplotlib import pyplot as plt



import cv2
import numpy as np
import time
import json
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles
from scipy.spatial.transform import Rotation as R
import math
import socket

from mediapipeline import MedaiPipeline,human
from OneEuroFilter import OneEuroFilter
from pathlib import Path
import time
import asyncio
import cv2

#TODO: debug why no arrows appear


    # Example usage 1
def compare_two_images(picture1="./image.png",picture2 = "./download.png"):
    """ TAKE TWO IMAGES AND COMPARE THE TWO, THEN SHOW"""

    pipeline=MedaiPipeline()

    image,pose = pipeline.mark_image(picture1)
    image2,pose2 = pipeline.mark_image(picture2)

    t_angles, t_points = pipeline.human_analysis(pose)
    s_angles, s_points = pipeline.human_analysis(pose2)
    teacher = human(t_angles,t_points)
    student = human(s_angles,s_points)

    teacher_normalized, teacher_transform = pipeline.normalize_pose(pose)
    student_normalized, student_transform = pipeline.normalize_pose(pose2) 

    corrections_arrow = pipeline.euclidean_distance(teacher_normalized, student_normalized, student_transform, image2)

    arrow_student = pipeline.draw_arrow(image2,corrections_arrow)

    corrections = pipeline.difference(teacher,student,image2)

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    axes[0].imshow(image)
    axes[0].set_title("Teacher",fontsize=13,fontweight="bold")
    axes[0].axis('off')


    axes[1].imshow(arrow_student)
    axes[1].set_title("Student",fontsize=13,fontweight="bold")
    axes[1].axis('off')

    if corrections:
        summary = "\n".join(f"• {c}" for c in corrections)
        fig.text(0.5, 0.01, f"Corrections needed:\n{summary}",
                ha="center", fontsize=9, color="darkred",
                bbox=dict(boxstyle="round", fc="lightyellow", ec="red"))
        
    else:
        fig.text(0.5, 0.01, "✓ Pose matches teacher!", ha="center",
                fontsize=11, color="green")

    plt.tight_layout()
    plt.show()

    # Example usage 2
def check_keyposes(picture="./image.png"):
    """
    Check which of the images in keyposes is closest to the image: ./image.png
    """

    pipeline = MedaiPipeline()
    image,pose = pipeline.mark_image(picture)
    pose_dictionary = {}
    for i,v in enumerate(pose):
        pose_dictionary[i]=[v.x,v.y,v.z,v.visibility]


    with open("./keyposes/poses.json","r") as f:
        stored:dict = json.load(f)

    pose_dictionary = pipeline.normalize(pose_dictionary)

    for key, value in stored.items():
        stored[key] = pipeline.normalize(value)

    score = float("inf") #infinity
    index = None

    print(json.dumps(pose_dictionary,indent=3))  

    for i,v in stored.items():
        current_score = 0
        valid_joints = 0

        for j,values in v.items():
            vector1 = pose_dictionary[int(j)]
            vector2 = values

            if vector1[3] > pipeline.visibility_threshold and vector2[3] > pipeline.visibility_threshold:
                valid_joints +=1
                current_score+=pipeline.compare_vectors(vector1,vector2)

        if valid_joints > 7: #if image not empty
            average_score = current_score/valid_joints

            if average_score < score:
                index = i
                score = average_score


    return score,index

_, index = check_keyposes("./image.png")
# compare_two_images("./image.png",f"./keyposes/{index}.png")
compare_two_images("./image.png","keypose_sample.jpeg")


# def compare_two_images(pose,picture2 = "./download.png"):
#     """ TAKE TWO IMAGES AND COMPARE THE TWO, THEN SHOW"""

#     pipeline=MedaiPipeline()
#     image2,pose2 = pipeline.mark_image(picture2)

#     t_angles, t_points = pipeline.human_analysis(pose)
#     s_angles, s_points = pipeline.human_analysis(pose2)
#     teacher = human(t_angles,t_points)
#     student = human(s_angles,s_points)

#     teacher_normalized, teacher_transform = pipeline.normalize_pose(pose)
#     student_normalized, student_transform = pipeline.normalize_pose(pose2) 

#     corrections_arrow = pipeline.euclidean_distance(teacher_normalized, student_normalized, student_transform, image2)

#     arrow_student = pipeline.draw_arrow(image2,corrections_arrow)
#     final_corrections =[]
#     reverse_LM ={
#         0:"nose",
#         11:"l_shoulder",12:"r_shoulder",
#         13: "l_elbow",14:"r_elbow",
#         15:"l_wrist",16:"r_wrist",
#         23:"l_hip",24:"r_hip",
#         25:"l_knee",26: "r_knee",
#         27:"l_ankle", 28:"r_ankle",
#     }
#     for i in corrections_arrow:
#         #i has the following
#         """
#         joint: number, based on LM from Mediapipe class
#         start_point_3d -> end_point_3d vector
#         rotation from pointing to avatars right side 90 degrees quaternion
#         """
#         print(f"the joint is........ joint: {i["joint"]}")
#         temp_dict={
#             "body":reverse_LM[i["joint"]]
#         }
#         arrow_vector = np.array(i["end_point_3d"]) - np.array(i["start_point_3d"])
#         start_vector = np.array([-1,0,0])
#         arrow_vector = arrow_vector/np.linalg.norm(arrow_vector)
#         start_vector = start_vector/np.linalg.norm(start_vector)
#         rotation = R.align_vectors(arrow_vector,start_vector)
#         temp_dict["direction"] = rotation[0].as_quat()
#         final_corrections.append(temp_dict)
#     return final_corrections
    
# def check_keyposes(picture="./keypose_sample.jpeg"): #change to just pose for now
#     """
#     Check which of the images in keyposes is closest to the image: ./image.png
#     """

#     pipeline = MedaiPipeline()
#     image,pose = pipeline.mark_image(picture)
#     # pose_dictionary = {}
#     # for i,v in enumerate(pose):
#     #     pose_dictionary[i]=[v.x,v.y,v.z,v.visibility]


#     # with open("./keyposes/poses.json","r") as f:
#     #     stored:dict = json.load(f)

#     # pose_dictionary = pipeline.normalize(pose_dictionary)

#     # for key, value in stored.items():
#     #     stored[key] = pipeline.normalize(value)

#     # score = float("inf") #infinity
#     # index = None

#     # print(json.dumps(pose_dictionary,indent=3))  

#     # for i,v in stored.items():
#     #     current_score = 0
#     #     valid_joints = 0

#     #     for j,values in v.items():
#     #         vector1 = pose_dictionary[int(j)]
#     #         vector2 = values

#     #         if vector1[3] > pipeline.visibility_threshold and vector2[3] > pipeline.visibility_threshold:
#     #             valid_joints +=1
#     #             current_score+=pipeline.compare_vectors(vector1,vector2)

#     #     if valid_joints > 7: #if image not empty
#     #         average_score = current_score/valid_joints

#     #         if average_score < score:
#     #             index = i
#     #             score = average_score


#     return compare_two_images(pose,f"./keyposes/{7}.png")
#     # return compare_two_images(pose[0],f"./keyposes/{index}.png") #For now make this pose 7







# import cv2
# cap = cv2.VideoCapture(0)

# if not cap.isOpened():
#     print("Error: Could not open camera.")
#     exit()

# print("Press 'q' to quit the video stream.")


# while True:
#     ret, frame = cap.read()

#     if not ret:
#         print("Error: Can't receive frame (stream end?). Exiting ...")
#         break
#     cv2.imshow('Live Camera', frame)

#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# cap.release()
# cv2.destroyAllWindows()