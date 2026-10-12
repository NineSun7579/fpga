"""Three complete-window observations; a single cycle is not whole-system acceptance."""
import argparse,json,re,statistics
from pathlib import Path
from summarize_fresh_display import summarize as fresh
from summarize_infer_age import summarize as ages
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('trial',type=Path);args=parser.parse_args()
trial=json.loads((args.trial/'trial.json').read_text())
assert trial['phase']=='complete_original_restored','Trial incomplete; inspect recovery before comparing'
result={'trial':str(args.trial),'original_sha256':trial['original_sha256'],'restored_identity':trial['flipfb_original_restored']['identity'],'observations':{}}
for label in ('flipfb_original_before','flipfb_off','flipfb_original_restored'):
    actual=(trial.get('sample_prefix','')+'_' if trial.get('sample_prefix') else '')+label
    text=(root/(actual+'_sample_window.log')).read_text(errors='replace')
    display=fresh(text);age=ages(text)
    capture={}
    for cam in range(1,7):
        values=[float(v) for v in re.findall(r'\[capture\] camera='+str(cam)+r' delivered_fps=([\d.]+)',text)]
        capture[str(cam)]={'mean_fps':statistics.mean(values) if values else None,'samples':len(values)}
    values=[float(v) for v in re.findall(r'npu_completed_fps=([\d.]+)',text)]
    xorg=(args.trial/(label+'.xorg.log')).read_text(errors='replace')
    window=args.trial/(label+'.xorg_window.log')
    result['observations'][label]={'fresh_display':display,'capture':capture,'inference_fps':statistics.mean(values) if values else None,'cpu':json.loads((root/(actual+'_cpu.json')).read_text()),'source_age':age,'xorg_flip_config':[line for line in xorg.splitlines() if 'FlipFB:' in line or 'Option "FlipFB"' in line],'xorg_log_timeout_count':len(re.findall('flip timeout!',xorg)),'matched_xorg_timeouts':len(re.findall('flip timeout!',window.read_text())) if window.exists() else None}
result['limits']='Each phase follows a different Xorg uptime; restart itself is a confound. Timeout counts cover saved Xorg logs, not matched 180s intervals. Upload freshness is not scanout or optical latency. Missing age events remain unavailable.'
output=json.dumps(result,indent=2)
(args.trial/'comparison.json').write_text(output)
for label,row in result['observations'].items():
    fps=[round(row['fresh_display']['cameras'][str(c)]['weighted_fps'],2) for c in (1,2,5,6)]
    print(label,json.dumps({'fresh_c1_c2_c5_c6':fps,'cpu_percent':row['cpu']['cpu_percent'],'inference_fps':row['inference_fps'],'flip_config':row['xorg_flip_config']}))
