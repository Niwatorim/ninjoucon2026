import json
import os
import time
import threading
import cv2 as cv
import glob
import numpy as np

#read images
images_folder = "D2/*"

BOARD_SIZE = (6, 4)
SQUARE_SIZE = 0.025  # Meters (2.5 cm)

# Prepare object points (0,0,0), (1,0,0), (2,0,0) ...
objp = np.zeros((BOARD_SIZE[0] * BOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_SIZE[0], 0:BOARD_SIZE[1]].T.reshape(-1, 2)
objp *= SQUARE_SIZE

def capture_thread(cap,frame_list):
    while cap.isOpened():
        ret,frame = cap.read()
        if ret:
            frame_list[0]=frame


def calibrate_camera(images_folder):
    images_name = sorted(glob.glob(images_folder))
    images=[]

    for i in images_name:
        im = cv.imread(i,1)
        images.append(im)

    #detecting checkerboard patterns
    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER,30,0.001) #the frick does this do
    rows = 5
    columns = 8
    world_scaling = 1.

    #coordinates of squares in checkerboard space
    objp = np.zeros((rows*columns,3),np.float32)
    objp[:,:2] = np.mgrid[0:rows,0:columns].T.reshape(-1,2)
    objp = world_scaling * objp

    width = images[0].shape[1]
    height = images[0].shape[0]


    imgpoints = [] #points in 2d
    objpoints = [] # points in 3d

    for frame in images:
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        ret, corners = cv.findChessboardCorners(gray,(rows,columns),None)

        if ret == True:
            conv_size = (11,11)
            corners = cv.cornerSubPix(gray, corners,conv_size,(-1,-1),criteria)
            cv.drawChessboardCorners(frame,(rows,columns),corners,ret)
            cv.imshow("img",frame)
            k = cv.waitKey(500)
            objpoints.append(objp)
            imgpoints.append(corners)

    ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, (width, height), None, None)
    print('rmse:', ret)
    print('camera matrix:\n', mtx)
    print('distortion coeffs:', dist)
    print('Rs:\n', rvecs)
    print('Ts:\n', tvecs)
 
    return mtx, dist


def main():
    #open cams
    cap0 = cv.VideoCapture(0)
    cap1 = cv.VideoCapture(1)

    if not cap0.isOpened() or not cap1.isOpened():
        print("Error opening cameras")
        return

    frame0 = [None]
    frame1 = [None]
    t0 = threading.Thread(target=capture_thread,args=(cap0,frame0), daemon=True)
    t1 = threading.Thread(target=capture_thread,args=(cap1,frame1), daemon=True)

    t0.start()
    t1.start()

    objpoints = [] #3d points
    imgpoints0=[] #2d points in cam 0
    imgpoints1=[] #2d points in cam 1

    print("Cameras opened")
    captures = 0 #how many captures we got
    last_capture_time = 0 #last time a capture taken
    cooldown = 1.5 #cooldown till done

    while True:
        if frame0[0] is None or frame1[0] is None:
            continue

        #copy te frames
        f0 = frame0[0].copy()
        f1 = frame1[0].copy()

        gray0 = cv.cvtColor(f0, cv.COLOR_BGR2GRAY)
        gray1 = cv.cvtColor(f1, cv.COLOR_BGR2GRAY)

        ret0, corners0 = cv.findChessboardCorners(gray0,BOARD_SIZE,None)
        ret1, corners1 = cv.findChessboardCorners(gray1,BOARD_SIZE,None)

        if ret0:
            cv.drawChessboardCorners(f0,BOARD_SIZE,corners0,ret0)

        if ret1:
            cv.drawChessboardCorners(f1,BOARD_SIZE,corners1,ret1)

        cv.putText(f0,f"Captures {captures}" ,(10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        current_time = time.time()
        if ret0 and ret1 and (current_time - last_capture_time > cooldown):
            #refine corners
            criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER,30,0.001)

            corners0_ref = cv.cornerSubPix(gray0,corners0, (11,11),(-1,-1),criteria)
            corners1_ref = cv.cornerSubPix(gray1,corners1,(11,11),(-1,-1),criteria)


            imgpoints0.append(corners0_ref)
            imgpoints1.append(corners1_ref)
            objpoints.append(objp)
            captures+=1
            last_capture_time = current_time
            
            #flash for 
            cv.rectangle(f0, (0, 0), (f0.shape[1], f0.shape[0]), (0, 255, 0), 10)
            cv.rectangle(f1, (0, 0), (f1.shape[1], f1.shape[0]), (0, 255, 0), 10)

        cv.imshow("Camera 0 (Webcam)", f0)
        cv.imshow("Camera 1 (Phone)", f1)

        key = cv.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cv.destroyAllWindows()
    cap0.release()
    cap1.release()


    if captures < 5:
        print("Not enough captures")
        return
    
    print("Math time")

    h,w = gray0.shape #find the size 
    img_size = (w,h)

    ret0, mtx0, dist0, _,_ = cv.calibrateCamera(objpoints, imgpoints0,img_size,None,None)
    ret1, mtx1, dist1, _,_ = cv.calibrateCamera(objpoints, imgpoints1,img_size,None,None)

    print("Stereo stuff idk")
    criteria_stereo = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER,100,1e-5)
    ret_stereo,CM1,dist0_stereo,CM2,dist1_stereo,R,T,E,F = cv.stereoCalibrate(
        objpoints, imgpoints0,imgpoints1,
        mtx0,dist0,mtx1,dist1,img_size,criteria=criteria_stereo,flags=cv.CALIB_FIX_INTRINSIC
    )

    R1,R2,P1,P2,Q,roi1,roi2 = cv.stereoRectify(CM1,dist0_stereo,CM2,dist1_stereo,img_size,R,T)
    calibration_data = {
        "P1": P1.tolist(),
        "P2": P2.tolist(),
        "mtx0": CM1.tolist(),
        "dist0": dist0_stereo.tolist(),
        "mtx1": CM2.tolist(),
        "dist1": dist1_stereo.tolist(),
        "R": R.tolist(),
        "T": T.tolist()
    }


    out_path = os.path.join(os.path.dirname(__file__), "camera_parameters.json")
    with open(out_path, 'w') as f:
        json.dump(calibration_data, f, indent=4)
    
    print(f"Calibration successful! Saved to: {out_path}")
    print(f"Reprojection Error: {ret_stereo}")

if __name__ == "__main__":
    main()




            