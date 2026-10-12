"""Summarize only the bounded fresh SRAM observation, without board access."""
import argparse
import json
from pathlib import Path
import re
import statistics


def summarize(receipt):
    text = ''.join(e['text'] for e in receipt['events'] if e['state']=='log_chunk')
    end = [e for e in receipt['events'] if e['state']=='observed']
    captures = {}
    for camera in range(1,7):
        rates = re.findall(r'\[capture\] camera='+str(camera)+r' delivered_fps=([\d.]+) tag_advance_rate=([\d.]+)',text)
        traffic = re.findall(r'\[capture-traffic\] camera='+str(camera)+r' .*',text)
        fields = [dict(re.findall(r'(\w+)=([\d.]+)',line)) for line in traffic]
        frames = sum(int(f['delivered_frames']) for f in fields)
        seconds = sum(float(f['seconds']) for f in fields)
        captures[str(camera)] = dict(samples=len(rates), mean_delivered_fps=statistics.mean(float(r[0]) for r in rates) if rates else None,
            mean_tag_advance_rate=statistics.mean(float(r[1]) for r in rates) if rates else None,
            delivered_frames=frames, measured_seconds=seconds, weighted_delivered_fps=frames/seconds if seconds else None,
            read_errors=sum(int(f['read_errors']) for f in fields), unstable=sum(int(f['unstable']) for f in fields))
    motion = [dict(re.findall(r'(\w+)=(\d+)',line)) for line in text.splitlines() if '[motion-traffic]' in line]
    infer = [dict(re.findall(r'(\w+)=([\d.]+)',line)) for line in text.splitlines() if '[infer-perf]' in line]
    generations = [int(v) for v in re.findall(r'\bgeneration=(\d+)',text)]
    error_lines = [line for line in text.splitlines() if re.search(r'EGL_BAD|\[motion-error\]|\[recover\]|read failed|failed to.*EGL',line,re.I)]
    return dict(observation_status=receipt['status'], seconds=end[-1]['seconds'] if end else None,
        cameras=captures, all_six_fresh=all(c['delivered_frames']>0 for c in captures.values()),
        rate_target_met=all(c['weighted_delivered_fps'] is not None and c['weighted_delivered_fps'] >= (.95*(30 if n in ('3','4') else 40)) for n,c in captures.items()),
        motion_first=motion[0] if motion else None, motion_last=motion[-1] if motion else None,
        policy_generation_first=generations[0] if generations else None,policy_generation_last=generations[-1] if generations else None,
        inference_samples=infer,error_lines=error_lines,
        motion_record_limit='Existing viewer logs do not expose each bitmap/count/bbox or CAM5/6 reserved word; no additional DMA reader was opened.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt',type=Path)
    args=parser.parse_args()
    result=summarize(json.loads(args.receipt.read_text(encoding='utf-8')))
    output=args.receipt.with_suffix('.summary.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
