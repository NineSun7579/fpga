"""Extract actual old wbin5 -> WADM4 paths from fresh physical experiment STA."""
import hashlib
import json
import os
from pathlib import Path
import re

root = Path(os.environ['LOCALAPPDATA']) / 'Temp/sta50k_holdexperiment'
report = root / 'report_timing/hdmi_ddr_ov5640_top.rtr'
records = []
block = []
start_line = 0


def consume(lines, line_number):
    text = ''.join(lines)
    if ('u_cam2_merge/u_afifo/wbin[5]/opit_0_inv_A2Q21/CLK' not in text
            or not re.search(r'^Endpoint\s*:.*u_cam2_merge/u_afifo/.*/WADM4', text, re.M)):
        return
    def field(name):
        match = re.search(r'^' + name + r'\s*:\s*(.*)', text, re.M)
        return match.group(1).strip() if match else None
    slack = re.search(r'Slack \((MET|VIOLATED)\)\s+(-?\d+\.\d+)', text)
    records.append({'line': line_number, 'startpoint': field('Startpoint'),
                    'endpoint': field('Endpoint'), 'type': field('Path Type'),
                    'group': field('Path Group'),
                    'slack_ns': float(slack.group(2)) if slack else None,
                    'uncertainty': re.findall(r'clock uncertainty\s+(-?\d+\.\d+)', text)})


with report.open(encoding='utf-8', errors='replace') as stream:
    for number, line in enumerate(stream, 1):
        if line.startswith('Startpoint'):
            consume(block, start_line)
            block = []
            start_line = number
        block.append(line)
    consume(block, start_line)
result = {'report': str(report), 'paths': records}
(root / 'hold_path_evidence.json').write_text(json.dumps(result, indent=2), encoding='ascii')
for corner in ('slow', 'fast'):
    selected = [r for r in records if r['type'] == 'min (' + corner + ' corner)']
    print(corner, 'wbin5 WADM4 min paths:', len(selected))
    for r in selected:
        if any('/' + endpoint + '/' in r['endpoint'] for endpoint in
               ('mem_20_6', 'mem_29_11', 'mem_29_14', 'mem_17_8', 'mem_29_8')):
            print(json.dumps(r))
    if selected:
        print('worst:', min(r['slack_ns'] for r in selected))
for path in (report, root / 'place_route/hdmi_ddr_ov5640_top_pnr.adf'):
    print(path.name, hashlib.sha256(path.read_bytes()).hexdigest())
