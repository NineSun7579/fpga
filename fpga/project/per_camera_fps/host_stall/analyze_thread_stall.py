"""Summarize host-only JSONL; runtime/wait values retain explicit units."""
import collections
import json
import pathlib
import re
import statistics
import sys

def numbers(text):
    return [int(value) for value in (text or '').split()]

def fields(text):
    result = {}
    for line in (text or '').splitlines():
        parts = line.replace(':', '').split()
        if len(parts) >= 2:
            try: result[parts[0]] = int(parts[1])
            except ValueError: pass
    return result

def distribution(values):
    ordered = sorted(values)
    if not ordered: return None
    return dict(min=min(values),mean=statistics.mean(values),p95=ordered[int((len(ordered)-1)*.95)],max=max(values))

def main(path):
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    start = next(value for value in records if value['kind']=='start')
    end = next((value for value in records if value['kind']=='end'), {})
    samples = [value for value in records if value['kind']=='sample']
    elapsed = samples[-1]['monotonic']-samples[0]['monotonic']
    hz = start['hz']; thread_report=[]
    for tid in sorted(set().union(*(value['threads'] for value in samples)),key=int):
        seen = [value['threads'][tid] for value in samples if tid in value['threads']]
        runtime=wait=slices=ticks=voluntary=involuntary=0; intervals=[]
        for before,after in zip(samples,samples[1:]):
            a=before['threads'].get(tid); b=after['threads'].get(tid)
            if not a or not b or a['start']!=b['start']:continue
            dt=after['monotonic']-before['monotonic']; ticks+=b['ticks']-a['ticks']
            sa=numbers(a['schedstat']);sb=numbers(b['schedstat'])
            if len(sa)==3 and len(sb)==3:
                dr=sb[0]-sa[0];dw=sb[1]-sa[1];ds=sb[2]-sa[2]
                runtime+=dr;wait+=dw;slices+=ds
                intervals.append(dict(index=after['index'],runtime_ms=dr/1e6,runnable_wait_ms=dw/1e6,wall_ms=dt*1000,wchan=b['wchan'],state=b['state']))
            ast=fields(a['status']);bst=fields(b['status'])
            voluntary+=bst.get('voluntary_ctxt_switches',0)-ast.get('voluntary_ctxt_switches',0)
            involuntary+=bst.get('nonvoluntary_ctxt_switches',0)-ast.get('nonvoluntary_ctxt_switches',0)
        thread_report.append(dict(tid=tid,name=seen[-1]['name'],cpu_percent_one_core=100*ticks/hz/elapsed,runtime_seconds=runtime/1e9,runnable_wait_seconds=wait/1e9,timeslices=slices,voluntary_switches=voluntary,involuntary_switches=involuntary,states=dict(collections.Counter(value['state'] for value in seen)),wchans=dict(collections.Counter(value['wchan'] for value in seen)),runtime_interval_ms=distribution([value['runtime_ms'] for value in intervals]),wait_interval_ms=distribution([value['runnable_wait_ms'] for value in intervals]),top_wait_intervals=sorted(intervals,key=lambda value:value['runnable_wait_ms'],reverse=True)[:5]))
    thread_report.sort(key=lambda value:value['cpu_percent_one_core'],reverse=True)
    process_report=[]
    for pid,b in samples[-1]['processes'].items():
        a=samples[0]['processes'].get(pid)
        if a and a['start']==b['start']:
            process_report.append(dict(pid=pid,name=b['name'],cpu_percent_one_core=100*(b['ticks']-a['ticks'])/hz/elapsed,major_fault_delta=b['majflt']-a['majflt']))
    process_report.sort(key=lambda value:value['cpu_percent_one_core'],reverse=True)
    def cpu(value):
        return numbers(value['system']['stat'].splitlines()[0][4:])
    delta=[b-a for a,b in zip(cpu(samples[0]),cpu(samples[-1]))];total=sum(delta[:8])
    sysfirst=fields(samples[0]['system']['stat']);syslast=fields(samples[-1]['system']['stat'])
    vmfirst=fields(samples[0]['system']['vmstat']);vmlast=fields(samples[-1]['system']['vmstat'])
    logevents=[]; line_metrics=collections.defaultdict(list); camera_fps=collections.defaultdict(list); useful_lines=[]
    for value in samples:
        for log,text in value['log_new'].items():
            logevents.append(dict(time=value['time'],uptime=value['uptime'],sample_index=value['index'],path=log,text=text))
            for line in text.splitlines():
                match=re.search(r'capture_fps=([0-9./]+)',line)
                if match:
                    for camera,number in enumerate(match.group(1).split('/'),1):camera_fps[str(camera)].append(float(number))
                if any(word in line for word in ('copy=','dma=','delivered=','[stereo]','[capture','[display]')):
                    useful_lines.append(dict(sample_index=value['index'],time=value['time'],line=line))
                if any(tag in line for tag in ('[capture','[panes]','[stereo]','[display','[tdm]')):
                    for key,number in re.findall(r'([A-Za-z_][A-Za-z_0-9]*)=([0-9]+(?:\.[0-9]+)?)',line):
                        tag=line.split(']')[0]+']';name=re.search(r'name=(\w+)',line)
                        line_metrics[tag+(name.group(1) if name else '')+'.'+key].append(float(number))
    logs_path=path.with_suffix('.viewer_logs.jsonl')
    logs_path.write_text(''.join(json.dumps(value,ensure_ascii=False)+'\n' for value in logevents),encoding='utf-8')
    identitykeys=('pid','start','exe','exe_sha256','argv','config_sha256','environ_sha256','dma_owners')
    comparison={key:start['identity'].get(key)==end.get('identity',{}).get(key) for key in identitykeys}
    report=dict(raw=str(path),seconds=elapsed,samples=len(samples),start_identity=start['identity'],end_identity=end.get('identity'),identity_matches=comparison,schedstats_flag=start['schedstats'],schedstat_units=start['schedstat_units'],schedstat_wait_positive_observed=any(value['runnable_wait_seconds']>0 for value in thread_report),threads=thread_report,top_processes=process_report[:15],system=dict(cpu_idle_percent=100*delta[3]/total,cpu_iowait_percent=100*delta[4]/total,cpu_irq_percent=100*delta[5]/total,cpu_softirq_percent=100*delta[6]/total,context_switches_per_second=(syslast['ctxt']-sysfirst['ctxt'])/elapsed,pgfault_delta=vmlast['pgfault']-vmfirst['pgfault'],pgmajfault_delta=vmlast['pgmajfault']-vmfirst['pgmajfault'],runnable_count=distribution([int(value['system']['loadavg'].split()[3].split('/')[0]) for value in samples]),mem_available_kb=distribution([fields(value['system']['meminfo'])['MemAvailable'] for value in samples]),frequency={key:distribution([int(value['system']['frequency'][key]) for value in samples if value['system']['frequency'].get(key)]) for key in samples[0]['system']['frequency']},thermal={key:distribution([int(value['system']['thermal'][key]) for value in samples if value['system']['thermal'].get(key)]) for key in samples[0]['system']['thermal'] if key.endswith('/temp')},pressure_available={key:samples[0]['system']['pressure'][key] is not None for key in ('cpu','io','memory')}),collector_cpu_seconds=end.get('collector_cpu_seconds'),collector_work_seconds=distribution([value['collector_work_seconds'] for value in samples]),viewer_log_events=len(logevents),viewer_logs=str(logs_path),log_metric_distributions={key:distribution(values) for key,values in line_metrics.items()})
    def interrupts(text):
        result={}
        for line in (text or '').splitlines():
            if ':' not in line:continue
            key,tail=line.split(':',1);parts=tail.split();counts=[]
            for part in parts:
                if part.isdigit():counts.append(int(part))
                else:break
            if counts:result[key.strip()]={'count':sum(counts),'description':' '.join(parts[len(counts):])}
        return result
    irqfirst=interrupts(samples[0]['system']['interrupts']);irqlast=interrupts(samples[-1]['system']['interrupts'])
    report['system']['top_irq_rates']=sorted([dict(irq=key,description=value['description'],per_second=(value['count']-irqfirst[key]['count'])/elapsed) for key,value in irqlast.items() if key in irqfirst],key=lambda value:value['per_second'],reverse=True)[:15]
    report['camera_capture_fps']={key:distribution(values) for key,values in camera_fps.items()}
    report['useful_viewer_lines']=useful_lines
    out=path.with_suffix('.summary.json');out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(summary=str(out),seconds=elapsed,identity_matches=comparison,schedstats_flag=start['schedstats'],threads=[{key:value[key] for key in ('tid','name','cpu_percent_one_core','runtime_seconds','runnable_wait_seconds','voluntary_switches','involuntary_switches','wchans')} for value in thread_report],system=report['system'],viewer_log_events=len(logevents),collector_cpu_seconds=report['collector_cpu_seconds']),indent=2))

if __name__=='__main__': main(pathlib.Path(sys.argv[1]))
