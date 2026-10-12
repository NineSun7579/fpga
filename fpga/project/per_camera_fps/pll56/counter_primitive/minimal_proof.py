"""Single isolated 32-bit primitive counter synthesis, guarded by shared lock."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import tempfile
import time

OWN = Path(__file__).resolve().parent
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
LOCK = OWN.parent.parent / 'fpga/build.lock'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    run = Path(tempfile.mkdtemp(prefix='minimal32_', dir=OWN))
    raw = (OWN / 'ov5640_cdc.v').read_bytes()
    counter = re.search(rb'module pll56_source_drop_counter\s*\([\s\S]+?endmodule', raw).group()
    wrapper = b'''module top(input clk, input rst, input frame, input increment,
output [31:0] value);
pll56_source_drop_counter u_src_drop(.clk(clk), .rst(rst), .frame(frame),
.increment(increment), .value(value));
endmodule
'''
    source = run / 'counter.v'
    source.write_bytes(counter + b'\n' + wrapper)
    project = run / 'flow.pds'
    project.write_bytes(b'''(_flow fab_demo "2022.2-SP6.4"
 (_version "1.1.0")
 (_status "initial")
 (_project (_option prj_work_dir (_string ".")) (_option prj_impl_dir (_string ".")))
 (_task tsk_setup
  (_widget wgt_select_arch (_input (_part (_family Logos2) (_device PG2L100H) (_speedgrade -6) (_package FBG484))))
  (_widget wgt_my_design_src (_input (_file "counter.v" + "top:" (_format verilog))))
 )
 (_task tsk_compile (_command cmd_compile (_option top_module (_string "top"))))
 (_task tsk_synthesis (_command cmd_synthesize (_option selected_syn_tool_opt (_integer 2))))
)
''')
    receipt = dict(status='prepared', run=str(run), candidate_sha256=sha(OWN / 'ov5640_cdc.v'),
                   source_sha256=sha(source), counter_bytes_sha256=hashlib.sha256(counter).hexdigest(),
                   attributes_added=[], configuration='Existing explicit GTP_DFF_C, INIT=0, GRS_EN=TRUE; ADS tool 2; same device',
                   full_build_launched=False, hardware_access=False)
    def save():
        (run / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        (OWN / 'minimal_latest.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    save()
    acquired = False
    try:
        try:
            with LOCK.open('x') as f:
                f.write('minimal32 proof ' + str(run))
            acquired = True
        except FileExistsError:
            receipt.update(status='blocked_vendor_busy', error='Shared fpga/build.lock exists; no PDS launched')
            return
        check = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
            "@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue).Count"], capture_output=True)
        assert check.returncode == 0
        if int(check.stdout.strip()) != 0:
            receipt.update(status='blocked_vendor_busy', error='PDS processes present; no PDS launched')
            return
        for stage in ('compile', 'synthesize'):
            receipt.update(status='running', stage=stage)
            save()
            command = [str(PDS), '-project', str(project), '-run', stage, '-work_dir', str(run)]
            with (run / (stage + '.log')).open('xb') as log:
                result = subprocess.run(command, cwd=run, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=180)
            assert result.returncode == 0, stage + ' failed: ' + str(result.returncode)
        net = run / 'synthesize/top_syn.vm'
        b = net.read_bytes()
        cells = [c.group() for c in re.finditer(rb'\n    GTP_DFF[^;]+;', b)]
        assert len(cells) == 32, len(cells)
        assert all(re.match(rb'\n    GTP_DFF_C\s', c) for c in cells)
        assert all(not re.search(rb'\.CE\s*\(', c) for c in cells)
        cs = run / 'synthesize/top_controlsets.txt'
        assert not any(b'CE(' in line for line in cs.read_bytes().splitlines()), 'Dynamic CE in minimal counter'
        receipt.update(status='PASS', cells=[c.decode('ascii', 'replace') for c in cells],
                       counter_flops=32, netlist_sha256=sha(net), controlsets_sha256=sha(cs))
    except Exception as error:
        receipt.update(status='FAIL', error=str(error))
        raise
    finally:
        receipt['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save()
        if acquired:
            LOCK.unlink()
        print(receipt['status'], run, receipt.get('error', ''), flush=True)

if __name__ == '__main__':
    main()
