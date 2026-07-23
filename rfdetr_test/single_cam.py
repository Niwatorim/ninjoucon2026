import cv2
import time
import numpy as np

# You must have rfdetr and supervision installed
# pip install rfdetr supervision
from rfdetr import RFDETRKeypointPreview
import supervision as sv

# COCO 17 Keypoint Edges
COCO_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),             # Face
    (5, 6), (5, 11), (6, 12), (11, 12),         # Torso
    (5, 7), (7, 9),                             # Left Arm
    (6, 8), (8, 10),                            # Right Arm
    (11, 13), (13, 15),                         # Left Leg
    (12, 14), (14, 16)                          # Right Leg
]

def draw_keypoints(frame, keypoints_obj):
    """
    Custom drawer to draw COCO keypoints and edges on the frame.
    keypoints_obj: supervision.KeyPoints object
    """
    if not keypoints_obj or len(keypoints_obj) == 0:
        return frame
    
    # keypoints_obj.xy is usually shape (N, 17, 2)
    xy = keypoints_obj.xy
    confidence = keypoints_obj.confidence if hasattr(keypoints_obj, 'confidence') else None

    for i in range(len(xy)):
        pts = xy[i] # (17, 2)
        conf = confidence[i] if confidence is not None else np.ones(17)

        # Draw vertices
        for j in range(len(pts)):
            x, y = int(pts[j][0]), int(pts[j][1])
            # Only draw if confidence > 0.5 and point is not [0, 0]
            if conf[j] > 0.5 and (x > 0 and y > 0):
                cv2.circle(frame, (x, y), 4, (0, 0, 255), -1)

        # Draw edges
        for edge in COCO_EDGES:
            pt1_idx, pt2_idx = edge
            x1, y1 = int(pts[pt1_idx][0]), int(pts[pt1_idx][1])
            x2, y2 = int(pts[pt2_idx][0]), int(pts[pt2_idx][1])

            # Check validity
            valid_1 = conf[pt1_idx] > 0.5 and (x1 > 0 and y1 > 0)
            valid_2 = conf[pt2_idx] > 0.5 and (x2 > 0 and y2 > 0)

            if valid_1 and valid_2:
                cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    return frame

def main():
    print("Initializing RF-DETR Keypoint Model...")
    model = RFDETRKeypointPreview()
    print("Model loaded.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    print("Starting video stream. Press 'q' to quit.")

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Predict keypoints
        # The result is typically a supervision.KeyPoints object
        keypoints = model.predict(frame, threshold=0.5)

        # Draw keypoints onto frame
        annotated_frame = draw_keypoints(frame, keypoints)

        # FPS calculation
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        cv2.putText(annotated_frame, f"People Detected: {len(keypoints)}", (20, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        cv2.imshow("RF-DETR Single Cam", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
