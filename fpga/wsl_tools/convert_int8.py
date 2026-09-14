from rknn.api import RKNN
import sys
ONNX = '/mnt/c/Users/NineSun/Desktop/HT/tableware.v2i.yolov8/yolo26n.onnx'
OUT  = '/mnt/c/Users/NineSun/Desktop/ov56401/control_model/yolo26n_ctrl_i8.rknn'
DS   = '/mnt/c/Users/NineSun/Desktop/ov56401/calib_png/dataset_linux.txt'
rknn = RKNN(verbose=False)
rknn.config(mean_values=[[0,0,0]], std_values=[[255,255,255]], target_platform='rk3568')
if rknn.load_onnx(model=ONNX) != 0: sys.exit(1)
if rknn.build(do_quantization=True, dataset=DS) != 0: sys.exit(1)
if rknn.export_rknn(OUT) != 0: sys.exit(1)
print('I8 CONVERT OK:', OUT)
