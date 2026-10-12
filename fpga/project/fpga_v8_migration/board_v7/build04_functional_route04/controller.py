"""Functional route continuation. All databases are produced by official tools."""
from pathlib import Path
import sys, json, re, shutil, time, traceback, os, tkinter, subprocess
sys.dont_write_bytecode = True
E = Path(__file__).resolve().parent
OLD = E.parent/'build04_constraint_load_fix01'
REBUILD = OLD/'rebuild03'
sys.path.insert(0, str(OLD))
import runner as r
import continue_map_pnr as c
from binding_review import fields, sexpr
sys.path.insert(0, str(r.F/'runtime'))
from graph_adapter import Resolver
from derive_new_constraints import coll
r.E = E
original_save=r.save
def history_save(name,obj):
    if (E/name).exists():
        p=Path(name);name=str(p.with_name(p.stem+'_retry_'+str(time.time_ns())+p.suffix))
    return original_save(name,obj)
r.save=history_save

def save(name, obj):
    r.save(name, obj)

def idle(label):
    command='[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress'
    ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command]).decode('utf-8-sig'))
    busy=[p for p in ps if re.search(r'pds|programmer|^ta\.exe$|^pnr\.exe$|^synplify|^ads\.exe$|^cfg|^pgm|^cdt_(?:cfg|js)',p['Name'],re.I) or (p['ProcessId']!=os.getpid() and p['Name'].lower() in {'python.exe','pythonw.exe'} and re.search(r'run_trial\.py|programwrapper|run_mapping|controller04\.py|build04_functional_route04.*controller\.py',p.get('CommandLine') or '',re.I))]
    save(label+'_idle.json',dict(time=time.time(),processes=ps,busy=busy))
    assert not busy, ('Whole machine tools/controller busy',busy)

r.idle=idle

def actual_pairs(g):
    rows = []
    resolver = Resolver(g)
    for cell, rec in g['primitives'].items():
        m = re.match(r'source_diagnostics/cameras\[(\d)\]\.source/host_bank\[', cell)
        if not m or cell+'/D' not in g['pin_net']: continue
        q, trace = resolver.trace_driver(g['pin_net'][cell+'/D'])
        launch = q.rsplit('/', 1)[0]
        assert '/mailbox[' in launch, (cell, q)
        rows.append(dict(camera=int(m[1]), launch_Q=q,
            launch_CLK=launch+'/'+resolver.clock_ports(launch)[0], capture_D=cell+'/D',
            capture_CLK=cell+'/'+resolver.clock_ports(cell)[0], trace=trace))
    assert rows and len(rows)==len({(p['launch_CLK'], p['capture_D']) for p in rows})
    return rows

def site_plan(g, w, output):
    t = tkinter.Tcl()
    targets = [t.splitlist(l) for l in (w/'constraints_live/production60.lcf').read_text('ascii').splitlines() if l.strip() and not l.lstrip().startswith('#')]
    actual = [t.splitlist(l) for l in (w/'device_map/v7_sdt_top.pcf').read_text('ascii').splitlines() if l.startswith('def_inst_site ')]
    rows = []
    for cmd in targets:
        source, site = cmd[1][2:], cmd[3]
        cells = [p for p in g['primitives'] if (p==source or p.startswith(source+'/')) and p+'/CLK' in g['pin_net'] and any(p+'/'+x in g['pin_net'] for x in ['Q','Q0','L6Q','L5Q'])]
        assert len(cells)==1, (source, cells)
        matched = [x for x in actual if x[1].lstrip('\\')==cells[0]]
        assert len(matched)==1 and matched[0][2]==site, (source,matched)
        rows.append(dict(source=source, cell=cells[0], site=site, type=g['primitives'][cells[0]]['type']))
    assert len(rows)==len({p['cell'] for p in rows})==len({p['site'] for p in rows})==60
    save(output, dict(rows=rows, passed=True))
    return rows

