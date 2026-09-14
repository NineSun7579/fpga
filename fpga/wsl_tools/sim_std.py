from rknn.api import RKNN
import numpy as np, sys
ONNX = '/mnt/c/Users/NineSun/Desktop/ov56401/control_model/yolo26n_std.onnx'
IMG  = '/mnt/c/Users/NineSun/Desktop/ov56401/test_car.ppm'
def read_ppm(path):
    with open(path,'rb') as f: data=f.read()
    tok,idx=[],0
    while len(tok)<4:
        if data[idx:idx+1].isspace(): idx+=1
        else:
            j=idx
            while not data[j:j+1].isspace(): j+=1
            tok.append(data[idx:j]); idx=j
    w,h=int(tok[1]),int(tok[2]); idx+=1
    return np.frombuffer(data[idx:idx+w*h*3],np.uint8).reshape(h,w,3)
rknn=RKNN(verbose=False)
rknn.config(mean_values=[[0,0,0]],std_values=[[255,255,255]],target_platform='rk3568')
if rknn.load_onnx(model=ONNX)!=0: sys.exit(1)
if rknn.build(do_quantization=False)!=0: sys.exit(1)
if rknn.init_runtime(target=None)!=0: sys.exit(1)
img=read_ppm(IMG)
canvas=np.zeros((640,640,3),np.uint8); canvas[80:560,:,:]=img
ret=rknn.inference(inputs=[np.expand_dims(canvas,0)])
outs=ret[0] if isinstance(ret,tuple) else ret
o=np.array(outs[0] if isinstance(outs,list) else outs)
print('SIM std output shape:', o.shape)
# [1,84,8400]: ch0-3 = cx,cy,w,h ; ch4+ = class scores
t=o.reshape(84,8400)
scores=t[4:,:]
mx=scores.max(axis=0)
print('score max:', float(mx.max()), '| anchors>0.25:', int((mx>0.25).sum()))
top=np.argsort(-mx)[:5]
for a in top:
    cx,cy,w,h = t[0,a],t[1,a],t[2,a],t[3,a]
    print('  a=%d box=(%.0f,%.0f,%.0f,%.0f) cls=%d score=%.3f' % (a,cx-w/2,cy-h/2,cx+w/2,cy+h/2,int(scores[:,a].argmax()),mx[a]))
rknn.release()
