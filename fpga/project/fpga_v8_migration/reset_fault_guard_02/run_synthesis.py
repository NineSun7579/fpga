from pathlib import Path
import subprocess,json,hashlib,re
HERE=Path(__file__).resolve().parent
WORK=HERE/'synthesis_02'
PDS=Path(r'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not WORK.exists(),'Use a fresh synthesis directory'
    check=subprocess.run(['powershell.exe','-NoProfile','-Command',
        'ConvertTo-Json -InputObject @(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName) -Compress'],capture_output=True,check=True)
    assert not json.loads(check.stdout),'PDS must be idle'
    WORK.mkdir()
    (WORK/'processes_before.json').write_bytes(check.stdout)
    src=HERE/'fpga_v8_reset_fault_guard_02.v'
    before=sha(src)
    (WORK/'component.fdc').write_text('create_clock -name free_clk -period 40 [get_ports {free_clk}]\ncreate_clock -name axi_clk -period 7.619 [get_ports {axi_clk}]\ncreate_clock -name pcie_clk -period 8 [get_ports {pcie_clk}]\n',encoding='ascii')
    template=HERE.parent/'component_synthesis/coop_control_01/project.pds'
    data=template.read_bytes().replace(b'../../cooperative_control/fpga_v8_coop_control_axil.v',b'../fpga_v8_reset_fault_guard_02.v')
    data=data.replace(b'fpga_v8_coop_control_axil',b'fpga_v8_reset_fault_guard_02')
    data=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',data)
    (WORK/'project.pds').write_bytes(data)
    (WORK/'template_provenance.json').write_text(json.dumps({'template':str(template),'sha256':sha(template),'changes':['registered source and module names','task states reset to zero'],'timing_scope':'component structure only; no timing signoff'},indent=2))
    stages=[]
    for stage in ['compile','synthesize']:
        cmd=[str(PDS),'-project',str(WORK/'project.pds'),'-run',stage,'-work_dir',str(WORK)]
        with (WORK/(stage+'.log')).open('xb') as log:
            p=subprocess.run(cmd,cwd=WORK,stdout=log,stderr=subprocess.STDOUT)
        stages.append({'stage':stage,'exit_code':p.returncode})
        (WORK/'result.json').write_text(json.dumps({'stages':stages,'source_unchanged':sha(src)==before,'source_sha256':before},indent=2))
        assert p.returncode==0,stage+' failed'
        print(stage,'PASS',flush=True)
    assert sha(src)==before
if __name__=='__main__':main()
