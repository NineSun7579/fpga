from pathlib import Path
import os
import re
import subprocess
import json
from prepare import prepare, refs, HERE, SOURCE, OUT, NAMES

SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
PANGO = Path(r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation')

def tool(args, label):
    p = subprocess.run([str(a) for a in args], cwd=OUT, capture_output=True,
                       encoding='utf-8', errors='replace', timeout=120)
    text = p.stdout+p.stderr
    (OUT/(label+'.log')).write_text(text, encoding='utf-8')
    if p.returncode or '** Error' in text or '** Fatal' in text:
        raise RuntimeError(label+'\n'+text[-7000:])
    return text

def hoist(source, extra=b''):
    # Simulation compatibility ONLY, existing mixed-Verilog forward declarations.
    declarations=[]
    def move(m):
        decl=m[0]; clean=re.sub(rb'/\*.*?\*/',b'',decl,flags=re.S)
        if b'=' in clean and not clean.lstrip().startswith(b'localparam'):
            assert clean.lstrip().startswith(b'wire'), decl
            left,rhs=clean[:-1].split(b'=',1)
            name=re.search(rb'(\w+)\s*$',left)[1]
            declarations.append(left.rstrip()+b';')
            return b'assign '+name+b' ='+rhs+b';'
        declarations.append(decl);return b''
    body=re.sub(rb'(?m)^\s*(?:wire|reg|localparam)\s+[^;]*;',move,source)
    at=body.index(b');')+2
    return body[:at]+b'\n'+extra+b'\n'+b'\n'.join(declarations)+b'\n'+body[at:]

def main():
    before=prepare()
    ctrl=SOURCE/'inputs/source/pcie_dma/pcie_dma_ctrl'
    common=[PANGO/'GTP_DRM36K_E1.v',PANGO/'GTP_GRS.v']
    for name in ('pcie_rx_fifo','pcie_tx_fifo'):
        directory=SOURCE/'inputs/ipcore'/name
        common+=sorted((directory/'rtl').glob('ipm*.v'))+[directory/(name+'.v')]
    common += [ctrl/(name+'.v') for name in ('ips2l_pcie_dma_mwr_tx_ctrl',
        'ips2l_pcie_dma_tx_mwr_rd_ctrl','ips2l_pcie_dma_rd_ctrl','pgs_pciex4_prefetch_fifo_v1_2',
        'fifo/pgs_pciex4_fifo_v1_2','fifo/pgs_pciex4_fifo_ctrl',
        'fifo/ipm_distributed_sdpram_v1_2_distributed_fifo')]
    common += [PANGO/'GTP_DRM16X4.v']
    passed=[]
    for kind in ('original','candidate'):
        lib='work_'+kind
        tool([SIM/'vlib.exe',lib],kind+'_vlib')
        copies=[]
        for name in NAMES:
            path=OUT/(kind+'_'+name+'.v')
            compat=OUT/('compat_'+path.name)
            extra=b'wire fifo_rx_almost_full;' if 'fifo' in name else b'wire total_length_cfg_done;'
            compat.write_bytes(hoist(path.read_bytes(), extra))
            copies.append(compat)
        defines=['+define+CANDIDATE'] if kind=='candidate' else []
        tool([SIM/'vlog.exe','-sv','-work',lib]+defines+common+copies+
             [HERE/'f2h_production_shell.sv',HERE/'tb_f2h.sv'],kind+'_vlog')
        modes=range(10) if kind=='candidate' else (0,1,2,3)
        for mode in modes:
            label=f'{kind}_{mode}'
            text=tool([SIM/'vsim.exe','-c','-onfinish','stop',lib+'.tb_f2h',
                       f'+MODE={mode}','-do','run -all; quit -f'],label)
            assert 'F2H_PATH_PASS' in text, label
            passed.append({'test':label,'trace':re.search(r'F2H_PATH_PASS[^\n]*',text)[0]})
            print(passed[-1],flush=True)
    after=refs()
    assert before==after,'read-only sources changed'
    (OUT/'references_after.json').write_text(json.dumps(after,indent=2)+'\n')
    (OUT/'results.json').write_text(json.dumps({'tests':passed,'source_hashes_unchanged':True,
        'board_access':False,'pds_run':False,'hard_ip_simulated':False,
        'physical_ordering_proved':False,'candidate_registered':False},indent=2)+'\n')

if __name__=='__main__':main()
