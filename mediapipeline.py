import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import matplotlib.pyplot as plt
import numpy as np
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles
import cv2
from scipy.spatial.transform import Rotation as R
import json


model_path = "./pose_landmarker_full.task"
keyposes_path = "./keyposes"
keypose_meta_path = "./keyposes/poses.json"


    #relevant landmarks
LM ={
  "nose":0,
  "l_shoulder": 11,"r_shoulder": 12,
  "l_elbow": 13,"r_elbow": 14,
  "l_wrist": 15, "r_wrist": 16,
  "l_hip": 23, "r_hip": 24,
  "l_knee": 25, "r_knee": 26,
  "l_ankle": 27, "r_ankle": 28,
}

JOINT_BONE={ #which bone to target for that joint
    "R_armpit":   {"point": 14, "label": "right elbow"},
    "R_elbow":    {"point": 16, "label": "right forearm"},
    "L_armpit":   {"point": 13, "label": "left elbow"},
    "L_elbow":    {"point": 15, "label": "left forearm"},
    "chest_tilt": {"point": 12, "label": "Chest"},
    "hip_tilt":   {"point": 24, "label": "hips"},
    "R_pelvis":   {"point": 26, "label": "right knee"},
    "L_pelvis":   {"point": 25, "label": "left knee"},
    "R_knee":     {"point": 28, "label": "right ankle"},
    "L_knee":     {"point": 27, "label": "left ankle"},
}

JOINT_WEIGHTS = { #weighting for how important this stuff is
    "R_armpit": 1.0, "L_armpit": 1.0,
    "R_elbow":  0.8, "L_elbow":  0.8,
    "chest_tilt": 1.2, "hip_tilt": 1.2,
    "R_pelvis": 1.0, "L_pelvis": 1.0,
    "R_knee":   0.9, "L_knee":   0.9,
}

ANGLE_THRESHOLD = 12
VISIBILITY_THRESHOLD = 0.5 #must be above this value to be considered

class human():
  def __init__(self,angles,points) -> None:
    self.angles: dict = angles
    self.points: dict = points #normalized coordinates

