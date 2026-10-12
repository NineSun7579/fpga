"""Read viewer full-frame capture and GPU-upload statistics after acceptance."""
from pathlib import Path
import json
import re
import shlex
import statistics
from board_host import ssh_connect

ROOT = Path(__file__).resolve().parents[2]
launch = json.loads((ROOT / 'log/50k_fps40_launch.json').read_text())
archive = Path(launch['archive'])
tag = archive.name.removeprefix('bitstream_final_50k_')
out = ROOT / 'log' / ('six_fps40_board_' + tag)
out.mkdir(exist_ok=True)
c = ssh_connect(timeout=8)
try:
    command = 'cat /root/ov5640/camview_fps_candidate.log; pgrep -a -x camview'
    stdin,stdout,stderr = c.exec_command('sudo -S sh -c ' + shlex.quote(command),timeout=20)
    stdin.write('123456\n'); stdin.flush()
    text = stdout.read().decode('utf8','replace')
    errors = stderr.read()
    if stdout.channel.recv_exit_status():
        raise RuntimeError(errors.decode(errors='replace'))
finally:
    c.close()
(out / 'viewer_runtime.txt').write_text(text,encoding='utf8')
rows=[]
for camera in range(1,7):
    samples = re.findall(r'capture camera=%d seconds=([\d.]+) frames=(\d+) delivered_fps=([\d.]+) sequence_fps=([\d.]+) read_ms=([\d.]+) dma_ms=([\d.]+) unstable=(\d+)' % camera,text)
    samples = samples[1:]  # omit startup window
    seconds=sum(float(s[0]) for s in samples)
    frames=sum(int(s[1]) for s in samples)
    uploads=[float(v) for v in re.findall(r'(?:upload|present) camera=%d fps=([\d.]+)' % camera,text)][1:]
    rows.append({'camera':camera,'seconds':seconds,'complete_frames':frames,
        'complete_fps':frames/seconds if seconds else None,
        'sequence_fps_median':statistics.median(float(s[3]) for s in samples) if samples else None,
        'unstable_total':sum(int(s[6]) for s in samples),
        'gpu_upload_fps_median':statistics.median(uploads) if uploads else None})
result={'cameras':rows,'capture_target_pass':all(r['seconds']>=20 and r['complete_fps']>=40 for r in rows if r['camera'] in (5,6)),
        'note':'Complete tagged frame reads measured separately from GPU uploads; display40fps is not asserted.'}
(out / 'viewer_fps.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
