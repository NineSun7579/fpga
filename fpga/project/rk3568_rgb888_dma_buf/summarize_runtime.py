from pathlib import Path
import re,json,statistics,sys
path=Path(sys.argv[1]);text=path.read_text(errors='replace')
all_samples='--all-samples' in sys.argv[2:]
# Verification and performance share an appended board log; exclude verification.
segments=text.split('[display-config]')
text=segments[-1]
summary={}
for camera in range(1,7):
    samples=[float(x) for x in re.findall(r'\[capture\] camera='+str(camera)+r' delivered_fps=([\d.]+)',text)]
    if not all_samples:samples=samples[-12:]
    summary['camera'+str(camera)+'_delivered_fps']={'mean':statistics.mean(samples) if samples else None,'samples':len(samples)}
for name,pattern in [('rknn_completed_fps',r'npu_completed_fps=([\d.]+)'),('paint_fps',r'\bpaint_fps=([\d.]+)'),('lease_ms',r'lease_hold_ms=(\d+)')]:
    values=[float(x) for x in re.findall(pattern,text)]
    if not all_samples:values=values[-100:]
    summary[name]={'mean':statistics.mean(values) if values else None,'samples':len(values)}
print(json.dumps(summary,indent=2))
path.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2))
