import math
import numpy as np
pose_dict={}

def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)

def angle_between(v1, v2):
    """ Returns the angle in radians between vectors 'v1' and 'v2'::
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.rad2deg(np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0)))

right_ear = np.array([pose_dict[7][0],pose_dict[7][1]])
left_side = np.array([pose_dict[8][0],pose_dict[8][1]])

middle_line = right_ear - left_side
center_line = [1,0]
final_angle = angle_between(middle_line,center_line)





