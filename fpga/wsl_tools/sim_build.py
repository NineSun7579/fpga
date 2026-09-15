# PC-simulator: convert in-process then infer (standard toolkit flow)
from rknn.api import RKNN
import numpy as np, sys
ONNX = '/mnt/c/Users/NineSun/Desktop/HT/tableware.v2i.yolov8/yolo26n.onnx'
IMG  = '/mnt/c/Users/NineSun/Desktop/ov56401/test_car.ppm'

def read_ppm(path):
    with open(path, 'rb') as f: data = f.read()
    tok, idx = [], 0
    while len(tok) < 4:
        if data[idx:idx+1].isspace(): idx += 1
        else:
            j = idx
            while not data[j:j+1].isspace(): j += 1
            tok.append(data[idx:j]); idx = j
    w, h = int(tok[1]), int(tok[2]); idx += 1
    return np.frombuffer(data[idx:idx+w*h*3], np.uint8).reshape(h, w, 3)

rknn = RKNN(verbose=False)
rknn.config(mean_values=[[0,0,0]], std_values=[[255,255,255]], target_platform='rk3568')
if rknn.load_onnx(model=ONNX) != 0: print('load fail'); sys.exit(1)
if rknn.build(do_quantization=False) != 0: print('build fail'); sys.exit(1)
if rknn.init_runtime(target=None) != 0: print('init_runtime fail'); sys.exit(1)

img = read_ppm(IMG)
canvas = np.zeros((640, 640, 3), np.uint8)
canvas[80:560, :, :] = img
ret = rknn.inference(inputs=[np.expand_dims(canvas, 0)])
outs = ret[0] if isinstance(ret, tuple) else ret
out = outs[0] if isinstance(outs, list) else outs
o = np.array(out)
print('SIM output shape:', o.shape)
flat = o.reshape(-1)
print('first 18:', np.round(flat[:18], 3).tolist())
o2 = o.reshape(300, 6)
print('max score:', float(o2[:,4].max()), '| boxes>0.25:', int((o2[:,4] > 0.25).sum()))
for r in o2[o2[:,4] > 0.25][:10]:
    print('  x1=%.0f y1=%.0f x2=%.0f y2=%.0f score=%.3f cls=%d' % (r[0],r[1],r[2],r[3],r[4],int(r[5])))
rknn.release()
