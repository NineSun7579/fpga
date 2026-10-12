"""Read-only bounded streaming audit; outputs only beside this script."""
from pathlib import Path
import re, json, collections
ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'project/fpga_v8_migration/board_v7'
EXACT = BOARD / 'physical_subagent_evidence_01/fixed_06/physical_exact_09'
manifest = json.loads((EXACT/'actual/analysis/manifest.json').read_bytes())
expected = {(r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in manifest['resolved'] if r['mapping']['kind']=='register'}
def canonical(pin):
    return re.sub(r'/opit_[^/]+(?=/[^/]+$)', '', pin)
def scan(path, limit=None):
    count=collections.Counter(); coverage=collections.defaultdict(set); samples=[]; row={}; consumed=0
    def commit():
        if not row or 'slack' not in row:return
        corner=row.get('type',''); corner='Slow' if 'slow' in corner.lower() else 'Fast' if 'fast' in corner.lower() else 'Unknown'
        count['records']+=1;count['records_'+corner]+=1
        pair=(canonical(row.get('start','')),canonical(row.get('end','')))
        mailbox='/mailbox[' in row.get('start','') and '/host_bank[' in row.get('end','')
        md='MaxDelay Path' in row.get('exception','')
        if md:count['MaxDelay_records']+=1
        if mailbox:
            count['mailbox_records']+=1
            if md:count['mailbox_MaxDelay_records']+=1;coverage[corner].add(pair)
        cls=row.get('class','')
        check=row.get('check','')
        if check:
            count[check]+=1
            if len(samples)<4:samples.append(dict(row))
    with path.open('rb') as f:
        for line in f:
            consumed+=len(line)
            if limit and consumed>limit:break
            s=line.strip()
            if s.startswith(b'Startpoint'):
                commit();row={}
            m=re.match(rb'(Startpoint|Endpoint|Path Type|Path Class|Timing Exception)\s*:\s*(.*)',s)
            if m:
                k={b'Startpoint':'start',b'Endpoint':'end',b'Path Type':'type',b'Path Class':'class',b'Timing Exception':'exception'}[m[1]]
                val=m[2].decode('utf8','replace').strip()
                if k in ('start','end'):val=re.sub(r'\s+\(.*','',val)
                row[k]=val
            m=re.search(rb'Slack \((?:MET|VIOLATED)\)\s+([-\d.]+)',s)
            if m:row['slack']=float(m[1])
            m=re.match(rb'(Recovery|Removal)\s+time\s',s)
            if m:row['check']=m[1].decode('ascii')
        else:commit()
    return {'path':str(path),'size':path.stat().st_size,'bytes_read':consumed,'full_scan':not limit or consumed<=limit,'counts':dict(count),'expected_pairs':len(expected),'canonical_MaxDelay_coverage':{k:{'unique_pairs':len(v),'expected_intersection':len(v&expected),'unexpected':len(v-expected)} for k,v in coverage.items()},'reset_samples':samples}
def main():
    results=[]
    for path,limit in [(EXACT/'routed_mailbox/report_timing/v7_sdt_top.rtr',None),(EXACT/'routed_reset/report_timing/v7_sdt_top.rtr',128*1024*1024),(BOARD/'source_diagnostics_build_01/sta_ab_01/ta_B_exact_grouped_01/bundle_max.snr',None),(BOARD/'source_diagnostics_build_01/sta_ab_01/ta_B_exact_grouped_01/reset.snr',None)]:
        r=scan(path,limit);results.append(r);print(json.dumps(r,ensure_ascii=True),flush=True)
    Path(__file__).with_name('stream_results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
if __name__=='__main__':main()
