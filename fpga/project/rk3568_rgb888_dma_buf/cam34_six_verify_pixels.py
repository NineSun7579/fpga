"""Verify downloaded camera RAW/composite evidence byte for byte."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parent/'cam34_six_board_evidence'
a=np.asarray(Image.open(root/'cam3_raw_640x480.png').convert('RGB'),dtype=np.uint16)
b=np.asarray(Image.open(root/'cam4_raw_640x480.png').convert('RGB'),dtype=np.uint16)
actual=np.asarray(Image.open(root/'cam34_input_640x480.png').convert('RGB'),dtype=np.uint8)
assert a.shape==b.shape==actual.shape==(480,640,3)
def shrink(v):return ((v[0::2,0::2,:]+v[0::2,1::2,:]+v[1::2,0::2,:]+v[1::2,1::2,:]+2)//4).astype(np.uint8)
expected=np.full((480,640,3),114,dtype=np.uint8)
expected[120:360]=np.concatenate([shrink(a),shrink(b)],axis=1)
wrong=np.count_nonzero(expected!=actual)
feed=Image.open(root/'actual_rknn_input.png')
result={'source_size':[640,480],'joined_size':[640,480],'actual_rknn_input_size':list(feed.size),'compared_rgb_bytes':actual.size,'mismatch_bytes':int(wrong),'raw_cameras_distinct':not np.array_equal(a,b),'cam3_pixel_stddev':float(np.std(a)),'cam4_pixel_stddev':float(np.std(b))}
(root/'pixel_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
assert wrong==0 and feed.size==(640,480)