class MedaiPipeline():
  
  def __init__(self) -> None:
    self.landmarker = self._initialize()
    self.angle_threshold = ANGLE_THRESHOLD
    self.visibility_threshold = VISIBILITY_THRESHOLD
    self.lm = LM
    self.joint_bone = JOINT_BONE
    self.joint_weights = JOINT_WEIGHTS


  def _initialize(self):
    """
    Create the thing that creates the path
    
    :param self: Description
    """
    # setup
    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode
    options = PoseLandmarkerOptions(
        base_options = BaseOptions(model_asset_path=model_path),
        running_mode=VisionRunningMode.IMAGE
    )
    landmarker=vision.PoseLandmarker.create_from_options(options)
    return landmarker
    
  def draw_landmarks_on_image(self, rgb_image, detection_result):
      """
      Draw the landmarks on an image
      
      :param self: Description
      :param rgb_image: Description
      :param detection_result: Description
      """

      pose_landmarks_list = detection_result.pose_landmarks
      annotated_image = np.copy(rgb_image)

      pose_landmark_style = drawing_styles.get_default_pose_landmarks_style()
      pose_connection_style = drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=2)

      for pose_landmarks in pose_landmarks_list:
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=pose_landmarks,
            connections=vision.PoseLandmarksConnections.POSE_LANDMARKS,
            landmark_drawing_spec=pose_landmark_style,
            connection_drawing_spec=pose_connection_style)

      return annotated_image
  
  def mark_image(self,file_name:str):
    """
    Create the landmarks
    
    :param self: Description
    :param file_name: Description
    :type file_name: str
    """

    mp_image=mp.Image.create_from_file(file_name=file_name)
    raw_image= mp_image.numpy_view()
    image_3_channel = cv2.cvtColor(raw_image,cv2.COLOR_RGBA2RGB)
    pose_landmarker_result = self.landmarker.detect(mp_image)
    annotated_image = self.draw_landmarks_on_image(image_3_channel, pose_landmarker_result)
    pose=pose_landmarker_result.pose_landmarks[0]
    image = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)
    return image, pose
  
  def human_analysis(self,pose):
    """
    Takes landmarks and generates angles for the body by making body into vectors and finding angles between them
    """
    #geometry helping:
    def vec(pose_dict,a,b):
      """Vector from a to b"""
      return pose_dict[b]-pose_dict[a]

    def find_angle(v1,v2):
      """
      finds angles between two vectors
      
      :param v1: first vector
      :param v2: second vector
      """
      v1 = v1/np.linalg.norm(v1)
      v2 = v2/np.linalg.norm(v2)

      # for quaternions
      # rotation= R.align_vectors([v1], [v2])[0]
      # quat = rotation.as_quat()

      return np.degrees(np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0)))

    def signed_angle(v1,v2):
      """angle with direction, positive is counter-clockwise"""
      angle = np.arctan2(v2[1], v2[0]) - np.arctan2(v1[1], v1[0])
      return float(np.degrees(angle))

    def normalize_orientation(pose_dict:dict):
      """Rotate everything so that we make hip-> shoulder vertical to ignore rotations and things"""
      mid_hip = (pose_dict[LM["r_hip"]] + pose_dict[LM["l_hip"]])/2
      mid_shoulder = (pose_dict[LM["r_shoulder"]] + pose_dict[LM["l_shoulder"]])/2
      spine = mid_shoulder - mid_hip
      spine_angle = np.arctan2(spine[1], spine[0])
      target_angle = np.pi/2
      rotation_needed = target_angle-spine_angle
      cos_a, sin_a = np.cos(rotation_needed),np.sin(rotation_needed)
      
      rot = np.array([ #rotation matrix
        [cos_a,-sin_a],
        [sin_a,cos_a]
      ])
      centered = {k: v - mid_hip for k,v in pose_dict.items()}
      rotated = {k: rot @ v for k,v in centered.items()}
      return rotated

    #for creating human body angles
    def create_dict(pose):
      values={}
      visibility={}
      for i in range(len(pose)):
        values[i]=np.array([pose[i].x,pose[i].y]) # remove z for now
        visibility[i] = getattr(pose[i],"visibility",1.0)
      return values,visibility
    
    def angle_if_vis(idx_list,v1,v2):
      """Return the angle of the body part if visible or not"""
      if all(visibility.get(i,1.0) >= VISIBILITY_THRESHOLD for i in idx_list):
        return find_angle(v1,v2)
      return None

    #------------
    pose_dict ,visibility= create_dict(pose)
    n = normalize_orientation(pose_dict=pose_dict) #normalize the orientation

    body_angles = {
        "R_armpit":  angle_if_vis([12, 14, 24], vec(n,12,14), vec(n,12,24)),
        "R_elbow":   angle_if_vis([12, 14, 16], vec(n,14,16), vec(n,14,12)),
        "L_armpit":  angle_if_vis([11, 13, 23], vec(n,11,13), vec(n,11,23)),
        "L_elbow":   angle_if_vis([11, 13, 15], vec(n,13,15), vec(n,13,11)),
        "chest_tilt":  angle_if_vis([11, 12], vec(n,12,11), np.array([1,0])),
        "hip_tilt":    angle_if_vis([23, 24], vec(n,24,23), np.array([1,0])),
        "R_pelvis":  angle_if_vis([24, 26], vec(n,24,23), vec(n,24,26)),
        "L_pelvis":  angle_if_vis([23, 25], vec(n,23,24), vec(n,23,25)),
        "R_knee":    angle_if_vis([24, 26, 28], vec(n,26,24), vec(n,26,28)),
        "L_knee":    angle_if_vis([23, 25, 27], vec(n,25,23), vec(n,25,27)),
    }

    return body_angles,pose_dict

  def _hint_location(self,joint,t_val,s_val):
      """TO give the hints on what the angle is"""
      diff = t_val - s_val
      label = JOINT_BONE[joint]["label"]
      if "elbow" in joint.lower() or "knee" in joint.lower():
        return f"{label} : {'extend more' if diff > 0 else 'bend more'} ({diff:+.1f})"
      elif "armpit" in joint.lower() or "pelvis" in joint.lower():
        return f"{label}: {'raise' if diff < 0 else 'lower'} ({diff:+.1f})"
      else:
        return f"{label}: adjust by {diff:+.1f}"
      
  def difference(self,teacher:human,student:human, image, ax=None, threshold = ANGLE_THRESHOLD):
    """Compare the two angles, then annotate for correction"""
    corrections = []
    img_height, img_width = image.shape[:2]
    common = set(teacher.angles) & set(student.angles) #check which common joints they have

    for j in common:
      t_val = teacher.angles[j]
      s_val = student.angles[j]
      weight = JOINT_WEIGHTS.get(j,1.0) #get the weighting for importance

      final_threshold = threshold/weight
      if t_val is None or s_val is None:
        continue

      if abs(t_val-s_val) > final_threshold:
        bone = JOINT_BONE[j]
        point_indx = bone["point"]
        hint = self._hint_location(j,t_val,s_val)

        px_stu = int(float(student.points[point_indx][0]) * img_width)
        py_stu = int(float(student.points[point_indx][1]) * img_height)

        px_teach = int(float(teacher.points[point_indx][0]) * img_width)
        py_teach = int(float(teacher.points[point_indx][1]) * img_height)

        corrections.append({"hint":hint,"points":student.points[point_indx], "start_point":(px_stu, py_stu), "end_point": (px_teach, py_teach)})

        # px_teach = float(teacher.points[point_indx][0]) * img_width
        # py_teach = float(teacher.points[point_indx][1]) * img_height

        # ax.annotate(
        #   "",
        #   xy=(px,py),
        #   xytext=(px_teach,py_teach),
        #   arrowprops=dict(arrowstyle="->",color="blue")
        # )
        if ax is not None:
          ax.annotate(
            hint,
            xy=(px_stu,py_stu),
            xytext = (px_stu+40,py_stu+40),
            fontsize=7,
            color="white",
            bbox=dict(boxstyle="round,pad=0.2", fc="red", alpha=0.7),
            arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
          )

    return corrections

  def normalize(self,pose:dict):
    """normalize the pose so that everything is the same
    
    midpoint of hip -> midpoint to chest = 1
    divide everything by that
    
    """
    def get_value(indx):
      """I dont remember if i kept it as an integer or a string, so im using this"""
      if indx in pose:
        return np.array(pose[indx][:3])
      if str(indx) in pose:
        return np.array(pose[str(indx)][:3])
      return np.zeros(3)

    #chest
    chest = (get_value(12) + get_value(11))/2
    hip = (get_value(24) + get_value(23))/2
    
    
    normalizer = np.linalg.norm(chest - hip)

    if normalizer == 0:
      return pose

    for k,v in pose.items():
      pose[k] = [
        v[0]/normalizer,
        v[1]/normalizer,
        v[2]/normalizer,
        v[3]
      ]
    return pose

  def compare_vectors(self,v1,v2):
    """
    dot product every vector, check score for every item, then find thing with lowest score and thats the one closest
    """
    x = abs(v1[0]-v2[0])
    y = abs(v1[1]-v2[1])
    z = abs(v1[2]-v2[2])

    p1 = np.array(v1[:3])
    p2 = np.array(v2[:3])

    return np.linalg.norm(p1-p2) #distance between two vectors
  
  def normalize_pose(self, pose_data:list):
    """
    For Euclidean distance between student and teacher pose
    Translate to origin, rotate spine to vertical and scale by torso length.
    torso length is between midpoint of shoulder and midpoint of hip
    """
    np_pose = {}
        
    # Check if the input is a list (MediaPipe raw output) or a dictionary
    iterable = enumerate(pose_data) if isinstance(pose_data, list) else pose_data.items()
    
    for k, v in iterable:
        # Check if it's a MediaPipe object and extract x, y
        if hasattr(v, 'x'):
            np_pose[k] = np.array([v.x, v.y])
        else:
            np_pose[k] = np.array(v[:2]) # Fallback if it's already an array/tuple

    # 2. Use np_pose for all the math instead of the raw input
    # Because k is an integer index, np_pose[LM["r_hip"]] will grab the correct array
    mid_hip = (np_pose[LM["r_hip"]] + np_pose[LM["l_hip"]]) / 2
    mid_shoulder = (np_pose[LM["r_shoulder"]] + np_pose[LM["l_shoulder"]]) / 2
    spine = mid_shoulder - mid_hip
    spine_angle = np.arctan2(spine[1], spine[0])
    target_angle = np.pi/2
    rotation_needed = target_angle-spine_angle
    cos_a, sin_a = np.cos(rotation_needed),np.sin(rotation_needed)
    
    rot = np.array([ #rotation matrix
      [cos_a,-sin_a],
      [sin_a,cos_a]
    ])
    centered = {k: v - mid_hip for k,v in np_pose.items()}
    rotated = {k: rot @ v for k,v in centered.items()}

    torso_length = np.linalg.norm(spine)
    normalized_pose = {k: v/torso_length for k,v in rotated.items()}

    transform_params = {
      "mid_hip": mid_hip,
      "rot": rot,
      "torso_length": torso_length
    }

    return normalized_pose, transform_params
  
  def euclidean_distance(self,teacher:human,student:human, student_params:dict, image, ax=None, threshold = 0.3):
    """
    calculate 2D distance in normalized
    then transform back to raw

    some code is from difference
    """
    corrections = []
    img_height, img_width = image.shape[:2]
    
    relevant_landmarks = set(self.lm.values())

    common = set(teacher.keys()) & set(student.keys()) & relevant_landmarks

    rot_inv = student_params["rot"].T

    for j in common:
        t_val = teacher[j]
        s_val = student[j]

        dist = np.linalg.norm(t_val - s_val)

        if dist > threshold:
            scaled_t = t_val * student_params["torso_length"]
            unrotated_t = rot_inv @ scaled_t
            target_raw = unrotated_t + student_params["mid_hip"]

            scaled_s = s_val * student_params["torso_length"]
            unrotated_s = rot_inv @ scaled_s
            student_raw = unrotated_s + student_params["mid_hip"]

            px_stu = int(student_raw[0] * img_width)
            py_stu = int(student_raw[1] * img_height)

            px_teach = int(target_raw[0] * img_width)
            py_teach = int(target_raw[1] * img_height)

            corrections.append({
                "joint": j,
                "start_point": (px_stu, py_stu),
                "end_point": (px_teach, py_teach),
                "error_magnitude": dist
            })
            print(corrections)

    return corrections
  
  def draw_arrow(self, image, corrections:list[dict]):
    """
    use cv2.arrowedLine(image, start_point, end_point, color, thickness, line_type, shift, tipLength)
    if theres correction:
    take the point coordinate of that correction (raw) for both student and teacher
    draw arrow using open cv, student -> teacher
    """
    for correction in corrections:
      start_point = correction["start_point"]
      end_point = correction["end_point"]

      cv2.arrowedLine(
        img=image,
        pt1=start_point,
        pt2=end_point,
        color=(0,0,255),
        thickness=2,
        line_type=cv2.LINE_AA,
        shift=0,
        tipLength=0.2
      )
    return image
  
"""
in main.py, separate difference and euclidean_distance
try using difference and draw arrow in main.py directly
if cannot, correct the difference func to its original state and make the euclidean func

"""