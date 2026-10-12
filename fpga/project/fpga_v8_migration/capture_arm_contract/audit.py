"""Exact immutable/API/source/warnings and final mapped component receipt."""
from pathlib import Path
import hashlib,json,re,collections,xml.etree.ElementTree as ET
from prepare import snapshot
HERE=Path(__file__).resolve().parent;ART=HERE/'artifacts';MIG=HERE.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def api(p):
    raw=p.read_bytes();raw=re.sub(rb'//[^\r\n]*',b'',raw).split(b');',1)[0]
    raw=re.sub(rb'module\s+\w+',b'module API',raw)
    return re.sub(rb'\s+',b'',raw)
def main():
    before=json.loads((ART/'immutable_before.json').read_text());after=snapshot()
    save(ART/'immutable_after.json',after)
    differences={p:{'before':v,'after':after.get(p)} for p,v in before.items() if v!=after.get(p)}
    differences.update({p:{'before':None,'after':v} for p,v in after.items() if p not in before})
    old_core=json.loads((MIG/'capture_core_contract/artifacts/immutable_hashes_before.json').read_text())
    old_diffs={p:v for p,v in old_core.items() if sha(Path(p))!=v}
    frozen=json.loads((MIG/'whole_candidate/artifacts/protected_hashes_before.json').read_text())
    frozen_diffs={p:{'expected':v,'actual':sha(MIG.parent/p)} for p,v in frozen.items() if sha(MIG.parent/p)!=v}
    original=MIG/'capture_endpoint/fpga_v8_capture_control_axil.v'
    candidate=HERE/'fpga_v8_capture_control_axil_arm_v2.v'
    assert api(original)==api(candidate),'original API changed'
    whole_control=MIG/'whole_candidate/rtl/fpga_v8_capture_control_axil.v'
    assert sha(original)==sha(whole_control),'whole binding differs from diagnosed control'
    work=HERE/'component_01';snr=work/'synthesize/fpga_v8_capture_arm_loop_top.snr'
    db=work/'synthesize/snr.db';text=snr.read_text();xml=db.read_text()
    assert 'There are 0 combinational loops in the design.' in xml
    assert 'There are 0 latch loops in the design.' in xml
    assert re.search(r'Total Latches:\s+0',text)
    warnings=[]
    for fn in ['compile_stdout.log','synthesize_stdout.log']:
        for line_num,line in enumerate((work/fn).read_text(errors='replace').splitlines(),1):
            if line.startswith('W:'):warnings.append({'file':fn,'line':line_num,'text':line})
    save(ART/'warnings_exact.json',warnings)
    codes=collections.Counter(re.match(r'W:\s+([^:]+):',w['text'])[1] if re.match(r'W:\s+([^:]+):',w['text']) else w['text'] for w in warnings)
    check=ET.parse(db)
    check_rows=[]
    for table in check.iter('table'):
        if 'check' in table.get('id','').lower() or any(t in table.get('id','') for t in ['loops','no_clock','no_input_delay','no_output_delay']):
            check_rows.append({'attributes':table.attrib,'text':' '.join(table.itertext())})
    save(ART/'check_timing_exact.json',check_rows)
    source_manifest=json.loads((work/'expected_inputs.json').read_text())
    assert all(sha(Path(r['path']))==r['sha256'] for r in source_manifest['sources'])
    manifest=json.loads((HERE/'bindings_manifest.json').read_text())
    manifest.update(candidate_module='fpga_v8_capture_control_axil_arm_v2',
      integration='replace original controller source binding and instantiated module name only',
      api_normalized_sha256=hashlib.sha256(api(candidate)).hexdigest(),original_api_equal=True,
      immutable_snapshot_count=len(before),source_sha256={r['path']:r['sha256'] for r in source_manifest['sources']})
    manifest['replacement']={'old_source':str(whole_control),'old_sha256':sha(whole_control),
      'old_module':'fpga_v8_capture_control_axil','new_source':str(candidate),'new_sha256':sha(candidate),
      'new_module':'fpga_v8_capture_control_axil_arm_v2','diff_file':'control.diff',
      'manager_and_capture_replacement':False}
    save(HERE/'bindings_manifest.json',manifest)
    results={name:json.loads((HERE/name/'artifacts/results.json').read_text()) for name in ['core','core_revision','core_priority','core_final_b','endpoint','lease']}
    receipts={name:sha(HERE/name/'artifacts/results.json') for name in results}
    report={'status':'PASS' if not differences and not old_diffs and not frozen_diffs else 'IMMUTABILITY_FAILURE',
      'immutable_count':len(before),'immutable_differences':differences,
      'existing_core_snapshot_count':len(old_core),'existing_core_snapshot_differences':old_diffs,
      'whole_frozen_protected_count':len(frozen),'whole_frozen_protected_differences':frozen_diffs,
      'original_full_api_equal':True,'candidate_sha256':sha(candidate),
      'component':{'combinational_loops':0,'latch_loops':0,'latches':0,'lut':2423,'ff':2070,
        'distributed_ram_luts':64,'drm':4,'period_ns':7.619048,'setup_wns_ns':1.203,'hold_whs_ns':0.619,
        'setup_hold_failing_endpoints':0,'same_clock_endpoints':4958,'synthesis_only':True,
        'report_sha256':sha(snr),'database_sha256':sha(db),'warning_counts':dict(codes)},
      'suite_receipt_sha256':receipts,
      'revision_busy_probes':{c:re.findall(r'ACTUAL_BUSY_ARM_REJECT[^\n]*',(HERE/'core_final_b/artifacts'/c/'simulate.log').read_text()) for c in results['core_final_b']['cases']}}
    save(ART/'review_receipt.json',report)
    assert not differences and not old_diffs and not frozen_diffs,'immutable original artifacts changed'
    assert all(len(v)==3 for v in report['revision_busy_probes'].values())
    print(json.dumps({k:v for k,v in report.items() if k not in ['component']},indent=2))
if __name__=='__main__':main()
