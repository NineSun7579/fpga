"""Static source/registration checks only; no hardware or allocator calls."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
R = ROOT / 'fpga_v8_migration/whole_candidate_v2_route_01'
manifest = json.loads((HERE / 'source_manifest.json').read_text(encoding='ascii'))
changed = []
for item in manifest:
    path = ROOT / item['path']
    data = path.read_bytes()
    if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        changed.append(item['path'])
assert not changed, changed
checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)
top = (R / 'rtl/fpga_v8_cooperative_top_v2.v').read_bytes()
fifo = (R / 'rtl/fpga_v8_pcie_fifo_h2f.v').read_bytes()
arm = (R / 'rtl/fpga_v8_capture_control_axil_arm_v2.v').read_bytes()
lease = (R / 'rtl/fpga_v8_capture_lease.v').read_bytes()
project = (R / 'project.pds').read_bytes()
check('direct DDR-init fabric reset', b'assign axi_rst = ~ddr_init_done;' in top)
check('same core and AXI clock', b'assign axi_clk = core_clk;' in top)
for name in ['fpga_v8_capture_control_axil_arm_v2', 'fpga_v8_pcie_fifo_h2f',
             'fpga_v8_pcie_dma_h2f', 'fpga_v8_pcie_dma_controller_h2f',
             'fpga_v8_pango_pcie_top_h2f', 'fpga_v8_cooperative_top_v2']:
    check('registered ' + name, ('(_file "rtl/' + name + '.v"').encode() in project)
check('credit OR reset', b'rx_retirement_epoch_rst = axi_rst | fifo_pcie_rst;' in fifo)
writer = fifo[fifo.index(b'always @(posedge axi_clk) begin\n    if (axi_rst)'):]
writer = writer[:writer.index(b'\nend\n') + len(b'\nend\n')]
check('writer does not share credit OR reset', b'fifo_pcie_rst' not in writer and b'rx_retire_axi_rst2' not in writer)
check('writer B wait preserved without AXI reset', b'assign axi_bready = (state == S_BRESP_WAIT);' in fifo)
check('split FIFO resets', bool(re.search(rb'\.wr_rst\s*\(fifo_pcie_rst\s*\)', fifo)) and bool(re.search(rb'\.rd_rst\s*\(axi_rst\s*\)', fifo)))
check('configReady limited to capture engine and lease', b'assign config_ready = !rst && all_free && engine_idle && !epoch_start;' in lease)
check('ARM staging has separate doorbell', b"32'h0c: staged_generation<=merge_bytes" in arm and b'pending<=ARM_WAIT' in arm)
allocator = (ROOT / 'fpga_v8_migration/epoch_allocator/allocate_epoch.py').read_bytes()
check('allocator explicit provision and existing-only allocation', b'def initialize(' in allocator and b'data = _read(directory_fd, path.name, domain)' in allocator)
check('allocator journal durable before return', b'os.fsync(directory_fd)' in allocator and b"raise OverflowError" in allocator)
result = {'kind': 'STATIC_AUDIT_ONLY', 'manifest_files_verified': len(manifest),
          'checks': checks, 'board_recovery_certified': False,
          'journal_provisioned': False, 'cycle_simulation_run': False,
          'source_mutations': False}
(HERE / 'validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='ascii')
print(json.dumps(result))
