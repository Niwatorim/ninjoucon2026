import os
import json
import numpy as np
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8')

# MediaPipe pose landmark indices for the body (excluding face/hands)
# Maps from a reduced 12-point skeleton to MediaPipe's 33-landmark indices
# 0:R_SHOULDER(12), 1:L_SHOULDER(11), 2:L_ELBOW(13), 3:R_ELBOW(14),
# 4:L_WRIST(15), 5:R_WRIST(16), 6:R_HIP(24), 7:L_HIP(23),
# 8:R_KNEE(26), 9:L_KNEE(25), 10:R_ANKLE(28), 11:L_ANKLE(27)
mp_body_indices = [12, 11, 13, 14, 15, 16, 24, 23, 26, 25, 28, 27]

# Skeleton connections (indices into mp_body_indices, NOT raw MediaPipe indices)
torso = [[0, 1], [1, 7], [7, 6], [6, 0]]
armr  = [[0, 3], [3, 5]]
arml  = [[1, 2], [2, 4]]
legr  = [[6, 8], [8, 10]]
legl  = [[7, 9], [9, 11]]
body  = [torso, arml, armr, legr, legl]
colors = ['red', 'blue', 'green', 'black', 'orange']


def load_recording(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def visualize_3d(all_frames):
    """Visualize 3D pose using the same style as bodypose3d/show_3d_pose.py"""

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    for framenum, frame_kpts in enumerate(all_frames):
        if framenum % 2 == 0:
            continue  # skip every 2nd frame like the reference

        frame_kpts = np.array(frame_kpts)  # (33, 3)

        # Extract only the 12 body keypoints we care about
        kpts3d = frame_kpts[mp_body_indices]  # (12, 3)

        for bodypart, part_color in zip(body, colors):
            for _c in bodypart:
                ax.plot(
                    xs=[kpts3d[_c[0], 0], kpts3d[_c[1], 0]],
                    ys=[kpts3d[_c[0], 1], kpts3d[_c[1], 1]],
                    zs=[kpts3d[_c[0], 2], kpts3d[_c[1], 2]],
                    linewidth=4, c=part_color
                )

        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])

        ax.set_xlim3d(-2, 2)
        ax.set_xlabel('x')
        ax.set_ylim3d(-2, 2)
        ax.set_ylabel('y')
        ax.set_zlim3d(-2, 2)
        ax.set_zlabel('z')

        plt.pause(0.1)
        ax.cla()

def main():
    recording_path = os.path.join(os.path.dirname(__file__), "pose_recording.json")
    if not os.path.exists(recording_path):
        print(f"Error: {recording_path} not found. Please run multicam.py first.")
        return

    frames = load_recording(recording_path)
    if not frames:
        print("Recording is empty.")
        return

    print(f"Loaded {len(frames)} frames. Playing back...")
    visualize_3d(frames)

if __name__ == "__main__":
    main()
