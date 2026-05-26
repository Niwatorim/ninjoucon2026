import cv2
import numpy as np
import mediapipe as mp
import sys
import os
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles
from mediapipe.tasks.python.vision.hand_landmarker import HandLandmarksConnections

def draw_landmarks_on_image(rgb_image, detection_result):
    """
    Draw hand landmarks and connections on the image.
    """
    hand_landmarks_list = detection_result.hand_landmarks
    handedness_list = detection_result.handedness
    annotated_image = np.copy(rgb_image)

    # Loop through the detected hands to visualize
    for idx in range(len(hand_landmarks_list)):
        hand_landmarks = hand_landmarks_list[idx]
        handedness = handedness_list[idx]
        
        # Draw the hand landmarks and connections using modern MediaPipe Tasks API
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=hand_landmarks,
            connections=HandLandmarksConnections.HAND_CONNECTIONS,
            landmark_drawing_spec=drawing_styles.get_default_hand_landmarks_style(),
            connection_drawing_spec=drawing_styles.get_default_hand_connections_style()
        )

        # Label the hand with handedness at the wrist (landmark index 0)
        if hand_landmarks:
            wrist = hand_landmarks[0]
            height, width, _ = annotated_image.shape
            x_pos = int(wrist.x * width)
            y_pos = int(wrist.y * height) - 15
            
            category = handedness[0]
            label = getattr(category, "category_name", getattr(category, "categoryName", "Unknown"))
            score = category.score
            
            label_text = f"{label} ({score:.2f})"
            
            # Put label shadow for better contrast
            cv2.putText(
                annotated_image,
                label_text,
                (x_pos + 1, y_pos + 1),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2,
                cv2.LINE_AA
            )
            # Put actual white label
            cv2.putText(
                annotated_image,
                label_text,
                (x_pos, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
            
    return annotated_image

def main():
    model_path = "./hand_landmarker.task"
    image_path = sys.argv[1] if len(sys.argv) > 1 else "./download.png"
    base_name, ext = os.path.splitext(os.path.basename(image_path))
    output_path = f"./{base_name}_annotated{ext}"

    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode
    
    try:
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.IMAGE,
            num_hands=4, 
            min_hand_detection_confidence=0.1,  
            min_hand_presence_confidence=0.1
        )
        
        with HandLandmarker.create_from_options(options) as landmarker:
            print(f"Reading input image: {image_path}")
            mp_image = mp.Image.create_from_file(image_path)
            
            print("Detecting hands...")
            detection_result = landmarker.detect(mp_image)
            
            num_hands = len(detection_result.hand_landmarks)
            print(f"Detection complete! Detected {num_hands} hand(s).")
            
            for i, handedness in enumerate(detection_result.handedness):
                category = handedness[0]
                label = getattr(category, "category_name", getattr(category, "categoryName", "Unknown"))
                score = category.score
                print(f" -> Hand {i+1}: Class = {label}, Confidence = {score:.4f}")
            
            rgb_image = mp_image.numpy_view()
            
            if rgb_image.shape[2] == 4:
                rgb_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGBA2RGB)
            elif rgb_image.shape[2] == 1:
                rgb_image = cv2.cvtColor(rgb_image, cv2.COLOR_GRAY2RGB)
            
            if num_hands > 0:
                print("Drawing landmarks and connections...")
                annotated_image = draw_landmarks_on_image(rgb_image, detection_result)
            else:
                print("No hands were detected by the model.")
                print("Saving the original image without modifications.")
                annotated_image = rgb_image
            
            # Convert from RGB to BGR before saving with OpenCV
            bgr_image = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)
            cv2.imwrite(output_path, bgr_image)
            print(f"Success! Output image saved as: {output_path}")
            print("=" * 60)
            
    except Exception as e:
        print(f"An error occurred during hand detection: {e}")
        print("=" * 60)

if __name__ == "__main__":
    main()
