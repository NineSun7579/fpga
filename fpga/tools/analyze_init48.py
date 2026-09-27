from pathlib import Path
import json
import numpy as np
from PIL import Image
out=Path(__file__).resolve().parents[1]/'tp/init48_evidence'
images={};results=[]
for f in sorted(out.glob('*.rgb565')):
    v=np.frombuffer(f.read_bytes(),dtype='<u2').reshape(480,640).astype(np.int32)
    a=np.stack([((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31],axis=-1)
    images[f.stem]=a
    Image.fromarray(a.astype(np.uint8)).save(f.with_suffix('.png'))
    score=np.abs(a[:,1:]-a[:,:-1]).mean(axis=(0,2))
    results.append(dict(file=f.name,seam=int(score.argmax()+1),score=float(score.max()),median=float(np.median(score))))
for cam in (1,2,3):
    for bank in (0,1):
        p='cam%d_bank%d_'%(cam,bank)
        print(p,'temporal MAD',float(np.abs(images[p+'0']-images[p+'2']).mean()))
print(json.dumps(results,indent=2))
(out/'analysis.json').write_text(json.dumps(results,indent=2))
if (out/'screen1.png').exists():
    a=np.asarray(Image.open(out/'screen0.png').convert('RGB')).astype(int)
    b=np.asarray(Image.open(out/'screen1.png').convert('RGB')).astype(int)
    w=a.shape[1]//3
    print('screen panel MAD',[float(np.abs(a[:,i*w:(i+1)*w]-b[:,i*w:(i+1)*w]).mean()) for i in range(3)])
