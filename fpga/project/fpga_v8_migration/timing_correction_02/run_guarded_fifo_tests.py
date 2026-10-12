"""Actual new guard/FIFO integration, public shell model and official FIFOs."""
from pathlib import Path
import sys,importlib.util,subprocess,json,hashlib
HERE=Path(__file__).resolve().parent
M=HERE.parent;OLD=M/'reset_fault_guard';OUT=HERE/'guarded_artifacts'
sys.path.insert(0,str(OLD))
from build_binding import compatibility
SIM=Path(r'C:\modeltech64_10.6e\win64')
PANGO=Path(r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation')
BASE=M/'whole_candidate_v4_route_01'
def run(cmd,label):
    r=subprocess.run([str(x) for x in cmd],cwd=OUT,capture_output=True,timeout=90)
    data=r.stdout+r.stderr;(OUT/(label+'.log')).write_bytes(data)
    assert not r.returncode and b'** Error' not in data and b'** Fatal' not in data,data.decode(errors='replace')
    return data
def main():
    OUT.mkdir(exist_ok=True)
    pinned=[BASE/'rtl'/n for n in ['fpga_v8_reset_fault_guard_02.v','fpga_v8_pcie_fifo_h2f_tc02.v','fpga_v8_pcie_dma_controller_h2f_rfg01.v']]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pinned}
    fifo=OUT/'fifo_compat.v';fifo.write_bytes(compatibility((BASE/'rtl/fpga_v8_pcie_fifo_h2f_tc02.v').read_bytes(),[b'wire fifo_rx_almost_full;']))
    ctrl=OUT/'controller_compat.v';ctrl.write_bytes(compatibility((BASE/'rtl/fpga_v8_pcie_dma_controller_h2f_rfg01.v').read_bytes(),[b'wire total_length_cfg_done;']))
    shell=OUT/'pcie_public_shell.sv';shell.write_bytes((OLD/'artifacts/pcie_public_shell.sv').read_bytes())
    sources=[PANGO/'GTP_DRM36K_E1.v',PANGO/'GTP_GRS.v']
    for name in ['pcie_rx_fifo','pcie_tx_fifo']:
        folder=BASE/'inputs/ipcore'/name
        sources+=sorted((folder/'rtl').glob('ipm*.v'))+[folder/(name+'.v')]
    sources += [BASE/'rtl/fpga_v8_reset_fault_guard_02.v',fifo,ctrl,shell]
    tests=[]
    for name in ['tb_fifo_fault','tb_fifo_read']:
        target=OUT/(name+'.sv')
        target.write_bytes((OLD/(name+'.sv')).read_bytes().replace(b'fpga_v8_reset_fault_guard #',b'fpga_v8_reset_fault_guard_02 #').replace(b'fpga_v8_pcie_fifo_h2f_rfg01 dut',b'fpga_v8_pcie_fifo_h2f_tc02 dut'))
        tests.append(target)
    run([SIM/'vlib.exe','work'],'vlib')
    run([SIM/'vlog.exe','-sv']+sources+tests,'compile')
    cases=[]
    for name,count,marker in [('tb_fifo_fault',3,b'FIFO_FAULT_PASS'),('tb_fifo_read',2,b'FIFO_READ_PASS')]:
        for mode in range(count):
            label=name+'_'+str(mode)
            data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.'+name,'+MODE='+str(mode),'-do','run -all; quit -f'],label)
            assert marker in data;cases.append(label);print('PASS',label,flush=True)
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pinned}
    (OUT/'results.json').write_text(json.dumps({'passed':cases,'source_hashes':before,'source_unchanged':True,'hard_ip_or_posted_visibility_claimed':False},indent=2))
if __name__=='__main__':main()
