"""完整 compile 约束保留旧 snapshot 位后，核验 CDB 继承再串行继续实际 PNR。"""
from pathlib import Path
import json,re,sys,shutil,traceback,importlib.util
import generate_exact11 as gen
import continue_fixed as cf
import run_exact11 as runner
OUT=gen.OUT;HERE=gen.NEW;cf.OUT=OUT;cf.HERE=HERE
def main():
    cf.idle();runner.guard()
    assert not (OUT/'pnr_launch.json').exists(),'保留已有实际 PNR，不重复'
    analysis=OUT/'actual/analysis'
    parser=analysis/'parse_objects.py'
    # 离线 parser 加入真实 CDB 继承记录；原版本保留。
    backup=OUT/'parse_objects_before_cdb.py'
    if not backup.exists():shutil.copy2(parser,backup)
    raw=backup.read_bytes();needle=b"'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER')}"
    assert raw.count(needle)==1
    raw=raw.replace(needle,b"'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER'), 'cdb_entries':children(i,'CDBENTRY')}")
    parser.write_bytes(raw)
    cf.run('offline_cdb_parse',[sys.executable,str(parser)],analysis)
    g=json.loads((analysis/'graph.json').read_bytes());off=json.loads((OUT/'coverageproof_offline.json').read_bytes())
    exact=json.loads((analysis/'exact_complement.json').read_bytes());assert not exact['errors']
    rows=[]
    constraints=(HERE/'physical_constraints_exact_11/clock.fdc').read_text(encoding='ascii').splitlines()
    def field(entry,key):return next(x[1] for x in entry[1:] if isinstance(x,list) and x[0]==key)
    for camera in off['cameras']:
        i=camera['camera'];actual=gen.camera_leaves(g,i)
        missing=set(camera['synthesis']['leaves'])-set(actual['leaves'])
        extra=set(actual['leaves'])-set(camera['synthesis']['leaves'])
        prefix=('' if i==0 else f'cam{i+1}_')+'ov5640_top/ov5640/ov5640_cdc/'
        assert not missing
        assert extra=={prefix+f'src_snapshot[{bit}]/CLK' for bit in range(64,96)},(i,extra)
        inheritance=[]
        for pin in sorted(extra):
            cell,port=pin.rsplit('/',1);r=g['primitives'][cell]
            assert r['type']=='GTP_DFF_CE'
            entries=[]
            for e in r['cdb_entries']:
                filename=field(e,'FILENAME').strip('"');line=int(field(e,'LINENUM'))
                if filename!=str(HERE/'physical_constraints_exact_11/clock.fdc').replace('\\','/'):continue
                if field(e,'HIER')!=prefix+'src_snapshot[95:0]' or field(e,'PINNAME')!='CLK':continue
                text=constraints[line-1]
                assert text.startswith('set_false_path -from [get_pins -hierarchical {') and text.endswith('-to [get_clocks {ddrphy_sysclk}]')
                assert gen.native(prefix+'src_snapshot[95:0]/CLK') in text
                entries.append({'entry':e,'constraint_line':line,'constraint_sha256':gen.cf.sha(HERE/'physical_constraints_exact_11/clock.fdc')})
            assert entries,('无真实 compile 补集继承',pin)
            inheritance.append({'pin':pin,'compile_vector':prefix+'src_snapshot[95:0]/CLK','cdb':entries})
        latest=exact['cameras'][i]
        assert set(actual['leaves'])==set(latest['all_launch_pins'])
        assert sorted(latest['bundle_pairs'])==sorted(camera['physical_pairs']) and len(latest['bundle_pairs'])==330
        rows.append({'camera':i,'leaf_count':len(actual['leaves']),'missing':[], 'retained_extra':sorted(extra),'compile_cdb_inheritance':inheritance,'actual':actual})
    gen.write_json(OUT/'coverageproof_synthesis.json',{'stage':'synthesis','passed':True,'pair_count':1320,'cameras':rows,'retained_extra_count':128,'reason':'完整 compile 补集使旧 snapshot[64..95] 从等价优化中保留；每个新增 CLK 已实证继承精确 compile 向量补集，mailbox B 不变'})
    gen.write_json(OUT/'canonical_equivalence_after_remap.json',{'physical_pairs':1320,'verified_by':'coverageproof_synthesis.json'})
    routeguard=OUT/'dev_map_artifact.json';receipt=json.loads(routeguard.read_bytes())
    assert cf.sha(Path(receipt['path']))==receipt['sha256']
    runner.guard();print('新增128旧 snapshot CLK逐项 CDB继承通过；1320 mailbox对不变。开始真实 PNR。',flush=True)
    marks=cf.run('pnr',[str(cf.PDS),'-project',str(HERE/'standard_flow_exact11.pds'),'-run','pnr','-work_dir',str(HERE)],HERE)
    assert 'Process "Place & Route" done.' in marks
    route=HERE/'place_route/v7_sdt_top_pnr.adf'
    gen.write_json(OUT/'pnr_artifact.json',{'path':str(route),'sha256':cf.sha(route)})
    runner.guard()
    sys.argv=['audit_fixed.py','physical_exact_11','standard_flow_exact11.pds']
    spec=importlib.util.spec_from_file_location('exact11_audit',Path(__file__).with_name('audit_fixed.py'))
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    error=None
    try:audit.main()
    except BaseException:
        error=traceback.format_exc();(OUT/'audit_failure.txt').write_text(error,encoding='utf8')
    runner.export_graph('routed',route,False)
    import summarize_exact11
    summarize_exact11.main()
    if error:raise RuntimeError('完整实际门禁尚有失败，保留十组与定向预算全部证据，不生成/烧录 bit。')
if __name__=='__main__':
    try:main()
    except BaseException:
        (OUT/'resume_failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        import summarize_exact11
        summarize_exact11.main()
        raise
