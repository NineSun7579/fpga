"""Byte-level retained-source copies/diffs only. Never writes the routed tree."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / 'whole_candidate_v3_timing_route_01'
OUT = HERE / 'artifacts'
NAMES = ('fpga_v8_pcie_fifo_h2f_rfg01', 'fpga_v8_pcie_dma_controller_h2f_rfg01')

def once(data, old, new):
    assert data.count(old) == 1, old
    return data.replace(old, new)

def refs():
    paths = list((SOURCE/'rtl').glob('*.v')) + list(
        (SOURCE/'inputs/source/pcie_dma').rglob('*.v'))
    paths += list((SOURCE/'inputs/source/axi_crossbar').rglob('*.v'))
    paths += [SOURCE/'project.pds', ROOT/'driver_ownership_audit/board_files/000_pango_pci_driver.c',
              ROOT/'driver_ownership_audit/board_files/001_pango_pci_driver.h',
              ROOT/'driver_ownership_audit/board_files/003_pango_pci_driver_fixed_20260926.ko']
    paths += list((ROOT/'cooperative_linux_transport').glob('*.hpp'))
    return {str(p.relative_to(ROOT)).replace('\\','/'):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

def prepare():
    OUT.mkdir(exist_ok=True)
    before = refs()
    (OUT/'references_before.json').write_text(json.dumps(before, indent=2)+'\n')
    for name in NAMES:
        data = (SOURCE/'rtl'/f'{name}.v').read_bytes()
        original = once(data, ('module '+name).encode(), ('module '+name+'_dcb01_original').encode())
        fixed = once(data, ('module '+name).encode(), ('module '+name+'_dcb01_candidate').encode())
        if 'fifo' in name:
            # Fail-stop in the actual reader, before bad beats enter TX FIFO.
            fixed = once(fixed, b'assign fpga_data_ready = fpga_data_ready_r;',
                         b'assign fpga_data_ready = fpga_data_ready_r && !f2h_fault_sync2;')
            fixed = once(fixed, b'assign fpga_tx_done = fpga_tx_done_r;',
                         b'assign fpga_tx_done = fpga_tx_done_r && !f2h_fault_sync2;')
            fixed = once(fixed, b'assign axi_arvalid = (r_state == R_ADDR_SEND);',
                         b'assign axi_arvalid = (r_state == R_ADDR_SEND) && !f2h_fault;')
            fixed = once(fixed, b'axi_rvalid && axi_rready && (axi_rid == 4\'b0000);',
                         b'axi_rvalid && axi_rready && (axi_rid == 0) && !f2h_bad_beat && !f2h_fault;')
            extra = b'''
// dcb01 isolated candidate: latch ARLEN at acceptance; check EVERY accepted R.
// Sticky until coordinated reset, including across commands. No timeout recovery.
reg f2h_fault;
reg [4:0] f2h_burst_left;
reg [31:0] f2h_beats_seen;
wire f2h_bad_beat = (axi_rresp != 2'b00) || (axi_rid != 0) ||
    (f2h_burst_left == 0) || (axi_rlast != (f2h_burst_left == 1)) ||
    (f2h_beats_seen >= dma_total_beats);
always @(posedge axi_clk or posedge rx_retire_axi_rst2) begin
    if (rx_retire_axi_rst2) begin
        f2h_fault <= 0; f2h_burst_left <= 0; f2h_beats_seen <= 0;
    end else begin
        if (tx_runing_axi_rising) f2h_beats_seen <= 0;
        if (axi_arvalid && axi_arready) begin
            if (f2h_burst_left != 0) f2h_fault <= 1;
            f2h_burst_left <= {1'b0,axi_arlen} + 5'd1;
        end
        if (axi_rvalid && axi_rready) begin
            if (f2h_bad_beat) f2h_fault <= 1;
            else begin
                f2h_burst_left <= f2h_burst_left - 1'b1;
                f2h_beats_seen <= f2h_beats_seen + 1'b1;
            end
        end
    end
end
(* ASYNC_REG = "TRUE" *) reg f2h_fault_sync1, f2h_fault_sync2;
always @(posedge fifo_pcie_clk or posedge rx_retire_pcie_rst2) begin
    if (rx_retire_pcie_rst2) begin f2h_fault_sync1<=0; f2h_fault_sync2<=0; end
    else begin f2h_fault_sync1<=f2h_fault; f2h_fault_sync2<=f2h_fault_sync1; end
end
'''
            fixed = once(fixed, b'\nendmodule', extra+b'\nendmodule')
        (OUT/f'original_{name}.v').write_bytes(original)
        (OUT/f'candidate_{name}.v').write_bytes(fixed)
        # Decode only for human review. All transforms above operate on bytes.
        diff = ''.join(difflib.unified_diff(data.decode('gbk', errors='replace').splitlines(True),
            fixed.decode('gbk', errors='replace').splitlines(True),
            fromfile=str(SOURCE/'rtl'/f'{name}.v'), tofile=f'candidate_{name}.v'))
        (OUT/f'{name}.diff').write_text(diff, encoding='utf-8')
    dma = (SOURCE/'rtl/fpga_v8_pcie_dma_h2f_rfg01.v').read_bytes()
    candidate = once(dma, b'.i_mwr_tx_busy              (~fpga_tx_done              )',
                          b'.i_mwr_tx_busy              (mwr_tx_busy | ~fpga_tx_done)')
    # Wiring diff only: no copied parent hierarchy, not registered in project.pds.
    (OUT/'dma_retirement_wiring.diff').write_text(''.join(difflib.unified_diff(
        dma.decode('gbk', errors='replace').splitlines(True),
        candidate.decode('gbk', errors='replace').splitlines(True),
        fromfile='routed/fpga_v8_pcie_dma_h2f_rfg01.v', tofile='proposed/dma.v')), encoding='utf-8')
    return before

if __name__ == '__main__': prepare()
