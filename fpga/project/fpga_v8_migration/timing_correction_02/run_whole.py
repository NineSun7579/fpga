"""Fresh whole implementation; structural synthesis gate before expensive route."""
from pathlib import Path
import subprocess,shutil,re,json,hashlib,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
M=HERE.parent
BASE=M/'whole_candidate_v3_timing_route_01'
WORK=M/'whole_candidate_v4_route_01'
PDS=Path(r'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v): (WORK/n).write_text(json.dumps(v,indent=2),encoding='utf-8')
def idle(label):
    p=subprocess.run(['powershell.exe','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName) -Compress'],capture_output=True,check=True)
    items=json.loads(p.stdout);save('processes_'+label+'.json',items)
    assert not items,'PDS single-instance gate'
def inventory():
    return {str(p.relative_to(WORK)):sha(p) for folder in ['inputs','rtl'] for p in (WORK/folder).rglob('*') if p.is_file()}
def main():
    assert not WORK.exists(),'Do not overwrite any implementation attempt'
    WORK.mkdir();idle('before_prepare')
    baseline={str(p):sha(p) for folder in ['inputs','rtl'] for p in (BASE/folder).rglob('*') if p.is_file()}
    for folder in ['inputs','rtl']:shutil.copytree(BASE/folder,WORK/folder)
    sources=[(HERE/'rtl/fpga_v8_pcie_fifo_h2f_tc02.v','fpga_v8_pcie_fifo_h2f_tc02.v'),
             (HERE/'rtl/axi_dma_write_tc02.v','axi_dma_write_tc02.v'),
             (M/'reset_fault_guard_02/fpga_v8_reset_fault_guard_02.v','fpga_v8_reset_fault_guard_02.v')]
    for p,n in sources:shutil.copyfile(p,WORK/'rtl'/n)
    top=WORK/'rtl/fpga_v8_cooperative_top_v2_rfg01.v';data=top.read_bytes();counts={}
    for old,new in [(b'fpga_v8_pcie_fifo_h2f_rfg01',b'fpga_v8_pcie_fifo_h2f_tc02'),
                    (b'fpga_v8_reset_fault_guard',b'fpga_v8_reset_fault_guard_02'),
                    (b'axi_dma_write',b'axi_dma_write_tc02')]:
        pattern=rb'\b'+old+rb'(?=\s*(?:#\s*\(|\w+\s*\())'
        data,count=re.subn(pattern,new,data);assert count>0,(old,count)
        counts[old.decode()]=count
    top.write_bytes(data)
    project=(BASE/'project.pds').read_bytes()
    for old,new in [(b'rtl/fpga_v8_pcie_fifo_h2f_rfg01.v',b'rtl/fpga_v8_pcie_fifo_h2f_tc02.v'),
                    (b'rtl/fpga_v8_reset_fault_guard.v',b'rtl/fpga_v8_reset_fault_guard_02.v'),
                    (b'inputs/source/axi_dma/axi_dma_write.v',b'rtl/axi_dma_write_tc02.v')]:
        assert project.count(old)==1;project=project.replace(old,new)
    project=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',project)
    (WORK/'project.pds').write_bytes(project)
    before=inventory();save('inputs_before.json',before)
    save('preparation.json',{'base':str(BASE),'binding_counts':counts,'corrected_sources':{str(p):sha(p) for p,n in sources},'constraints_unchanged':True,'physical_options_inherited':True,'board_ready':False})
    stages=[]
    for stage in ['compile','synthesize','pnr']:
        idle('before_'+stage)
        cmd=[str(PDS),'-project',str(WORK/'project.pds'),'-run',stage,'-work_dir',str(WORK)]
        print('Starting',stage,flush=True)
        with (WORK/(stage+'_shell.log')).open('xb') as log:
            p=subprocess.run(cmd,cwd=WORK,stdout=log,stderr=subprocess.STDOUT)
        stages.append({'stage':stage,'exit_code':p.returncode});save('flow_result.json',{'stages':stages,'timing_verified':False})
        assert p.returncode==0,stage+' failed'
        assert before==inventory(),'Local input drift'
        if stage=='synthesize':
            root=ET.parse(WORK/'synthesize/snr.db').getroot()
            tab=next(t for t in root.iter('table') if t.get('id')=='synthesize_check_timing_summary')
            checks={r.findall('data')[0].text:r.findall('data')[1].text for r in tab.findall('row')}
            save('structural_gate.json',checks)
            assert all(checks[k]=='0' for k in ['loops','latchs','latch_loops','no_clock','unexpandable_clocks']),checks
            print('Whole structural gate PASS',flush=True)
    assert baseline=={p:sha(Path(p)) for p in baseline},'Frozen baseline drift'
    save('inputs_after.json',inventory());save('baseline_guard.json',{'files':len(baseline),'unchanged':True})
    print('Route finished; final slow/fast STA audit still required',flush=True)
if __name__=='__main__':main()
