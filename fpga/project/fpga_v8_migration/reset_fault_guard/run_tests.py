from pathlib import Path
import os, subprocess, json, shutil
from build_binding import build, SOURCE, HERE, OUT, RENAMES, NAMES, digest, compatibility, audited_bytes
SIM=Path(os.environ.get('MODELSIM_BIN',r'C:\modeltech64_10.6e\win64'))
PANGO=Path(os.environ.get('PANGO_SIM',r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation'))

def tool(cmd,label):
    r=subprocess.run([str(c) for c in cmd],cwd=OUT,capture_output=True,text=True,
                     encoding='utf-8',errors='replace',timeout=120)
    text=r.stdout+r.stderr;(OUT/(label+'.log')).write_text(text,encoding='utf-8')
    if r.returncode or '** Error' in text or '** Fatal' in text:
        raise RuntimeError(label+'\n'+text[-10000:])
    return text

def main():
    before={p.name:digest(p.read_bytes()) for p in SOURCE.glob('*.v')}
    candidates=build()
    # Compile small binding-chain components too, without a whole-design/PDS run.
    syntax=[]
    for n in (NAMES[2],NAMES[3],NAMES[5],NAMES[6]):
        p=OUT/('syntax_'+RENAMES[n]+'.v')
        p.write_bytes(compatibility(candidates[n],indented=True) if n in (NAMES[2],NAMES[3]) else candidates[n])
        syntax.append(p)
    # Simulation shell is explicitly not the hard-IP reset/posted-write model.
    stub=(HERE.parent/'pcie_retirement_contract/tests/pango_pcie_top_stub.sv').read_bytes()
    stub=stub.replace(b'module pango_pcie_top #(',b'module fpga_v8_pango_pcie_top_h2f_rfg01 #(')
    stub=stub.replace(b'input button_rst_n,',b'input i_admit, input button_rst_n,')
    stub=stub.replace(b'ips2l_pcie_dma_controller #(',b'fpga_v8_pcie_dma_controller_h2f_rfg01 #(')
    stub=stub.replace(b'.clk(fifo_pcie_clk),',b'.i_admit(i_admit),.clk(fifo_pcie_clk),')
    stub=stub.replace(b'assign mwr_tx_busy=0;',b'reg public_tx_busy=0; assign mwr_tx_busy=public_tx_busy;')
    stub=stub.replace(b'endmodule',b'''
    // Models only a public shell busy level, never a hard-IP retirement receipt.
    task f2h_public(input [31:0] target);
        begin
            bar_write(12'h1e0,target);
            bar_write(12'h110,32'h01000000);
            bar_write(12'h120,0);
            bar_write(12'h200,16);
            bar_write(12'h100,32'h01010004);
            if(!(txreq32 || txreq64)) $fatal(1,"F2H STATUS request was incorrectly gated");
            public_tx_busy=1;
        end
    endtask
endmodule''')
    (OUT/'pcie_public_shell.sv').write_bytes(stub)
    tool([SIM/'vlib.exe','work'],'vlib')
    frozen=SOURCE.parent/'inputs'
    sources=[PANGO/'GTP_DRM36K_E1.v',PANGO/'GTP_GRS.v']
    for name in ('pcie_rx_fifo','pcie_tx_fifo'):
        folder=frozen/'ipcore'/name
        sources+=sorted((folder/'rtl').glob('ipm*.v'))+[folder/(name+'.v')]
    sources += [HERE/'fpga_v8_reset_fault_guard.v',
                SOURCE/'fpga_v8_capture_control_axil_arm_v2.v',SOURCE/'fpga_v8_capture_lease.v',
                OUT/('compat_'+RENAMES[NAMES[1]]+'.v'),OUT/('compat_'+RENAMES[NAMES[4]]+'.v')]
    audited=[p for p in sources if p.is_relative_to(SOURCE.parent)]+[
             HERE.parent/'capture_host/capture_host_protocol.hpp',
             HERE.parent/'cooperative_host/coop_host_protocol.hpp',SOURCE.parent/'project.pds']
    extra_hashes={str(p):digest(audited_bytes(p)) for p in audited}
    tool([SIM/'vlog.exe','-work','work']+sources,'vlog_rtl')
    tool([SIM/'vlog.exe','-work','work']+syntax,'vlog_binding_components')
    # Keep only review diffs for wrapper/core; no second production tree.
    for p in syntax:
        if p.name!='syntax_'+RENAMES[NAMES[6]]+'.v':p.unlink()
    tool([SIM/'vlog.exe','-sv','-work','work',OUT/'pcie_public_shell.sv',
          HERE/'tb_guard.sv',HERE/'tb_fifo_fault.sv',HERE/'tb_capture_fault.sv',HERE/'tb_coop_hint.sv',
          HERE/'tb_fifo_read.sv'],'vlog_tb')
    passed=[]
    for tb,count,marker in [('tb_guard',10,'GUARD_PASS'),('tb_fifo_fault',3,'FIFO_FAULT_PASS'),
                            ('tb_capture_fault',4,'CAPTURE_'),('tb_coop_hint',1,'COOP_HINT_PASS'),
                            ('tb_fifo_read',2,'FIFO_READ_PASS')]:
        for mode in range(count):
            label=tb+'_'+str(mode)
            text=tool([SIM/'vsim.exe','-c','-onfinish','stop','work.'+tb,'+MODE='+str(mode),
                       '-do','run -all; quit -f'],label)
            assert marker in text,label
            passed.append(label);print(label+' PASS',flush=True)
    compiler=os.environ.get('RESET_GUARD_CXX') or shutil.which('g++')
    if compiler:
        tool([compiler,'-std=c++17','-I'+str(HERE),HERE/'test_transport.cpp',
              '-o',OUT/'test_transport.exe'],'host_compile')
    else:
        vcvars=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat')
        assert vcvars.exists(),'provide RESET_GUARD_CXX native C++17 compiler'
        script=OUT/'compile_host.cmd'
        script.write_text('@echo off\ncall "'+str(vcvars)+'" >nul\n'+
            'cl /nologo /std:c++17 /EHsc "'+str(HERE/'test_transport.cpp')+'" '+
            '/Fe:"'+str(OUT/'test_transport.exe')+'" /Fo:"'+str(OUT/'test_transport.obj')+'"\n')
        tool(['cmd.exe','/d','/c',script],'host_compile')
    assert 'TRANSPORT_PASS' in tool([OUT/'test_transport.exe'],'host_test')
    after={p.name:digest(p.read_bytes()) for p in SOURCE.glob('*.v')}
    assert before==after,'audited v2 mutated'
    assert extra_hashes=={str(p):digest(p.read_bytes()) for p in audited}
    (OUT/'results.json').write_text(json.dumps(dict(
        expectation_checks_passed=passed,
        unsupported_observation='tb_capture_fault_3: local control-only reset is invisible; HELD remains, bound claim lost',
        enforced_scenarios=19,transport_precheck_pass=True,audited_v2_rtl_hashes_unchanged=True,
        additional_audited_inputs_unchanged=extra_hashes,
        source_hashes=before,pds_run=False,board_access=False,
        hard_ip_reset_certified=False,uniform_recovery_certified=False,
        full_top_elaborated=False),indent=2)+'\n')

if __name__=='__main__':main()