def signature_check():
    g=json.loads((REBUILD/'mapping_native/analysis/graph.json').read_bytes())
    source=REBUILD/'candidate02/rtl/v7_sfd_candidate.v'
    text=source.read_bytes().decode('gbk')
    assert "mailbox[15*32+:32]<=32'h53464401;" in text and 'mailbox<=0;' in text
    rows=[]
    for cam in range(4):
        prefix=f'source_diagnostics/cameras[{cam}].source/'
        row={'camera':cam,'cells':[]}
        for stem in ['mailbox[480]','host_bank[480]']:
            matches=[p for p in g['primitives'] if p.startswith(prefix+stem+'/') and p+'/Q' in g['pin_net']]
            assert len(matches)==1
            cell=matches[0]; rec=g['primitives'][cell]
            pins={p:g['pin_net'].get(cell+'/'+p) for p in ['D','CE','RS','CLK','Q']}
            assert all(pins.values())
            if stem.startswith('mailbox'): assert pins['D']=='/@$constant_1' and pins['RS']== '/@'+prefix+'cr[1]'
            else: assert pins['D']=='/@'+prefix+'mailbox[480]' and pins['RS']=='/@'+prefix+'hr[1]'
            row['cells'].append(dict(cell=cell,type=rec['type'],pins=pins,parameters=rec.get('parameters'),defaults=rec.get('default_parameters'),q_consumers=g['netpins'].get(pins['Q'])))
        rows.append(row)
    save('signature_semantics.json',dict(source=str(source),source_sha256=r.sha(source),rows=rows,
        rtl_semantics='async reset0; camera edge_vs && armed && !busy writes1; otherwise hold; host acquires mailbox only on snapshot_available && acquire_strobe; read word15 when valid',
        conclusion='Retain real signature storage and timing paths. D=1 does not imply Q=1.'))
    return g

