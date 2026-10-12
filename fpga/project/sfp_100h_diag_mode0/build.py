"""Sequential isolated build, strong route, full final STA, pin and bit provenance."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, time
H=Path(__file__).resolve().parent
W=H/'work'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
ARCH='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o): p.write_text(json.dumps(o,indent=2),encoding='utf8')
def check():
    for manifest,absolute in [('original_sha256.json',True),('input_sha256.json',False)]:
        data=json.loads((H/manifest).read_text())
        for n,h in data.items():
            p=Path(n) if absolute else H/n
            if not p.is_file() or sha(p)!=h: raise RuntimeError('Changed protected input: '+n)
    print('PASS original and isolated input hashes')
def idle():
    q="Get-Process | Where-Object {$_.ProcessName -match '^(pds|pds_shell|pnr|ta|bitgen)$'} | Select-Object Id,ProcessName | ConvertTo-Json -Compress"
    busy=subprocess.check_output(['powershell','-NoProfile','-Command',q],text=True).strip()
    if busy: raise RuntimeError('Wait for the current 50K/vendor flow to finish: '+busy)
def execute(dest,name,args,cwd):
    idle();check()
    save(H/'status.json',{'status':'running','stage':name,'run':str(dest)})
    print('STAGE '+name+': '+subprocess.list2cmdline([str(x) for x in args]),flush=True)
    with (dest/(name+'.log')).open('wb') as f:
        p=subprocess.Popen([str(x) for x in args],cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in iter(p.stdout.readline,b''):
            f.write(line);f.flush();print(line.decode('gb18030',errors='replace').rstrip(),flush=True)
        code=p.wait()
    text=(dest/(name+'.log')).read_bytes().decode('gb18030',errors='replace')
    if code or re.search(r'^E:|invalid command name|Public-4023|no objects matched|empty collection',text,re.M|re.I):
        raise RuntimeError('Vendor stage failed: '+name)
    check()
def action(dest,name,tcl,work):
    work.mkdir(parents=True,exist_ok=True)
    script=dest/(name+'.tcl');script.write_text(ARCH+tcl,encoding='ascii')
    execute(dest,name,[PDS,'-file',script,'-work_dir',work,'-project_name',name],work)
def pinmap(p):
    out={}
    for l in p.read_text(errors='replace').splitlines():
        v=l.split('|')
        if len(v)>=7 and v[4]: out[v[4]]=v[:4]+v[5:7]
    if len(out)<100: raise RuntimeError('Incomplete pin report '+str(p))
    return out
def auditpins(report):
    expected=pinmap(H/'baseline/top_prr.prt');actual=pinmap(report)
    if actual!=expected: raise RuntimeError('Routed port/ball/site/bank/direction mismatch vs 192245')
    for fdc in (H/'source/constraints').glob('*.fdc'):
        for line in fdc.read_bytes().decode('ascii',errors='replace').splitlines():
            if line.strip().startswith('#'): continue
            m=re.search(r'define_attribute\s+\{p:([^}]+)\}\s+\{(?:PAP_LOC|PAP_IO_LOC)\}\s+\{([^}]+)\}',line)
            if m and m[1] in ('ref_clk_p','ref_clk_n'):
                # Dedicated pads are absent from ordinary-I/O package report.
                expected={'ref_clk_p':'F6','ref_clk_n':'E6'}
                if m[2]!=expected[m[1]]: raise RuntimeError('Dedicated reference pin changed')
                continue
            if m and (m[1] not in actual or actual[m[1]][0]!=m[2]):
                raise RuntimeError('Missing or mismatched FDC/routed ball '+m[1])
    return {'ports':len(actual),'baseline_pin_sha256':sha(H/'baseline/top_prr.prt'),'routed_pin_sha256':sha(report),'identical':True}
def phy(dump):
    text=dump.read_bytes().decode('gb18030',errors='replace')
    sites={n:(impl,dev,x,y) for n,impl,dev,x,y in re.findall(r'\(INSTANNOTATE \(INSTREF\s+(\S+)\s*\)\s*\(PLACE\s+(\S+)\s+\(DEVINSTREF\s+(\S+)\s+\(SITEREF\s+(\d+)\s+(\d+)\)',text) if 'HSST' in dev}
    nets={}
    for name,block in re.findall(r'^          \(NET\s+([^\n]+)\n(.*?)(?=^          \))',text,re.M|re.S):
        name=name.strip();m=re.fullmatch(r'\(INDEXED (\S+) (\d+)\)',name)
        if m:name=f'{m[1]}[{m[2]}]'
        nets[name.lstrip('\\')]=block
    ports=['ref_clk_p','ref_clk_n']+[f'{d}{p}[{i}]' for d in ('rx','tx') for p in ('p','n') for i in range(2)]+[f'sfp_l2{d}{p}' for d in ('rx','tx') for p in ('p','n')]
    connections={}
    for port in ports:
        block=nets.get(port,'')
        pads=re.findall(r'\(PORTREF\s+(PAD_\w+)\s+\(INSTREF\s+(\S+)\s*\)',block)
        if not pads: raise RuntimeError('Missing dedicated PHY connection '+port)
        connections[port]=sorted(pads)
    if len(sites)<3: raise RuntimeError('Incomplete actual HSST placements')
    return {'hsst_sites':sites,'dedicated_connections':connections}
def run():
    idle();check()
    dest=H/('run_'+time.strftime('%Y%m%d_%H%M%S'));dest.mkdir()
    for n in ('compile','synthesize','device_map','place_route'):
        if (W/n).exists(): raise RuntimeError('Use a fresh private work directory; existing '+n)
    flow=W/'flow.pds';shutil.copy2(W/'project.pds',flow)
    for stage in ('compile','synthesize','dev_map'):
        execute(dest,stage,[PDS,'-project',flow,'-run',stage,'-work_dir',W],W)
    mapped=W/'device_map/top_map.adf';pcf=W/'device_map/top.pcf'
    save(dest/'mapped_provenance.json',{'mapped_sha256':sha(mapped),'pcf_sha256':sha(pcf)})
    tcl='add_constraint -physical -pcf {'+pcf.as_posix()+'}\nset mapped {'+mapped.as_posix()+'}\n'
    tcl+='pnr -input_db_file $mapped -force_to_run -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 500 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clock_path_cross_srb 200 -fix_hold_violation_threshold_for_clk_tree 200 -max_hold_violated_paths_num 15000 -fast_router FALSE\n'
    action(dest,'strong_pnr',tcl,W)
    route=W/'place_route/top_pnr.adf';rh=sha(route)
    shutil.copytree(W/'place_route',dest/'routed')
    save(dest/'pin_audit.json',auditpins(W/'place_route/top_prr.prt'))
    for name,db in [('baseline_phy',H/'baseline/top_pnr.adf'),('routed_phy',route)]:
        dump=dest/(name+'.txt')
        action(dest,name,'.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',dest/name)
    reference=phy(dest/'baseline_phy.txt');actual=phy(dest/'routed_phy.txt')
    if reference!=actual: raise RuntimeError('Actual HSST placement or dedicated pad connectivity changed vs 192245')
    save(dest/'phy_audit.json',{'identical':True,'actual':actual,'baseline_dump_sha256':sha(dest/'baseline_phy.txt'),'routed_dump_sha256':sha(dest/'routed_phy.txt')})
    sta=dest/'final_sta'
    action(dest,'full_sta','report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n',sta)
    report=sta/'report_timing/top.rtr'
    text=report.read_bytes().decode('gb18030',errors='replace')
    for token in ('Timing Models: Production','Timing analysis mode : multi corner','Design Summary : All Constraints Met.','sfp_fabric','cam1_sccb','cam2_sccb','cam3_sccb','cam4_sccb'):
        if token not in text: raise RuntimeError('Final STA missing '+token)
    if 'Slack (VIOLATED)' in text: raise RuntimeError('Final STA has violations')
    # Report every bundled-data endpoint separately; clock totals also contain legacy CDCs.
    cdc_tcl='report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type max -nworst 1 -max_path 1\n'
    cdc_tcl+='report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -from [get_cells -hierarchical {*u_sfp_diag*held*}] -to [get_cells -hierarchical {*u_sfp_diag*data_sync0*}] -delay_type max -nworst 1 -max_path 512 -input_pins TRUE -report_exception TRUE\n'
    action(dest,'cdc_sta',cdc_tcl,dest/'cdc_sta')
    cdc=dest/'cdc_sta/report_timing/top.rtr'
    ct=cdc.read_bytes().decode('gb18030',errors='replace')
    endpoints=set(re.findall(r'(?im)^\s*Endpoint\s*:\s*([^\r\n]+)',ct))
    mode=1 if re.search(rb'parameter\s+SFP_NEW_PARSER\s*=\s*1',(H/'source/top.v').read_bytes()) else 0
    # Fifteen counter words plus link are dynamic; signature/reset bits may merge.
    minimum=481+mode
    if not minimum<=len(endpoints)<=512 or any('data_sync0' not in e for e in endpoints) or 'Slack (VIOLATED)' in ct or '4.000' not in ct:
        raise RuntimeError(f'Cannot prove at least {minimum} nonconstant bounded CDC endpoints; inspect cdc_sta before bitgen')
    if sha(route)!=rh: raise RuntimeError('STA changed routed DB')
    save(dest/'final_sta_proof.json',{'route_sha256':rh,'report_sha256':sha(report),'cdc_report_sha256':sha(cdc),'cdc_endpoints':len(endpoints),'setup_hold_multi_corner':True})
    bitwork=dest/'bitgen'
    action(dest,'bitgen','gen_bit_stream -input_db_file {'+route.as_posix()+'} -force_to_run -create_bit_file TRUE\n',bitwork)
    bits=list(bitwork.rglob('*.sbit'))
    if len(bits)!=1 or sha(route)!=rh: raise RuntimeError('Bit provenance mismatch')
    shutil.copy2(bits[0],dest/'top.sbit');check()
    save(H/'status.json',{'status':'complete','mode':mode,'bit':str(dest/'top.sbit'),'bit_sha256':sha(dest/'top.sbit'),'route_sha256':rh,'report_sha256':sha(report),'pin_audit':True})
    print('BUILD_ARTIFACT: '+str(dest/'top.sbit'))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');a.add_argument('--run',action='store_true');args=a.parse_args()
    try:
        if args.run: run()
        else: check()
    except Exception as e:
        if args.run: save(H/'status.json',{'status':'blocked','reason':str(e)})
        raise
