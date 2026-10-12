from pathlib import Path
import json,numpy as np
from PIL import Image
root=Path(__file__).resolve().parent/'board_evidence'
a=np.asarray(Image.open(root/'cam3_wire_320x240.png').convert('RGB'));b=np.asarray(Image.open(root/'cam4_wire_320x240.png').convert('RGB'))
actual=np.asarray(Image.open(root/'cam34_input_640x480.png').convert('RGB'))
assert a.shape==b.shape==(240,320,3)and actual.shape==(480,640,3)
expected=np.full((480,640,3),114,dtype=np.uint8);expected[120:360,:320]=a;expected[120:360,320:]=b
wrong=int(np.count_nonzero(expected!=actual));feed=Image.open(root/'actual_rknn_input.png')
ids=[json.loads((root/f'cam{c}_dma_identity.json').read_bytes())for c in [3,4]]
row={'on_wire_camera_size':[320,240],'expected_compressed_pixel_bytes':153600,'model_input_size':list(feed.size),'model_rgb_bytes':int(actual.size),'composition_mismatch_bytes':wrong,'distinct_camera_content':not np.array_equal(a,b),'cam3_stddev':float(a.std()),'cam4_stddev':float(b.std()),'dma_identity':ids,'hardware_parity_scope':'full RTL golden 2x2 test; live wire-to-model composition byte parity; live RAW was not transferred and cannot be asserted same-frame RAW parity'}
(root/'pixel_verification.json').write_text(json.dumps(row,indent=2),encoding='utf-8');print(json.dumps(row,indent=2))
assert wrong==0 and feed.size==(640,480)and all(x['frame_bytes']==153600 and x['dma_bytes']==153616 for x in ids)