def route(w, mapped_g, label, final=False, physical_options=''):
    attempt=E/label; attempt.mkdir()
    work=attempt/'work'; work.mkdir()
    copied=[]
    for folder in ['compile','synthesize','device_map']:
        shutil.copytree(w/folder,work/folder)
        for p in (w/folder).rglob('*'):
            if p.is_file():
                dest=work/folder/p.relative_to(w/folder);assert r.sha(p)==r.sha(dest)
                copied.append(dict(source=str(p),copy=str(dest),sha256=r.sha(p)))
    save(label+'/stage_copyhash.json',copied)
    adf=work/'device_map/v7_sdt_top_map.adf';pcf=work/'device_map/v7_sdt_top.pcf'
    plan=site_plan(mapped_g,w,label+'/native60_site_binding.json')
    helpraw=(r.BOARD/'build04_diagnostic_behavior_route01/help.log').read_bytes()
    for option in [b'-fix_hold_violation_in_route',b'-fix_hold_violation_iterations',b'-optimize_multi_corner_timing']: assert option in helpraw
    save(label+'/official_options.json',dict(help_sha256=r.sha(r.BOARD/'build04_diagnostic_behavior_route01/help.log'),iterations=12,inroute=True,multicorner=True))
    r.tool(label+'_pnr',r.ARCH+'add_constraint {'+pcf.as_posix()+'}\npnr -force_to_run -input_db_file {'+adf.as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_in_route TRUE -fix_hold_violation_iterations 12 -report_timing '+physical_options+'\n',work)
    routed=work/'place_route/v7_sdt_top_pnr.adf';assert routed.is_file()
    g=r.export(label+'/native',routed)
    c.E=attempt;c.R=attempt;c.P=work;c.W=w
    dump=attempt/'native/synthesis_export/synthesis_dump.txt'
    rawcdb=c.raw_cdb(dump)
    pp=actual_pairs(g)
    save(label+'/actual_pairs.json',dict(count=len(pp),rows=pp))
    # Storage recognition uses actual clock/D/Q connectivity, independent of gop type suffix.
    (attempt/'native60_site_binding.json').exists()
    placements={}
    pattern=rb'\(INSTANNOTATE\s+\(INSTREF\s+([^\s)]+)\s*\)\s+\(PLACE\s+([^\s]+)\s+\(DEVINSTREF\s+([^\s]+)\s+\(SITEREF\s+(\d+)\s+(\d+)'
    for m in re.finditer(pattern,dump.read_bytes()):placements.setdefault(m[1].decode().lstrip('\\'),[]).append(m[3].decode()+'_'+m[4].decode()+'_'+m[5].decode())
    site_rows=[]
    for item in plan:
        matches=[p for p in g['primitives'] if (p==item['source'] or p.startswith(item['source']+'/')) and p+'/CLK' in g['pin_net'] and any(p+'/'+x in g['pin_net'] for x in ['Q','Q0','L6Q','L5Q'])]
        assert len(matches)==1,(item,matches)
        sites=sorted(set(placements.get(matches[0],[])))
        assert sites==[item['site']],(item,sites)
        site_rows.append(dict(source=item['source'],cell=matches[0],site=sites[0],type=g['primitives'][matches[0]]['type']))
    save(label+'/routed60_sites.json',dict(rows=site_rows,passed=True))
    mappedcopy=attempt/'mapping_native/analysis';mappedcopy.mkdir(parents=True)
    (mappedcopy/'graph.json').write_text(json.dumps(mapped_g),encoding='ascii')
    retained=c.io_retention(g,placements)
    def report(name,options):
        dest=attempt/name
        r.tool(label+'_'+name,r.ARCH+'report_timing -force_to_run -input_db_file {'+routed.as_posix()+'} '+options+'\n',dest)
        return dest/'report_timing/v7_sdt_top.rtr'
    globalfile=report('global10','-delay_type min_max -report_exception TRUE -max_path 10 -nworst 1')
    allfile=report('crossings','-delay_type max -report_exception TRUE -input_pins TRUE -max_path '+str(2*len(pp))+' -nworst 1 -from '+c.pinlist(p['launch_CLK'] for p in pp)+' -to '+c.pinlist(p['capture_D'] for p in pp))
    sig=[p for p in pp if '/host_bank[480]/' in p['capture_D']]
    if sig: report('signature4','-delay_type max -report_exception TRUE -input_pins TRUE -max_path 8 -nworst 1 -from '+c.pinlist(p['launch_CLK'] for p in sig)+' -to '+c.pinlist(p['capture_D'] for p in sig))
    raw=globalfile.read_bytes();ss=c.summary(raw)
    minima={k:min((x['wns'] for x in rows),default=None) for k,rows in ss.items()}
    records=c.paths(allfile.read_bytes())
    expected={(p['launch_CLK'],p['capture_D'],corner) for p in pp for corner in ['slow','fast']}
    scored=[p for p in records if (p['start'],p['end'],p['corner']) in expected]
    coverage={(p['start'],p['end'],p['corner']) for p in scored if p['MaxDelay_15_238']}
    ddr=bool(re.search(rb'^\s*ddrphy_sysclk\s+131\.2500\s+MHz',raw,re.M))
    old_async=bool(re.search(rb'^\s*cmos[1-4]_pclk\s+asynchronous',raw,re.M))
    timing=len(minima)==10 and all(v is not None and v>=0 for v in minima.values()) and all(p['slack']>=0 for p in scored)
    result=dict(status='DIAGNOSTIC_PNR_COMPLETE' if not final else ('PASS_FUNCTIONAL_ROUTE' if timing and retained and coverage==expected and ddr and not old_async else 'FAIL_REAL_TIMING_OR_COVERAGE'),
        timing_pass=timing,retention_pass=retained,minima_ns=minima,critical_paths=c.paths(raw),crossing_records=scored,expected_pair_corners=len(expected),covered_15238=len(coverage),coverage_complete=coverage==expected,
        DDR131_25=ddr,old_camera_async=old_async,route=str(routed),route_sha256=r.sha(routed),map_sha256=r.sha(adf),CDB_sha256=r.sha(attempt/'native_CDB_raw.txt'),bit=False,program=False)
    save(label+'/RESULT.json',result)
    print('ACTUAL ROUTE RESULT '+label+' '+result['status']+' '+json.dumps(minima),flush=True)
    return result

def main():
    k,h=r.lock()
    try:
        g=signature_check()
        for stage in ['compile02','synthesize02','mapping02','mapping_native_export']:
            receipt=json.loads((REBUILD/(stage+'_receipt.json')).read_bytes());assert receipt['rc']==0 and not receipt['errors']
        # Existing global tool gate reads only the already-completed local board receipt.
        save('input_binding.json',dict(rebuild=str(REBUILD),map_sha256=r.sha(REBUILD/'candidate02/device_map/v7_sdt_top_map.adf'),controller_pid=os.getpid(),program=False))
        route(REBUILD/'candidate02',g,sys.argv[1] if len(sys.argv)>1 else 'diagnostic01')
        if (E/'continue_functional.py').exists():
            import continue_functional
            continue_functional.run()
        else:
            save('NEEDS_FUNCTIONAL_CONTINUATION.json',dict(reason='Diagnostic finished; final full crossing constraints still required',bit=False))
    finally:
        k.ReleaseMutex(h);k.CloseHandle(h)

if __name__=='__main__':
    try: main()
    except BaseException:
        save('failure_'+str(time.time_ns())+'.json',dict(traceback=traceback.format_exc(),bit=False,program=False))
        print(traceback.format_exc(),flush=True)
        raise
