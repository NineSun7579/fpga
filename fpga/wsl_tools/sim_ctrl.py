# PC-simulator ground-truth test: run the rknn on x86 sim + my e2e decode
from rknn.api import RKNN
import numpy as np
MODEL = '/mnt/c/Users/NineSun/Desktop/ov56401/control_model/yolo26n_ctrl_fp16.rknn'
IMG   = '/mnt/c/Users/NineSun/Desktop/ov56401/test_car.ppm'
rknn = RKNN(verbose=False)
ret = rknn.load_rknn(MODEL)
if ret != 0: print('load_rknn fail', ret); sys.exit(1)
ret = rknn.init_runtime(target=None)   # x86 simulator
if ret != 0: print('init_runtime fail', ret); sys.exit(1)
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
img = read_ppm(IMG)                      # RGB already
canvas = np.zeros((640, 640, 3), np.uint8)
canvas[80:560, :, :] = img
ret = rknn.inference(inputs=[np.expand_dims(canvas, 0)])
if isinstance(ret, tuple): outputs = ret[0]
else: outputs = ret
out = outputs[0] if isinstance(outputs, list) else outputs
print('output shape:', np.array(out).shape)
o = np.array(out).reshape(-1)
print('first 18:', np.round(o[:18], 3).tolist())
# e2e decode: rows [1,300,6] = x1,y1,x2,y2,score,cls
o2 = np.array(out).reshape(300, 6)
mask = o2[:, 4] > 0.25
print('boxes >0.25:', int(mask.sum()))
for r in o2[mask][:10]:
    print('  x1=%.0f y1=%.0f x2=%.0f y2=%.0f score=%.3f cls=%d' % (r[0], r[1], r[2], r[3], r[4], int(r[5])))
print('max score:', float(o2[:,4].max()))
rknn.release()
