"""Read-only source capture and fresh graph derivation; NEVER launches PDS."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, time
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
B03 = BOARD / 'source_diagnostics_timing_build_03'
B04 = BOARD / 'source_diagnostics_timing_build_04'
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()
def save(name, value):
    p = HERE / name
    if p.exists(): raise RuntimeError('Refuse overwrite: '+str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n', encoding='ascii')
def main():
    sources = []
    for root in [B03/'runtime', B04/'runtime']:
        sources.extend(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for n in ['manifest.json','sourcehash.json','source04hash.json','project.pds',
              'evidence/runtime/final_artifact_binding.json','evidence/runtime/final_receipt_review.json',
              'evidence/runtime/mapping60_01/final_result.json',
              'evidence/runtime/mapping60_01/independent_review60.json',
              'evidence/runtime/mapping60_01/FAILURE_DIAGNOSIS_ZH.md',
              'evidence/runtime/mapping60_01/mapping_artifact.json',
              'evidence/runtime/mapping60_01/graph_binding.json',
              'evidence/runtime/mapping60_01/actual_map.tcl']:
        p=B04/n
        if p.is_file(): sources.append(p)
    for n in ['constraints_live','constraints_templates']:
        sources.extend(p for p in (B04/n).rglob('*') if p.is_file())
    sources.extend(p for p in (BOARD/'production60_target_prepare01').glob('*') if p.is_file())
    for n in ['diagnostic_io_bank_join02/REPORT.md','diagnostic_io_bank_join02/join_result.json',
              'diagnostic_io_bank_report04/README.md','diagnostic_io_bank_report02/README.md']:
        p=BOARD/n
        if p.exists(): sources.append(p)
    sources.extend([BOARD.parent/'whole_candidate_v3_timing_route_01/pnr_help.log',
                    BOARD.parent/'whole_candidate_v7_route_01/bitstream_01/bitgen.tcl',
                    Path('C:/pango/PDS_2022.2-SP6.4/doc/Pango_Design_Suite_User_Guide.pdf')])
    binding={str(p.resolve()):sha(p) for p in sources}
    save('bound_reused_scripts_and_evidence.json', {'captured_time':time.time(), 'sha256':binding,
         'scope':'Read-only preparation bindings, NOT physical acceptance; future producer must reverify'})
    analysis=HERE/'offline_fresh_synthesis/analysis'
    analysis.mkdir(parents=True)
    for n in ['graph.json','objects.json']:
        p=B04/'evidence/runtime/actual/analysis'/n
        binding[str(p.resolve())]=sha(p);shutil.copy2(p,analysis/n)
    compile_graph=B04/'evidence/runtime/compile/analysis/graph.json'
    binding[str(compile_graph.resolve())]=sha(compile_graph)
    for n in ['graph_adapter.py','resolve_manifest.py','classify_paths.py','derive_new_constraints.py']:
        shutil.copy2(B04/'runtime/analysis_tools'/n,analysis/n)
    save('fresh_graph_input_binding.json', {str(p):sha(p) for p in [compile_graph,analysis/'graph.json',analysis/'objects.json']})
    results=[]
    commands=[[sys.executable,'-B',str(analysis/'resolve_manifest.py')],
              [sys.executable,'-B',str(analysis/'classify_paths.py')],
              [sys.executable,'-B',str(analysis/'derive_new_constraints.py'),
               '--compile-graph',str(compile_graph),'--synthesis-graph',str(analysis/'graph.json'),
               '--mapping-manifest',str(analysis/'manifest.json'),
               '--frozen-clock',str(B04/'inputs/source/constraints/clock.fdc'),
               '--output',str(HERE/'derived_logical_DRAFT')]]
    for i,cmd in enumerate(commands):
        res=subprocess.run(cmd,cwd=analysis,capture_output=True)
        (HERE/('offline_step'+str(i)+'.log')).write_bytes(res.stdout+res.stderr)
        results.append({'command':cmd,'exit_code':res.returncode})
        if res.returncode: break
    drift=[p for p,h in binding.items() if sha(p)!=h]
    save('offline_preparation_result.json', {'status':'DRAFT_DERIVED_OFFLINE' if len(results)==3 and all(x['exit_code']==0 for x in results) else 'OFFLINE_DERIVATION_BLOCKED',
         'steps':results,'bound_input_drift':drift,'mapping_final_observed':json.loads((B04/'evidence/runtime/mapping60_01/final_result.json').read_bytes()),
         'constraints_qualified':False,'mapping_pass':False,'pnr_started':False,'bit_generated':False,'device_operations':False})
    if drift: raise RuntimeError('Bound source drift: '+repr(drift))
if __name__=='__main__': main()
