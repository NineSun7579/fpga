"""Build03 frozen local inputs and independently recomputed map02 final gate."""
from pathlib import Path
import hashlib, json, re, sys
HERE=Path(__file__).resolve().parent.parent
BOARD=HERE.parent
RUNTIME=HERE/'runtime'
DATA=RUNTIME/'baseline_data'
MAP=BOARD/'diagnostic_sync_register_map02'
sys.path.insert(0,str(RUNTIME/'libraries'))

def require(ok,message):
    if not ok:raise RuntimeError(message)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(name,value):
    p=HERE/'evidence/runtime'/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def frozen_guard():
    m=load(HERE/'manifest.json')
    require(m['root']==str(HERE),'Build03 root binding changed')
    require(len(m['local_hashes'])==741 and len(m['registered_sources'])==186,'741/186 source contract changed')
    require(load(HERE/'sourcehash.json')==m['local_hashes'],'Source ledger disagrees')
    for n,h in m['local_hashes'].items():require(sha(HERE/n)==h,'Frozen build03 source drift: '+n)
    source03=load(HERE/'source03hash.json')
    require(source03['hashes']==m['local_hashes'] and source03['root']==str(HERE),'Source03 root/hash binding changed')
    require(hashlib.sha256(json.dumps(source03['hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()==source03['source_set_sha256'],'Source03 set digest changed')
    return m['local_hashes']
def verify():
    frozen_guard();m=load(HERE/'manifest.json')
    for n,h in m['optimization_gate']['hashes'].items():require(sha(HERE/n)==h,'Three original optimizations/top drift')
    attr=b'(* syn_noprune=1 *) '
    for row in load(HERE/'evidence/attribute_inverse.json'):
        raw=(HERE/row['path']).read_bytes()
        require(raw.count(attr)==row['textual_instances'] and hashlib.sha256(raw.replace(attr,b'')).hexdigest()==row['inverse_sha256'],'Primitive-only attribute inverse drift')
    require(sha(HERE/'project_template.pds')==m['project_template_sha256'],'Initial project template drift')
    return m

BAD_OPTIONS=re.compile(rb'Timing-4003|Timing-4006|STA-3016|(?:unknown|unsupported|unrecognized|ignor\w*).*?(?:option|argument|attribute)|(?:option|argument|attribute).*?not supported',re.I)
def log_errors(raw):
    return [line.decode('ascii','backslashreplace') for line in raw.splitlines() if line.startswith(b'E:') or
            re.match(rb'\s*(?:\*\*\s*)?(?:ERROR|FATAL)\b',line) or BAD_OPTIONS.search(line)]

def gate_header(final, independent=None):
    if not isinstance(final,dict):return 'BLOCKED','Malformed final result'
    if final.get('status')=='FAIL':return 'BLOCKED','map02 actual mapping final FAIL'
    if final.get('status')!='PASS':return 'PENDING','map02 mapping final not PASS'
    if final.get('all_verified_checks_passed') is not True:return 'PENDING','map02 independent audit not complete'
    if not isinstance(independent,dict):return 'PENDING','map02 independent_audit_result absent'
    if independent.get('status')!='PASS':return 'BLOCKED','map02 independent audit FAIL'
    stages=final.get('stages',{})
    if any(stages.get(s,{}).get(k)!=v for s in ['compile','synthesis','mapping'] for k,v in
           [('status','PASS'),('independent_registers',60),('independent_sync',28),('independent_reset',32)]):
        return 'BLOCKED','map02 does not prove independent60 at every actual stage'
    if final.get('mapping_option_evidence',{}).get('passed') is not True:return 'BLOCKED','Real dev_map options not proven'
    return 'VERIFY_REAL','Requires actual artifact/export/input and 60-endpoint recomputation'

def primitive_statements(raw):
    return re.findall(rb'GTP_DFF_(?:CE|PE)\s+#\([^\r\n]+;',raw)

def map_gate():
    finalpath=MAP/'evidence/final_result.json';indpath=MAP/'evidence/independent_audit_result.json'
    result={'status':'PENDING','reason':'map02 final_result absent','physical_start_allowed':False}
    if not finalpath.exists():return result
    try:
        final=load(finalpath);ind=load(indpath) if indpath.exists() else None
        state,reason=gate_header(final,ind)
        result.update(status=state,reason=reason,final_result_sha256=sha(finalpath))
        if state!='VERIFY_REAL':return result
        from map_topology import audit
        from endpoint_detail import detail
        import map_topology, endpoint_detail
        map_topology.save=lambda n,v:None;endpoint_detail.save=lambda n,v:None
        # The controller freezes these local exact checker sources. Their origin
        # hashes must also match the auditor dependencies behind map02 final PASS.
        origins=load(HERE/'evidence/runtime_port/source_provenance.json')
        for name in ['run.py','audit_final.py','endpoint_logic.py']:
            origin=MAP/name
            rows=[r for r in origins if r['source']==str(origin.resolve())]
            require(rows and all(sha(origin)==r['source_sha256'] for r in rows),'Map auditor changed after local pure copy: '+name)
        require(ind['auditor_sha256']==sha(MAP/'audit_final.py'),'Independent auditor hash mismatch')
        for n,h in ind['auditor_dependencies_sha256'].items():require(sha(MAP/n)==h,'Independent auditor dependency mismatch: '+n)
        require(all(not v for v in ind['failed_endpoint_checks'].values()),'Independent endpoint audit reports failed checks')
        require(not ind['active_run_input_guard']['mismatches'],'Map active guard failure')
        require(all(all(v.values()) for v in ind['artifact_hash_checks'].values()),'Independent artifact hash audit failure')
        for n,h in load(MAP/'evidence/input_hashes.json').items():
            if n!='project.pds':require(sha(MAP/n)==h,'Map02 actual input drift: '+n)
        for guard in ['active_run_input_guard.json']:
            gp=MAP/'evidence'/guard
            require(gp.exists(),'Missing actual mapping input guard')
            for n,h in load(gp).items():
                p=Path(n) if Path(n).is_absolute() else MAP/n
                if p.name=='project.pds':continue
                require(sha(p)==h,'Map actual frozen guard drift: '+str(p))
        mapping_inputs=load(MAP/'evidence/mapping_input_hashes.json')
        for n,h in mapping_inputs['stage_DBs'].items():require(sha(n)==h,'Mapping input stage DB changed: '+n)
        require(sha(MAP/'evidence/map.tcl')==mapping_inputs['map_tcl_sha256'],'Mapping actual Tcl changed')
        require(sha(MAP/'constraints/clock.fdc')==mapping_inputs['clock_fdc_sha256'],'Mapping actual clock input changed')
        proofs={}
        for stage in ['compile','synthesis','mapping']:
            art=load(MAP/f'evidence/{stage}_artifact.json')
            exported=load(MAP/f'evidence/{stage}_export_hashes.json')
            for key in ['adf','native_db']:require(sha(art[key])==art[key+'_sha256'],'Map02 actual DB drift: '+stage)
            require(art['official_done_lines'],'Missing official map02 stage completion')
            gp=MAP/f'evidence/{stage}/analysis/graph.json';dump=MAP/f'evidence/{stage}/synthesis_export/synthesis_dump.txt'
            require(sha(gp)==exported['graph_sha256'] and sha(dump)==exported['dump_sha256'] and exported['adf_sha256']==art['adf_sha256'],'Map02 export not bound to actual DB')
            rr=load(MAP/f'evidence/{stage}_result.json')
            require(rr['exit_code']==0 and not rr['errors'] and rr['log_sha256']==sha(MAP/f'evidence/{stage}.log'),'Map02 actual tool log failure/drift')
            require(not log_errors((MAP/f'evidence/{stage}.log').read_bytes()),'Map02 unknown/ignored option or error')
            g=load(gp);reference=load(MAP/'evidence/synthesis/analysis/graph.json') if stage=='mapping' else None
            a=audit(stage,g,reference);d=detail(stage,g,a)
            require(a['status']=='PASS' and (a['independent_registers'],a['independent_sync'],a['independent_reset'])==(60,28,32) and not d['failed_checks'],'Recomputed map02 actual60 endpoint details FAIL: '+stage)
            proofs[stage]={'independent_registers':60,'independent_sync':28,'independent_reset':32,'graph_sha256':sha(gp),
                           'adf_sha256':art['adf_sha256'],'native_db_sha256':art['native_db_sha256'],'detail_failed_checks':0}
        for name in ['v7_sfd_candidate.v','v7_sdt_bus.v']:
            actual=(HERE/'rtl'/name).read_bytes();candidate=(MAP/'rtl'/name).read_bytes()
            require(primitive_statements(actual)==primitive_statements(candidate),'Primitive parameter/port/instance text differs from mapped candidate')
            require(actual.count(b'(* syn_noprune=1 *) ')==candidate.count(b'(* syn_noprune=1 *) '),'Primitive attribute scope differs')
        require(sha(finalpath)==result['final_result_sha256'],'Map final changed during read-only audit')
        return {**result,'status':'PASS','reason':'Map02 actual mapping and independent60 re-read/recomputed',
                'independent_audit_sha256':sha(indpath),'physical_start_allowed':True,'recomputed_actual_graphs':proofs}
    except (OSError,KeyError,TypeError,ValueError,AssertionError,RuntimeError,StopIteration) as exc:
        return {**result,'status':'BLOCKED','reason':str(exc),'physical_start_allowed':False}
