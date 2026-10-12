"""Phase-aware explicit FDC objects, actual map then validate before PNR."""
from continue_fixed import BASE,HERE,PDS,sha,busy
from pathlib import Path
import json,re,shutil,subprocess,time,traceback
ROOT=Path(__file__).resolve().parent/'fixed_06'
OUT=ROOT/'physical_fixed_native_08'
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2))
def launch(stage):
    assert not busy()
    cmd=[str(PDS),'-project',str(HERE/'standard_flow_fixed_native.pds'),'-run',stage,'-work_dir',str(HERE)]
    save(stage+'_launch.json',{'command':cmd,'time':time.time()});print('START',stage,flush=True)
    with (OUT/(stage+'.log')).open('xb') as f:p=subprocess.run(cmd,cwd=HERE,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/(stage+'.log')).read_bytes();err=[s.decode('ascii','backslashreplace') for s in raw.splitlines() if s.startswith(b'E:') or b'Timing-4003' in s]
    marks=[s.decode('ascii','backslashreplace') for s in raw.splitlines() if s.startswith((b'Process "',b'Design '))]
    save(stage+'_result.json',{'exit_code':p.returncode,'errors':err,'marks':marks});assert p.returncode==0 and not err,(stage,err[:2])
    return marks
def main():
    assert not busy();OUT.mkdir(exist_ok=True)
    assert not (OUT/'dev_map_launch.json').exists(), 'Preserve any actual PDS attempt; use a new attempt for a rerun'
    if (OUT/'failure.txt').exists():shutil.move(str(OUT/'failure.txt'),str(OUT/'prelaunch_failure.txt'))
    synroot=ROOT/'native_probe_07/synthesize_actual/analysis';comproot=ROOT/'native_probe_07/compile_actual/analysis'
    sg=json.loads((synroot/'graph.json').read_bytes());cg=json.loads((comproot/'graph.json').read_bytes());exact=json.loads((synroot/'exact_complement.json').read_bytes())
    assert not exact['errors']
    manifest=json.loads((synroot/'manifest.json').read_bytes());assert not manifest['errors']
    mapping={}; phase_evidence=[];lines=[]
    def native(pin):
        cell,port=pin.rsplit('/',1);name=cell.replace('/','.')+'/'+port;mapping[pin]=name;return name
    def coll(pins):
        assert pins;return '[get_pins -hierarchical {'+' '.join(native(x) for x in sorted(set(pins)))+'}]'
    for cam,c in enumerate(exact['cameras']):
        assert len(c['bundle_pairs'])==320 and c['complement_launch_pins']
        pre=f'source_diagnostics/cameras[{cam}].source/'
        mb=[ip for ip in cg['primitives'] if ip.startswith(pre+'mailbox[')]
        host=[ip for ip in cg['primitives'] if ip.startswith(pre+'host_bank[')]
        assert len(mb)==17 and len(host)==1
        roots={cg['pin_net'][ip+'/CLK'] for ip in mb};assert len(roots)==1
        starts=set();unknown=[]
        for net in roots:
            for pin in cg['netpins'][net]:
                cell,port=pin.rsplit('/',1);prop=cg['primitives'][cell]['ports'][port]
                if prop['direction']!='INPUT':continue
                if prop['clock']:starts.add(pin)
                else:unknown.append(pin)
        assert not unknown,unknown
        compile_launch={ip+'/CLK' for ip in mb};compile_complement=starts-compile_launch;assert compile_complement
        compile_capture={ip+'/'+p for ip in host for p,v in cg['primitives'][ip]['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
        assert len(compile_capture)==512
        launchpins=set(c['mailbox_launch_pins'])|compile_launch;capture=set(c['capture_D'])|compile_capture;comp=set(c['complement_launch_pins'])|compile_complement
        # Whitelist exact selected scalar pins; vector names do not exist in synthesized graph.
        assert {p for p in launchpins if p.rsplit('/',1)[0] in sg['primitives']}==set(c['mailbox_launch_pins'])
        assert {p for p in capture if p.rsplit('/',1)[0] in sg['primitives']}==set(c['capture_D'])
        assert {p for p in comp if p.rsplit('/',1)[0] in sg['primitives']}==set(c['complement_launch_pins'])
        lines+=['set_false_path -from '+coll(comp)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(launchpins)+' -to '+coll(capture),'set_false_path -hold -from '+coll(launchpins)+' -to '+coll(capture)]
        phase_evidence.append({'camera':cam,'physical_pairs':320,'physical_complement':len(c['complement_launch_pins']),'compile_mailbox_clock_pins':sorted(compile_launch),'compile_complement_clock_pins':sorted(compile_complement),'compile_capture_pin_count':512})
    newfdc=HERE/'physical_constraints_native_08';newfdc.mkdir(exist_ok=True)
    for p in (HERE/'physical_constraints').glob('*.fdc'):
        raw=p.read_bytes()
        if p.name=='clock.fdc':raw=raw.split(b'# Exact real-object CDC complement and mailbox absolute budget')[0]+b'# Exact real-object CDC complement and mailbox absolute budget\n'+'\n'.join(lines).encode('ascii')+b'\n'
        (newfdc/p.name).write_bytes(raw)
    original=HERE/'standard_flow_fixed.pds';shutil.copy2(original,OUT/'pre_native_project.pds')
    raw=original.read_bytes();raw=raw.replace(b'physical_constraints/',b'physical_constraints_native_08/')
    dev_start=raw.index(b'(_command cmd_devmap');dev_end=raw.index(b'(_widget',dev_start);assert b'top_module' not in raw[dev_start:dev_end]
    project=HERE/'standard_flow_fixed_native.pds';project.write_bytes(raw);shutil.copy2(project,OUT/project.name)
    save('native_phase_mapping.json',{'synth_db_sha256':sha(HERE/'synthesize/v7_sdt_top_syn.adf'),'source_dump_sha256':sha(ROOT/'native_probe_07/synthesize_dump.txt'),'mapping':mapping,'cameras':phase_evidence,'actual_pairs':1280,'constraint_sha256':sha(newfdc/'clock.fdc'),'exact_scalar_graph_whitelist_verified':True,'runtime_validated':False})
    inputs={str(p.relative_to(HERE)):sha(p) for n in ['inputs','rtl','physical_constraints','physical_constraints_native_08'] for p in (HERE/n).rglob('*') if p.is_file()};save('input_hashes.json',inputs)
    guard=json.loads((BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    def check():assert all(sha(Path(p))==h for p,h in guard.items()) and all(sha(HERE/p)==h for p,h in inputs.items())
    check();synhash=sha(HERE/'synthesize/v7_sdt_top_syn.adf')
    marks=launch('dev_map');db=HERE/'device_map/v7_sdt_top_map.adf'
    assert db.exists() and db.stat().st_size
    assert 'Process "Device Map" started.' in marks and 'Process "Device Map" done.' in marks and any('successfully' in s for s in marks)
    save('dev_map_artifact.json',{'path':str(db),'sha256':sha(db)})
    check()
    # A source-triggered re-synthesis requires another actual graph export before PNR.
    if sha(HERE/'synthesize/v7_sdt_top_syn.adf')!=synhash:
        save('new_synthesis_pending.json',{'before':synhash,'after':sha(HERE/'synthesize/v7_sdt_top_syn.adf'),'pnr_started':False});print('MAP COMPLETE; new synthesis graph requires export/revalidation',flush=True);return
    marks=launch('pnr');route=HERE/'place_route/v7_sdt_top_pnr.adf'
    assert route.exists() and route.stat().st_size and 'Process "Place & Route" started.' in marks and 'Process "Place & Route" done.' in marks
    save('pnr_artifact.json',{'path':str(route),'sha256':sha(route)});check()
    print('REAL ROUTED DB; timing/CDC/IO gates required before bit',flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
