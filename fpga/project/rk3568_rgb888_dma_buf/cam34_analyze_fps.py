"""Compute measured fresh capture/display/inference rates from RK3568 logs."""
from pathlib import Path
import json,re,statistics
root=Path(__file__).resolve().parent/'cam34_board_evidence'
text=(root/'runtime.log').read_text(encoding='utf-8',errors='replace')
stats=[];panes=[];pairs=[];windows=[];uploads={3:[],4:[]};detection_frames={3:set(),4:set()};inference=[]
for line in text.splitlines():
 if line.startswith('[stats] '):stats.append({k:float(v) for k,v in re.findall(r'([A-Za-z_]+)=([0-9.]+)',line)})
 elif line.startswith('[panes] '):
  m=re.search(r'capture_fps=([0-9./]+)',line)
  if m:panes.append(([float(x) for x in m[1].split('/')],len(stats)))
 elif line.startswith('[cam34-pair] '):
  m=re.search(r'frames=(\d+) host_ms=(\d+)',line)
  if m:pairs.append((int(m[1]),int(m[2])))
 elif line.startswith('[display-perf] '):
  row={k:float(v) for k,v in re.findall(r'([A-Za-z_]+)=([0-9.]+)',line)};windows.append(row)
 elif line.startswith('[display-upload] '):
  m=re.search(r'camera=(\d+) count=(\d+)',line)
  if m and int(m[1]) in uploads and windows:uploads[int(m[1])].append((int(m[2]),windows[-1]['seconds']))
 elif line.startswith('[cam34-detections] '):
  d=json.loads(line.split(' ',1)[1]);inference.append(d['inference_ms'])
  for box in d['boxes']:detection_frames[box['camera']].add(d['frame'])
# Discard the first 10 seconds of aggregate windows and initial capture reports.
stable_stats=stats[2:];stable_panes=[values for values,windows_seen in panes if windows_seen>=2]
def summarize(values):
 return {'mean':statistics.mean(values),'minimum':min(values),'maximum':max(values),'samples':len(values)} if values else None
result={'model_input_lines':[l for l in text.splitlines() if '[cam34-network]' in l],
 'model_tensor_lines':[l for l in text.splitlines() if 'input[0]' in l],
 'stats_windows_total':len(stats),'stats_windows_after_startup':len(stable_stats),
 'fresh_capture_fps':{'cam3':summarize([v[2] for v in stable_panes]),'cam4':summarize([v[3] for v in stable_panes])},
 'fresh_display_fps':{},'pipeline_fps':{},'inference_ms':summarize(inference[20:]),
 'frames_with_detections_by_camera':{str(k):len(v) for k,v in detection_frames.items()},
 'driver_error_lines':[l for l in text.splitlines() if '[diag]' in l or 'FATAL' in l or 'QUARANTINE' in l],
 'last_panes': [l for l in text.splitlines() if l.startswith('[panes]')][-1:]}
for camera,rows in uploads.items():
 rows=rows[2:];seconds=sum(s for _,s in rows)
 result['fresh_display_fps']['cam'+str(camera)]={'fps':sum(n for n,_ in rows)/seconds if seconds else None,'fresh_uploads':sum(n for n,_ in rows),'seconds':seconds}
for k in ['take_fps','upload_new_fps','paint_new_fps','npu_request_fps','npu_started_fps','npu_completed_fps','npu_failed_fps','infer_service_ms']:
 result['pipeline_fps'][k]=summarize([s[k] for s in stable_stats])
if len(pairs)>2:
 first=next(v for v in pairs if v[1]>=pairs[0][1]+10000);last=pairs[-1];result['accepted_pair_fps']={'fps':(last[0]-first[0])*1000/(last[1]-first[1]),'pairs':last[0]-first[0],'seconds':(last[1]-first[1])/1000}
(root/'fps_summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
