"""Independent saved-evidence review; never runs PDS or touches upstream trees."""
from pathlib import Path
import gzip,hashlib,json,re,importlib.util
P=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def save(n,v): (P/n).write_text(json.dumps(v,indent=2),encoding='utf8')
def main():
    results=json.loads((P/'results.json').read_text())
    contracts=json.loads((P/'replacement_contract.json').read_text())
    O=P.parent/'source_diagnostics_top_candidate'
    F=P.parents[1]/'whole_candidate_v7_route_01'
    spec=importlib.util.spec_from_file_location('audit_sim_order',O/'sim_order.py')
    order=importlib.util.module_from_spec(spec);spec.loader.exec_module(order)
    view_proof=[]
    for row in contracts['baseline']:
        if Path(row['source']).parent!=O/'sim_views':continue
        name=Path(row['source']).name
        raw=O/name if name=='v7_sdt_top.v' else F/'rtl'/name
        target=P/'audit_views'/name;target.parent.mkdir(parents=True,exist_ok=True)
        normalized=order.normalize(raw,target)
        assert sha(normalized)==row['compiled_sha256'],('baseline simulation-view lineage',name)
        view_proof.append(dict(original_raw=str(raw),raw_sha256=sha(raw),normalized_sha256=sha(normalized),actually_compiled=row['compiled']))
    save('golden_sim_view_proof.json',view_proof)
    before=json.loads((P/'frozen_before.json').read_text());after=json.loads((P/'frozen_after.json').read_text())
    assert before==after, 'Protected files changed during the actual regression'
    compiled_sources={str(Path(r['source']).resolve()) for rows in contracts.values() for r in rows}
    for variant in contracts:
        compiled_sources.update(str(Path(r['source']).resolve()) for r in
                                json.loads((P/variant/'include_copies.json').read_text()))
    live_status_root=P.parent/'source_diagnostics_timing_build_02/evidence/runtime'
    observational_files={str((live_status_root/name).resolve()) for name in
                         ('controller_status.json','queue_build02.json')}
    assert not (compiled_sources & observational_files), 'Status file unexpectedly used as simulation input'
    drift=[]
    for name,digest in before.items():
        current=sha(name)
        if current!=digest:
            assert str(Path(name).resolve()) in observational_files, ('Unexpected live input drift',name)
            drift.append({'path':name,'regression_sha256':digest,'live_sha256':current,
                          'reason':'Live controller observation, not a simulation compilation input'})
    save('live_status_reconciliation.json',{'regression_before_after_identical':True,
         'compiled_input_drift':False,'observational_drift':drift})
    warnings={}
    for variant,rows in contracts.items():
        assert len(rows)==243
        for row in rows:
            assert sha(row['source'])==row['source_sha256']==sha(row['raw_copy'])
            assert sha(row['compiled'])==row['compiled_sha256']
        for row in json.loads((P/variant/'include_copies.json').read_text()):
            assert sha(row['source'])==row['sha256']==sha(row['copy'])
        text=(P/variant/'simulation.log').read_text(errors='replace')
        warnings[variant]=[l for l in text.splitlines() if '** Warning' in l]
        assert 'SDT_ALL_PASS checks=14540' in text and 'TOP_FOUR_RESET_PASS checks=14668' in text
        assert len(re.findall(r'TOP_RESET_CAM_PASS camera=',text))==4
        assert not re.search(r'\*\* (?:Error|Fatal)|FAIL',text)
        for log in ['compile.log','tb_compile.log']:
            t=(P/variant/log).read_text(errors='replace');assert not re.search(r'\*\* (?:Error|Fatal)',t)
        assert (P/variant/'scenario.vh').read_bytes()==(P/'baseline/scenario.vh').read_bytes()
        assert (P/variant/'tb_sdt.sv').read_bytes()==(P/'baseline/tb_sdt.sv').read_bytes()
    save('warnings.json',warnings)
    changes=[]
    for old,new in zip(contracts['baseline'],contracts['integrated']):
        assert old['original']==new['original']
        if old['compiled_sha256']!=new['compiled_sha256']:
            changes.append(dict(original_compile_entry=old['original'],baseline_compiled=old['compiled'],integrated_compiled=new['compiled'],baseline_sha256=old['compiled_sha256'],integrated_sha256=new['compiled_sha256']))
    attributes_only={'fpga_v8_pcie_fifo_h2f_tc02.v','fpga_v8_reset_fault_guard_02.v'}
    assert {Path(x['original_compile_entry']).name for x in changes}=={'ov5640_reg.v','fpga_v8_capture_control_axil_arm_v2.v','fpga_v8_capture_lease_tc04.v','v7_sdt_top.v','v7_sdt_bus.v','v7_sfd_candidate.v'}|attributes_only
    for row in changes:
        name=Path(row['original_compile_entry']).name
        row['synthesis_attributes_only']=name in attributes_only
        if name in attributes_only:
            def remove_attributes(b):return re.sub(rb'\(\*.*?\*\)',b'',b,flags=re.S)
            assert remove_attributes(Path(row['baseline_compiled']).read_bytes())==remove_attributes(Path(row['integrated_compiled']).read_bytes()),('unexpected functional source difference',name)
    save('actual_compile_delta.json',dict(changed=changes,unchanged_compile_entries=243-len(changes)))
    traces={}
    for name in ['comparison.trace','integrated.trace']:
        h=hashlib.sha256();count=0;size=0
        with gzip.open(P/'baseline'/(name+'.gz'),'rb') as a,gzip.open(P/'integrated'/(name+'.gz'),'rb') as b:
            for x in a:
                y=b.readline();assert x==y,(name,count,x[:150],y[:150]);h.update(x);count+=1;size+=len(x)
            assert not b.read()
        assert h.hexdigest()==results[name]['sha256'] and count==results[name]['records']
        traces[name]=dict(equal=True,records=count,bytes=size,sha256=h.hexdigest())
    src=P.parent/'source_diagnostics_timing_build_02'
    registered=json.loads((src/'manifest.json').read_text())['registered_sources']
    project_sources=[s.decode('ascii') for s in re.findall(rb'\(_file "([^"]+\.v)"',(src/'project.pds').read_bytes())]
    assert set(project_sources)==set(registered),('actual project registration drift',len(project_sources),len(registered))
    save('actual_project_registration.json',dict(project=str(src/'project.pds'),project_sha256=sha(src/'project.pds'),registered_sources=project_sources,unique_count=len(set(project_sources))))
    models=[r for r in contracts['integrated'] if '/inputs/ipcore/' in r['source'].replace('\\','/')]
    source_rows=[r for r in contracts['integrated'] if str(Path(r['source']).relative_to(src)).replace('\\','/').startswith(('rtl/','inputs/source/'))]
    assert all(str(Path(r['source']).relative_to(src)).replace('\\','/') in registered for r in source_rows)
    lease=[r for r in contracts['integrated'] if Path(r['source']).name=='fpga_v8_capture_lease_prefix.v'];assert len(lease)==1
    required_changed=['ov5640_reg.v','fpga_v8_capture_control_axil_arm_v2.v','fpga_v8_capture_lease_prefix.v','v7_sdt_bus.v','v7_sfd_candidate.v']
    assert all(any(Path(r['source']).name==n for r in contracts['integrated']) for n in required_changed)
    candidate_sources={
        'ov5640_reg.v':P.parent/'camera_read_decode_timing_candidate/rtl/ov5640_reg.v',
        'fpga_v8_capture_control_axil_arm_v2.v':P.parent/'capture_control_decode_timing_candidate/candidate/fpga_v8_capture_control_axil_arm_v2.v',
        'fpga_v8_capture_lease_prefix.v':P.parent/'capture_lease_prefix_timing_candidate/candidate/fpga_v8_capture_lease_prefix.v',
        'v7_sdt_bus.v':P.parent/'diagnostic_sync_register_timing_candidate/rtl_primitive/v7_sdt_bus.v',
        'v7_sfd_candidate.v':P.parent/'diagnostic_sync_register_timing_candidate/rtl_primitive/v7_sfd_candidate.v'}
    provenance=[]
    for name,reference in candidate_sources.items():
        row=next(r for r in contracts['integrated'] if Path(r['source']).name==name)
        assert sha(reference)==row['source_sha256'],('candidate lineage',name)
        provenance.append(dict(name=name,previous_regressed_candidate=str(reference),sha256=sha(reference),actual_build02_source=row['source']))
    save('optimization_lineage.json',provenance)
    fields=json.loads((P/'trace_fields.json').read_text())
    audit=dict(status='PASS',suite_checks_each=14668,compile_files_each=243,build02_registered_sources=len(registered),compiled_rtl_and_source_rows=len(source_rows),official_IP_and_sim_model_rows=len(models),trace_fields=sum(map(len,fields.values())),trace_groups=len(fields),traces=traces,protected_files=len(before),lease_prefix_actually_compiled=True,simulation_warnings={v:results[v]['warnings'] for v in ['baseline','integrated']},actual_bindings=json.loads((P/'actual_parent_bindings.json').read_text()))
    save('audit.json',audit)
    lines=['# Build02 integrated full-top ModelSim regression02', '',
        'PASS: exact09 golden and actual build02 integrated RTL each completed the unchanged original suite plus all four camera reset checks (14668 checks each). Both four-state traces match record by record after local reset, starting at 20 ns.','',
        f"Compiled 243 RTL/IP/simulation-model files per variant. Build02 registers {len(registered)} sources; the actual reachable compile list includes {len(source_rows)} registered RTL/source files and {len(models)} official IP/model files. This is a complete original full-top compile closure, not a primitive-only substitution.",'',
        'Actual compile delta: 235 entries are byte-identical. Six entries contain the requested camera/control/lease/diagnostic changes or top lease-module binding. Two further files (PCIe FIFO and reset fault guard) have existing ASYNC_REG to syn_preserve/syn_allow_retiming attribute substitutions only; independent removal of attribute spans proves all remaining bytes identical. See actual_compile_delta.json. These are not hidden functional golden changes.','',
        'Build02 actual registered v7_sdt_top, camera wrapper/binding and matching registered parents are byte-copied into integrated/. Camera ov5640_reg comes from build02 inputs/source. The actual top binds fpga_v8_capture_lease_prefix at u_v8_capture_lease. Camera read decode, full-address control decode, lease prefix and explicit diagnostic 28 CE / 32 PE implementations are all compiled together. See replacement_contract.json, both compile.f files, registered_modules.json, hierarchy.txt and actual_parent_bindings.json.','',
        'Golden original source_diagnostics_top_candidate top, camera wrapper/binding, camera register, control and lease SHA256 exactly match frozen exact09 inputs. See golden_exact09_provenance.json. No golden functional edits or extra latency compensation.','',
        f"Expanded trace compares {audit['trace_fields']} signal expressions in {len(fields)} groups: original top external outputs, AXI paths, all original camera outputs and camera register outputs, source and motion frame counters, cooperative outputs, all lease/control outputs, bank state, sequence, generation, claims/releases and config strobes. The original regression01 diagnostic monitor is also retained unchanged. See trace_fields.json and compressed traces. Internal redundant published-prefix predicates are excluded.",'',
        'Sampling uses actual host/camera/control clock edges with 2/3/4/5 ps post-NBA offsets, including camera negedge launch observation. Time-zero primitive INIT differences are excluded by the existing local-reset start at 20 ns. Identical consecutive group records are omitted losslessly; SAMPLES records preserve every sampled-edge count.','',
        '| Trace | Records | Bytes | SHA256 |','|---|---:|---:|---|']
    for n,v in traces.items():lines.append(f"| {n} | {v['records']} | {v['bytes']} | {v['sha256']} |")
    lines += ['', 'Six real camera RTL structures and four real motion detector RTL instances are asserted from ModelSim loaded hierarchy. Motion history exists as four 8-bit x 19200 RTL arrays (32 bitplanes). There are **no 32 independent motion RAM primitive instances in this RTL**: history inference into 32 physical RAM resources requires synthesis evidence. This run cannot honestly assert 32 primitive instances or physical-resource acceptance; actual_parent_bindings.json explicitly records motion_physical_RAM_instances_verified=false.','',
        'Uses the unchanged original official DDR/IP/interface simulation models and existing official vendor ModelSim library; no new stub. Existing sim_order.py only normalizes declarations/active USE_OV5640 branch for ModelSim. Integrated views and their .diff files are regenerated from copied build02 registered sources.','',
        'Coverage limits: the original TB forces AXI/control clocks, DDR init and I2C completion, with free_clk stopped. Four full DVP source frames and original AXI register/reset/lease diagnostics are exercised; this does not verify complete DMA full-frame DDR writes, DDR calibration, PCIe training, raw transport throughput or end-to-end cooperative processing. No PDS, remote action, device access, synthesis, routing or physical timing acceptance. Existing warnings remain recorded in real logs.','',
        f"Protected RTL/IP/config/scripts/evidence inputs: {len(before)} hashes unchanged before/after, including build02/runtime/controller sources. See frozen_before.json and frozen_after.json. Independent copies use read_bytes/write_bytes, preserving GBK bytes. No upstream source is modified.",'',
        'Evidence: results.json, audit.json, actual_parent_bindings.json, actual_project_registration.json, optimization_lineage.json, golden_exact09_provenance.json, golden_sim_view_proof.json, replacement_contract.json, trace_fields.json, baseline/ and integrated/ compile/TB/simulation logs, hierarchy and .trace.gz. hashlog.json seals all delivered files except work libraries and itself.','',
        'Reproduce from workspace root: `C:/Users/NineSun/anaconda3/python.exe project/fpga_v8_migration/board_v7/diagnostic_integrated_top_regression02/run.py`, then `.../audit.py`. Only the isolated regression02 tree is written.']
    lines += ['',f"Real simulation warnings: baseline={len(warnings['baseline'])}, integrated={len(warnings['integrated'])}. Full messages are preserved in warnings.json and simulation.log; these existing connection/width/model warnings are not physical signoff."]
    (P/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    save('hashlog.json',{str(f.relative_to(P)):sha(f) for f in P.rglob('*') if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.name!='hashlog.json'})
    print('INDEPENDENT_INTEGRATED_AUDIT_PASS',json.dumps(audit,indent=2))
if __name__=='__main__':main()
