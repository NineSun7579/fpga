from rknn.api import RKNN
import sys
ONNX = '/mnt/c/Users/NineSun/Desktop/HT/tableware.v2i.yolov8/yolo26n.onnx'
OUT  = '/mnt/c/Users/NineSun/Desktop/ov56401/control_model/yolo26n_ctrl_fp16.rknn'
rknn = RKNN(verbose=True)
print('-- config')
rknn.config(mean_values=[[0,0,0]], std_values=[[255,255,255]], target_platform='rk3568')
print('-- load onnx')
ret = rknn.load_onnx(model=ONNX)
if ret != 0: print('load_onnx failed', ret); sys.exit(1)
print('-- build (fp16, no quantization)')
ret = rknn.build(do_quantization=False)
if ret != 0: print('build failed', ret); sys.exit(1)
print('-- export')
ret = rknn.export_rknn(OUT)
if ret != 0: print('export failed', ret); sys.exit(1)
print('CONVERT OK:', OUT)
