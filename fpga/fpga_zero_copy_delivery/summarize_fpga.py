"""Compare actual placement utilization reports after completed builds."""
from pathlib import Path
import json
import re

root=Path(__file__).resolve().parent
baseline=root.parent/'fpga_acceleration_delivery/ddr_rgb_letterbox/integrated/project'
candidate=root/'integrated/project'
report={}
for label,project in [('baseline',baseline),('candidate',candidate),
                      ('six_camera',root/'integrated_six/project')]:
    log=project/'place_route/run.log'
    if not log.exists():
        report[label]={'available':False}
        continue
    text=log.read_bytes().decode('utf-8','replace')
    rows=[]
    for name,used,available,percent in re.findall(r'\|\s*([^|\r\n]+?)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)',text):
        rows.append({'name':name.strip(),'used':float(used),'available':float(available),'reported_percent':float(percent)})
    timing=project/'place_route/top_timing_summary_after_hold_fix.txt'
    report[label]={'available':True,'place_route_success':'placed and routed successfully' in text,
                   'resources':rows,'timing_summary':str(timing) if timing.exists() else None}
    if timing.exists():
        report[label]['timing_text']=timing.read_bytes().decode('utf-8','replace')
(root/'fpga_resources_compare.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({label:{'available':data['available'],'place_route_success':data.get('place_route_success'),
                         'resource_rows':len(data.get('resources',[]))} for label,data in report.items()},indent=2))
