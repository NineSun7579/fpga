"""User-run chessboard calibration helper; does not write application flags."""
import argparse,json,os
from pathlib import Path
import cv2
import numpy as np

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images',type=Path,required=True)
    parser.add_argument('--cols',type=int,required=True,help='Inner corner columns')
    parser.add_argument('--rows',type=int,required=True,help='Inner corner rows')
    parser.add_argument('--square-mm',type=float,required=True)
    parser.add_argument('--lens',choices=['pinhole','fisheye'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.cols<3 or args.rows<3 or not np.isfinite(args.square_mm) or args.square_mm<=0:
        parser.error('Use at least3x3 inner corners and a positive measured square size')
    if not args.images.is_dir():parser.error('Image directory does not exist')
    if args.output.exists():parser.error('Output exists; choose a new filename to preserve it')
    pattern=(args.cols,args.rows)
    points=np.zeros((args.rows*args.cols,3),np.float32)
    points[:,:2]=np.mgrid[0:args.cols,0:args.rows].T.reshape(-1,2)*args.square_mm
    object_points=[];image_points=[];used=[];skipped=[]
    for path in sorted(args.images.iterdir()):
        if path.suffix.lower() not in ['.png','.jpg','.jpeg','.bmp','.tif','.tiff']:continue
        image=cv2.imread(str(path))
        if image is None:skipped.append({'file':path.name,'reason':'Cannot read image'});continue
        if image.shape[:2]!=(480,640):
            skipped.append({'file':path.name,'reason':'Expected640x480; retain original capture dimensions'});continue
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        found,corners=cv2.findChessboardCorners(gray,pattern,cv2.CALIB_CB_ADAPTIVE_THRESH|cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not found:skipped.append({'file':path.name,'reason':'Chessboard corners not found'});continue
        corners=cv2.cornerSubPix(gray,corners,(11,11),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,50,.001))
        object_points.append(points.copy());image_points.append(corners);used.append(path.name)
    if len(used)<12:parser.error(f'Only{len(used)} usable images; need at least12 varied images, prefer15–25')
    size=(640,480)
    if args.lens=='fisheye':
        objects=[p.astype(np.float64).reshape(1,-1,3) for p in object_points]
        observations=[p.astype(np.float64).reshape(1,-1,2) for p in image_points]
        rms,K,D,rvecs,tvecs=cv2.fisheye.calibrate(objects,observations,size,np.eye(3),np.zeros((4,1)),flags=cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC|cv2.fisheye.CALIB_FIX_SKEW,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,100,1e-8))
        project=lambda i:cv2.fisheye.projectPoints(objects[i],rvecs[i],tvecs[i],K,D)[0]
    else:
        rms,K,D,rvecs,tvecs=cv2.calibrateCamera(object_points,image_points,size,None,None)
        project=lambda i:cv2.projectPoints(object_points[i],rvecs[i],tvecs[i],K,D)[0]
    if not np.isfinite(K).all() or not np.isfinite(D).all() or not np.isfinite(rms):raise RuntimeError('Calibration produced invalid parameters')
    errors=[]
    for i,name in enumerate(used):
        delta=project(i).reshape(-1,2)-image_points[i].reshape(-1,2)
        errors.append({'file':name,'rms_px':float(np.sqrt(np.mean(np.sum(delta*delta,axis=1))))})
    distortion=D.ravel().tolist()
    record={'lens':args.lens,'resolution':[640,480],'K':K.ravel().tolist(),'D':distortion+[0.0]*(8-len(distortion)),'distortionCount':len(distortion),'overall_rms_px':float(rms),'board_inner_corners':[args.cols,args.rows],'square_mm':args.square_mm,'usable_images':len(used),'per_image':errors,'skipped':skipped,'application_calibration_flags_written':False,'note':'Inspect independent rectified images and errors before copying K/D into the corresponding camera configuration. This file is not a complete six-camera application configuration.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_name(args.output.name+'.tmp')
    temporary.write_text(json.dumps(record,indent=2),encoding='utf-8');os.replace(temporary,args.output)
    print(f'Usable images={len(used)}, RMS={rms:.4f}px. Saved{args.output}; application flags remain unchanged.')

if __name__=='__main__':main()
