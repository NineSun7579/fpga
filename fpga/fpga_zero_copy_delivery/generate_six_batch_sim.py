"""Generate a focused test of the COMPLETE real pcie_fifo and delivery adapter.

Only vendor PCIe link and FIFO IP are inert endpoint stubs; command inputs and
FIFO capacity are driven by the test. Real read engine, converter, registers,
and both converter cores compile unchanged from the candidate.
"""
from pathlib import Path
import re
import sys
from make_six_batch import ROOT

SIM = ROOT / 'sim_six_batch'
SRC = ROOT / 'integrated_six_batch/source'

def main():
    SIM.mkdir(exist_ok=True)
    baseline = '--baseline' in sys.argv
    raw = ((ROOT / 'integrated_six/source' if baseline else SRC) / 'pcie_dma/pcie_fifo.v').read_bytes()
    # Baseline PDS tolerates forward/implicit declarations that ModelSim rejects.
    # Normalize declaration placement ONLY in a simulation copy; no logic edits.
    normalized = raw
    declarations = []
    for name in (b'fifo_rx_empty', b'axi_b_resp_error', b'fifo_tx_wr_en', b'fifo_tx_wr_data'):
        match = re.search(rb'^(?:wire|reg)\s+[^;\n]*\b' + name + rb'\b[^;\n]*;[^\n]*\n', normalized, re.M)
        assert match, name
        declarations.append(match[0])
        normalized = normalized[:match.start()] + normalized[match.end():]
    normalized = normalized.replace(b'wire [3:0] burst_len =', b'assign burst_len =')
    declarations += [b'wire fifo_rx_almost_full;\n', b'wire [3:0] burst_len;\n']
    pos = normalized.index(b');') + 2
    normalized = normalized[:pos] + b'\n' + b''.join(declarations) + normalized[pos:]
    model = SIM / ('pcie_fifo_baseline_modelsim.v' if baseline else 'pcie_fifo_modelsim.v')
    model.write_bytes(normalized)
    widths = {'fpga_ddr3_addr':32,'fpga_ddr3_length':32,'fpga_ddr3_total_length':32,
              'rxn':2,'rxp':2,'txn':2,'txp':2,'i_msi_req':4,'o_msi_grant':4,
              'fpga_tx_addr':12,'fpga_rx_addr':12,'fpga_tx_data':128,'fpga_rx_data':128,
              'wr_data':128,'rd_data':128,'rd_water_level':10}
    stubs = []
    for mod in ('pango_pcie_top','pcie_rx_fifo','pcie_tx_fifo'):
        # Find named-port instantiation (the module and instance share a name).
        start = raw.index((mod + '(').encode()) if mod == 'pango_pcie_top' else raw.index((mod + ' ' + mod + ' (').encode())
        block = raw[start:raw.index(b');',start)]
        ports = re.findall(rb'\.([a-zA-Z0-9_]+)\s*\(', block)
        decl = []
        for port in ports:
            name = port.decode(); w = widths.get(name,1)
            outputs = ({'txn','txp','ref_led','pclk_led','smlh_link_up','rdlh_link_up',
                        'o_msi_grant','fpga_ddr3_addr','fpga_ddr3_length','fpga_ddr3_total_length',
                        'mwr_tx_busy','fpga_tx_clk_en','fpga_tx_addr','mrd_rx_busy',
                        'fpga_rx_clk_en','fpga_rx_addr','fpga_rx_data','fifo_pcie_clk','fifo_pcie_rst'}
                       if mod == 'pango_pcie_top' else
                       {'wr_full','almost_full','rd_data','rd_empty','rd_water_level','almost_empty'})
            decl.append(('output wire ' if name in outputs else 'input wire ') +
                        (f'[{w-1}:0] ' if w>1 else '') + name)
        params = '#(parameter ADDR_WIDTH=12, MSI_NUM=5)' if mod == 'pango_pcie_top' else ''
        stubs.append(f'module {mod} {params} ({", ".join(decl)}); endmodule\n')
    (SIM / 'vendor_endpoint_stubs.v').write_text(''.join(stubs))
    sources = [model, SRC / 'ov5640/axi_to_axi_lite.v']
    sources += list((SRC / 'delivery').glob('*.v')) + list((SRC / 'display').glob('*.v'))
    # Find actual thumbnail dependency directory rather than assuming it.
    for p in SRC.rglob('*.v'):
        if p.name.startswith('display_thumbnail') and p not in sources: sources.append(p)
    library = 'baseline_work' if baseline else 'work'
    (SIM / ('run_baseline.do' if baseline else 'run.do')).write_text('onerror {quit -code 2}\nvlib '+library+'\n' +
        'vlog -work '+library+' vendor_endpoint_stubs.v ' + ' '.join('{'+str(p).replace('\\','/')+'}' for p in sources) +
        '\nvlog -work '+library+' -sv six_batch_tb.sv\nvsim -c -onfinish exit -voptargs=+acc '+library+'.six_batch_tb\nrun -all\nquit -code 0\n')
    print('Generated simulation inputs', SIM)

if __name__ == '__main__': main()
