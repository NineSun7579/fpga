from pathlib import Path
import subprocess,json,time,hashlib,re,shutil,sys
HERE=Path(__file__).resolve().parent
ATTEMPT=sys.argv[1] if len(sys.argv)>1 else 'physical_registered_02'
PROJECT=sys.argv[2] if len(sys.argv)>2 else 'project.pds'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):(HERE/name.replace('physical_registered_02',ATTEMPT)).write_text(json.dumps(data,indent=2),encoding='utf8')
def processes():
    p=subprocess.run(['powershell','-NoProfile','-Command',"ConvertTo-Json -InputObject @(Get-Process | Where-Object { $_.ProcessName -match '^(pds|pds_shell|ta)$' } | Select-Object Id,ProcessName) -Compress"],capture_output=True,check=True)
    return json.loads(p.stdout)
def main():
    (HERE/ATTEMPT).mkdir(exist_ok=False)
    recovered=HERE/'recovered_actual_syn.adf'
    shutil.copy2(HERE/'synthesize/v7_sdt_top_syn.adf',recovered)
    save('physical_registered_02/input_hashes.json',{str(p.relative_to(HERE)):sha(p) for folder in ['inputs','rtl','physical_constraints'] for p in (HERE/folder).rglob('*') if p.is_file()}|{PROJECT:sha(HERE/PROJECT),'recovered_actual_syn.adf':sha(recovered)})
    print('WAITING FOR PDS IDLE; independent route02',flush=True)
    while True:
        items=processes();save('physical_registered_02/processes.json',items)
        if not items:break
        time.sleep(10)
    stages=[]
    for stage,artifact,mark in [('dev_map','device_map/v7_sdt_top_map.adf','Device Map'),('pnr','place_route/v7_sdt_top_pnr.adf','Place & Route')]:
        assert not processes(), 'PDS became busy'
        selector=stage
        cmd=[str(PDS),'-project',str(HERE/PROJECT),'-run',selector,'-work_dir',str(HERE)]
        save('physical_registered_02/'+stage+'_launch.json',{'command':cmd,'started_at':time.time()})
        print('START',stage,cmd,flush=True)
        log=HERE/ATTEMPT/ (stage+'_shell.log')
        with log.open('xb') as f:p=subprocess.run(cmd,cwd=HERE,stdout=f,stderr=subprocess.STDOUT)
        data=log.read_bytes()
        errors=[s.decode('ascii','backslashreplace') for s in data.splitlines() if s.startswith(b'E:') or b'Timing-4003' in s]
        db=HERE/artifact
        marks=[s.decode('ascii','backslashreplace') for s in data.splitlines() if s.startswith(b'Process "') or (s.startswith(b'Design ') and b'successfully' in s)]
        result={'stage':stage,'exit_code':p.returncode,'errors':errors,'process_marks':marks,'artifact_exists':db.exists(),'artifact_sha256':sha(db) if db.exists() else None,'finished_at':time.time()}
        stages.append(result);save('physical_registered_02/result.json',stages)
        assert p.returncode==0 and not errors and db.exists() and db.stat().st_size>0 and ('Process "'+mark+'" started.') in marks and ('Process "'+mark+'" done.') in marks and any(s.startswith('Design ') and 'successfully' in s for s in marks),result
        print('VERIFIED REAL',stage,db,flush=True)
        if stage=='dev_map' and PROJECT=='standard_flow.pds' and sha(HERE/'synthesize/v7_sdt_top_syn.adf')!=sha(recovered):
            save('physical_registered_02/new_synthesis_requires_validation.json',{'new_syn_sha256':sha(HERE/'synthesize/v7_sdt_top_syn.adf'),'original_recovered_sha256':sha(recovered),'map_constraints_had_zero_Timing4003':True,'pnr_started':False,'required':'export new actual syn and compare all 1280 pairs, complement and topology before PNR'})
            print('REAL MAP COMPLETE; new synthesis graph validation required before PNR',flush=True)
            return
    save('physical_registered_02/acceptance_pending.json',{'routed_db_exists':True,'timing_accepted':False,'ten_groups_accepted':False,'cdc_accepted':False,'bitstream_permitted':False})
if __name__=='__main__':main()
