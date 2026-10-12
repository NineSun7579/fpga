"""串行本地实际构建；全部失败留档，无远程/烧录。"""
from pathlib import Path
import json,re,shutil,subprocess,sys,time,traceback,importlib.util
import continue_fixed as cf
import generate_exact11 as gen
OUT=gen.OUT;HERE=gen.NEW;ROOT=gen.ROOT
cf.OUT=OUT
def save(n,v):gen.write_json(OUT/n,v)
def wait():
    # 已授权的前序 audit 与查询控制器必须自然结束，含其后续 PDS 子进程。
    print('等待前序审计/工具查询自然结束，不修改其工程。',flush=True)
    subprocess.run(['powershell','-NoProfile','-Command','Wait-Process -Id 75608,51608 -ErrorAction SilentlyContinue'],capture_output=True)
    while cf.busy():time.sleep(5)
    cf.idle()
def guard():
    original=json.loads((cf.BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    bad=[p for p,h in original.items() if cf.sha(Path(p))!=h]
    save('protected_latest.json',{'count':len(original),'mismatches':bad,'time':time.time()})
    assert len(original)==1022 and not bad
    manifest=OUT/'input_hashes.json'
    if manifest.exists():
        inputs=json.loads(manifest.read_bytes())
        assert all(cf.sha(HERE/p)==h for p,h in inputs.items())
def export_graph(stage,db,resolve=False):
    dest=OUT/stage;analysis=dest/'analysis';analysis.mkdir(parents=True,exist_ok=True)
    dump=dest/'synthesis_export/synthesis_dump.txt';dump.parent.mkdir(exist_ok=True)
    script=dest/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',encoding='ascii')
    h=cf.sha(db)
    cf.run(stage+'_export',[str(cf.PDS),'-file',str(script),'-work_dir',str(dest),'-project_name','exact11_'+stage],dest)
    assert cf.sha(db)==h
    origin=ROOT/'physical_exact_09/actual/analysis'
    scripts=['parse_objects.py']+(['resolve_manifest.py','derive_exact_complement.py','classify_paths.py'] if resolve else [])
    for name in scripts+['B_one_pair.sdc']:
        shutil.copy2(origin/name,analysis/name)
    for name in scripts:
        cf.run(stage+'_'+name[:-3],[sys.executable,str(analysis/name)],analysis)
    g=json.loads((analysis/'graph.json').read_bytes())
    return g,analysis
def verify_graph(stage,g,analysis):
    off=json.loads((OUT/'coverageproof_offline.json').read_bytes())
    rows=[]
    for old in off['cameras']:
        i=old['camera'];actual=gen.camera_leaves(g,i)
        expected=old['compile' if stage=='compile' else 'synthesis']
        missing=set(expected['leaves'])-set(actual['leaves']);extra=set(actual['leaves'])-set(expected['leaves'])
        rows.append({'camera':i,'leaf_count':len(actual['leaves']),'missing':sorted(missing),'extra':sorted(extra),'actual':actual})
        assert not missing and not extra,(stage,i,missing,extra)
    pairs=[]
    if stage!='compile':
        m=json.loads((analysis/'manifest.json').read_bytes());assert not m['errors']
        pairs=sorted(set((r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['mapping']['kind']=='register'))
        expected=sorted(tuple(p) for c in off['cameras'] for p in c['physical_pairs'])
        assert pairs==expected and len(pairs)==1320
    save('coverageproof_'+stage+'.json',{'stage':stage,'passed':True,'cameras':rows,'pairs':pairs,'pair_count':len(pairs)})
def main():
    wait();guard()
    assert not HERE.exists(),'新 attempt 已存在，禁止覆盖真实运行档'
    assert not (OUT/'dev_map_launch.json').exists()
    HERE.mkdir()
    for name in ['inputs','rtl']:shutil.copytree(gen.OLD/name,HERE/name)
    constraints=HERE/'physical_constraints_exact_11';constraints.mkdir()
    for p in (gen.OLD/'physical_constraints_exact_09').glob('*.fdc'):
        shutil.copy2(OUT/'clock.fdc' if p.name=='clock.fdc' else p,constraints/p.name)
    raw=(gen.OLD/'standard_flow_exact09.pds').read_bytes()
    raw=raw.replace(b'physical_constraints_exact_09/',b'physical_constraints_exact_11/')
    raw=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw)
    project=HERE/'standard_flow_exact11.pds';project.write_bytes(raw);shutil.copy2(project,OUT/project.name)
    # 独立目录中新综合保留与旧 exact09 相同物理寄存器，不复用旧 DB。
    save('input_hashes.json',{str(p.relative_to(HERE)):cf.sha(p) for n in ['inputs','rtl','physical_constraints_exact_11'] for p in (HERE/n).rglob('*') if p.is_file()})
    guard();cmd=lambda stage:[str(cf.PDS),'-project',str(project),'-run',stage,'-work_dir',str(HERE)]
    print('启动独立 route03 实际 dev_map。',flush=True)
    marks=cf.run('dev_map',cmd('dev_map'),HERE)
    assert 'Process "Device Map" done.' in marks
    db=HERE/'device_map/v7_sdt_top_map.adf';save('dev_map_artifact.json',{'path':str(db),'sha256':cf.sha(db)})
    guard()
    cg,ca=export_graph('compile',HERE/'compile/v7_sdt_top_comp.adf')
    verify_graph('compile',cg,ca)
    sg,sa=export_graph('actual',HERE/'synthesize/v7_sdt_top_syn.adf',True)
    verify_graph('synthesis',sg,sa)
    # 与 audit_fixed 的1320门禁兼容；真实配对逐一已验证，不能靠文件名宣称成功。
    save('canonical_equivalence_after_remap.json',{'physical_pairs':1320,'verified_by':'coverageproof_synthesis.json'})
    guard();print('compile -> synthesis 覆盖实证通过，启动实际 PNR。',flush=True)
    marks=cf.run('pnr',cmd('pnr'),HERE)
    assert 'Process "Place & Route" done.' in marks
    db=HERE/'place_route/v7_sdt_top_pnr.adf';save('pnr_artifact.json',{'path':str(db),'sha256':cf.sha(db)})
    guard()
    # 复用完整十组/HSST/IO/mailbox双角验收，将 HERE 显式指向独立 route03。
    cf.HERE=HERE;sys.argv=['audit_fixed.py','physical_exact_11','standard_flow_exact11.pds']
    spec=importlib.util.spec_from_file_location('exact11_audit',Path(__file__).with_name('audit_fixed.py'))
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    audit_error=None
    try:audit.main()
    except BaseException:
        audit_error=traceback.format_exc();(OUT/'audit_failure.txt').write_text(audit_error,encoding='utf8')
    # 即使十组失败，仍将真实 routed 图覆盖证据做完，完整保留负裕量路径。
    rg,ra=export_graph('routed',db,False)
    import verify_routed11
    assert verify_routed11.main(),'真实 routed 物理绑定失败'
    guard()
    save('result.json',{'pnr_done':True,'compile_syn_routed_coverage':True,'acceptance_passed':audit_error is None,
                         'bit_permitted':audit_error is None,'remote_or_program':False})
    if audit_error:raise RuntimeError('实际验收仍失败；查看 audit_failure 和全部 STA 原始档；禁止烧录。')
    print('实际构建及全部验收成功；仅本地 bit，无远程/烧录。',flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        OUT.mkdir(exist_ok=True);(OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf8');raise
