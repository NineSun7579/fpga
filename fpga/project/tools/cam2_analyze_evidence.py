"""Offline raw decode and seam statistics; no deployed code is changed."""
from pathlib import Path
import json, hashlib, struct, statistics
from PIL import Image
out=Path(__file__).resolve().parents[1]/'tp/cam2_evidence_84mhz'
results=[]
for f in sorted(out.glob('*.rgb565')):
    a=struct.unpack('<307200H',f.read_bytes())
    rgb=[(((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31) for v in a]
    im=Image.new('RGB',(640,480)); im.putdata(rgb); im.save(f.with_suffix('.png'))
    def distance(a,b): return sum(abs(x-y) for x,y in zip(a,b))/3
    diff=[sum(distance(rgb[y*640+x-1],rgb[y*640+x]) for y in range(480))/480 for x in range(1,640)]
    top=sorted(range(1,640),key=lambda x:diff[x-1],reverse=True)[:8]
    rec=dict(file=f.name,largest_column_boundaries=top,boundary_errors=[diff[x-1] for x in top],median_boundary_error=statistics.median(diff),wrap_same_row=sum(distance(rgb[y*640+639],rgb[y*640]) for y in range(480))/480,wrap_next_row=sum(distance(rgb[y*640+639],rgb[(y+1)*640]) for y in range(479))/479)
    results.append(rec)
(out/'analysis.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
manifest={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file() and f.name!='sha256.json'}
(out/'sha256.json').write_text(json.dumps(manifest,indent=2))
