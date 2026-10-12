"""逐行实报告解析：Slack提交；corner仅PathType；reset按行首check。"""
import re
def records(path):
    record=None
    with path.open('rb') as stream:
        for raw in stream:
            line=raw.decode('ascii',errors='backslashreplace').strip()
            if line.startswith('Startpoint') and ':' in line:
                record={'start':line.split(':',1)[1].strip().split(' (',1)[0], 'end':None,
                        'kind':None,'path_class':None,'corner':None,'check':None,'exception':None,
                        'slack':None,'launch_clock':None,'capture_clock':None}
            if record is None:continue
            for prefix,key in [('Endpoint','end'),('Path Type','kind'),('Path Class','path_class'),('Timing Exception','exception')]:
                if line.startswith(prefix) and ':' in line:
                    value=line.split(':',1)[1].strip()
                    record[key]=value.split(' (',1)[0] if key=='end' else value
                    if key=='kind':
                        m=re.search(r'\b(slow|fast)\s+corner\b',value,re.I)
                        record['corner']=m[1].capitalize() if m else None
            if re.match(r'^Recovery\s+time\s',line,re.I):record['check']='Recovery'
            elif re.match(r'^Removal\s+time\s',line,re.I):record['check']='Removal'
            elif re.match(r'^Setup\s+time\s',line,re.I):record['check']='Setup'
            elif re.match(r'^Hold\s+time\s',line,re.I):record['check']='Hold'
            m=re.match(r'^Clock\s+([\w]+)\s+\(',line)
            if m:
                if record['launch_clock'] is None:record['launch_clock']=m[1]
                record['capture_clock']=m[1]
            m=re.search(r'^Slack\s+\((?:MET|VIOLATED)\)\s+([-+0-9.]+)',line,re.I)
            if m:
                record['slack']=float(m[1]);yield record;record=None
def validate_logs(paths):
    bad=[];counts={}
    for path in paths:
        if not path.exists():raise RuntimeError('缺实际 target 日志：'+str(path))
        total=0
        with path.open('rb') as stream:
            for n,line in enumerate(stream,1):
                if b'Timing-4006' in line or b'STA-3016' in line or re.search(rb'unknown\s+(?:arguments?|options?)',line,re.I):
                    total+=1
                    if len(bad)<50:bad.append({'path':str(path),'line':n,'text':line.decode('ascii',errors='backslashreplace').strip()})
        counts[str(path)]=total
    return {'passed':not any(counts.values()),'counts':counts,'errors':bad}
