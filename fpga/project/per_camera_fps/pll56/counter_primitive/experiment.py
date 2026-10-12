"""Owned, byte-preserving PLL56 primitive counter experiment; no hardware access."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time

OWN = Path(__file__).resolve().parent
HERE = OWN.parent
BASE = HERE / 'build_capture_538dxoxa'
VENDOR = Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

def diagnose():
    import pymupdf
    failed = HERE / 'build_counter_bwnmjek8'
    net = failed / 'work/synthesize/top_syn.vm'
    raw = net.read_bytes()
    modules = [m.group() for m in re.finditer(rb'\nmodule [\s\S]+?\nendmodule', raw)
               if re.match(rb'\nmodule pll56_source_drop_counter(?:_unq\d+)?\s', m.group())]
    cells = [c.group() for m in modules for c in re.finditer(rb'\n    GTP_DFF[^;]+;', m)]
    assert len(modules) == 4 and len(cells) == 128
    assert all(re.search(rb'\.CE\s*\(N11\)', c) for c in cells)
    guide = Path('C:/pango/PDS_2022.2-SP6.4/doc/ADS_Synthesis_User_Guide.pdf')
    pdf = pymupdf.open(guide)
    pages = {str(i+1): pdf[i].get_text() for i in range(95, 100)}
    control = failed / 'work/synthesize/top_controlsets.txt'
    controls = [line.decode('ascii') for line in control.read_bytes().splitlines()
                if b'CLK(' in line and b'u_src_drop.N11)' in line]
    attributes = [line.decode('ascii') for line in (failed/'compile.log').read_bytes().splitlines()
                  if b'Convert attribute name from syn_reduce_controlset_size' in line]
    assert len(controls) == 4 and attributes
    cones = [c.group().decode('ascii') for m in modules
             for c in re.finditer(rb'\n    GTP_[^;]+;', m)
             if re.search(rb'\.Z\s*\(N11\)', c.group())]
    save(OWN/'attribute_diagnosis.json', dict(
        netlist_sha256=sha(net), controlsets_sha256=sha(control), guide_sha256=sha(guide),
        guide_pdf_pages=pages, compiler_attribute_recognition=attributes,
        counter_modules=4, counter_flops=128, counter_controlsets=controls, ce_driver_cones=cones,
        conclusion='Module scope is documented and attribute is recognized as PAP_MIN_CONTROLSET_SIZE. All four 32-register asynchronous-clear control sets retain dynamic CE(N11). This is not an unsupported-attribute or reg/wire placement diagnosis. The guide describes CLK/CE/synchronous SET/RESET and partial/all removal; it does not guarantee CE removal for this asynchronous-clear case. Exact internal optimizer reason remains unreported.'))

def prepare():
    diagnose()
    source = BASE/'inputs/source/ov5640/ov5640/ov5640_cdc.v'
    raw = source.read_bytes()
    nl = b'\r\n' if b'\r\n' in raw else b'\n'
    text = raw.replace(b'\r\n', b'\n')
    edits = {
        b'    reg [31:0] src_count, src_drop, src_seq;':
        b'    reg [31:0] src_count, src_seq;\n    wire [31:0] src_drop;\n    pll56_source_drop_counter u_src_drop (\n        .clk(cam_clk), .rst(cam_rst), .frame(s_vsync && !src_vs_q),\n        .increment(s_valid && full), .value(src_drop)\n    );',
        b'            src_drop <= 0;\n': b'',
        b"                src_drop <= {31'd0, (s_valid && full)};\n": b'',
        b"                if (s_valid && full) src_drop <= src_drop + 1'b1;\n": b'',
    }
    for old, new in edits.items():
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    text += b'''
// PDS 2022.2-SP6.4 vendor simulation/GTP_DFF_C.v documents positive-edge
// D flip-flop, asynchronous active-high clear, INIT=0, and no CE port.
// Increment is the carry-in: no extra held-value mux after the full adder.
// Frame load remains on the original rising edge; snapshot sees old Q.
module pll56_source_drop_counter (
    input clk, input rst, input frame, input increment,
    output wire [31:0] value
);
    wire [31:0] sum = value + {31'd0, increment};
    wire [31:0] next_value = {sum[31:1] & {31{!frame}},
                              frame ? increment : sum[0]};
    genvar bit_index;
    generate for (bit_index=0; bit_index<32; bit_index=bit_index+1) begin: bits
        GTP_DFF_C #(.GRS_EN("TRUE"), .INIT(1'b0)) ff (
            .Q(value[bit_index]), .D(next_value[bit_index]), .CLK(clk), .C(rst)
        );
    end endgenerate
endmodule
'''
    candidate = OWN/'ov5640_cdc.v'
    candidate.write_bytes(text.replace(b'\n', nl))
    for f in (BASE/'inputs/source').rglob('*.v'):
        assert not re.search(rb'\bmodule\s+pll56_source_drop_counter\b', f.read_bytes()), f
    (OWN/'ov5640_cdc_reference.v').write_bytes(raw.replace(
        b'module ov5640_cdc #(', b'module ov5640_cdc_reference #(', 1))
    test = (HERE/'tb_source_drop_equivalence.v').read_bytes()
    # Seed real primitive storage, not its output wire. The reference retains
    # its existing force/release seed. All integration comparisons stay intact.
    old = b"        force candidate.u_src_drop.value=32'hfffffffc;"
    deposits = b'\n'.join(("        $deposit(candidate.u_src_drop.bits[%d].ff.qout, 1'b%d);" %
                           (i, (0xfffffffc >> i) & 1)).encode() for i in range(32))
    assert test.count(old) == 1
    test = test.replace(old, deposits).replace(
        b'release reference.src_drop; release candidate.u_src_drop.value;', b'release reference.src_drop;')
    test = test.replace(b'module tb_source_drop_equivalence;\n',
                        b'module tb_source_drop_equivalence;\n    GTP_GRS GRS_INST (.GRS_N(1\'b1));\n')
    (OWN/'tb_source_drop_equivalence.v').write_bytes(test)
    save(OWN/'preparation.json', dict(status='prepared', original=str(source), candidate=str(candidate),
        original_sha256=sha(source), candidate_sha256=sha(candidate), base_build=str(BASE),
        primitive=str(VENDOR/'GTP_DFF_C.v'), primitive_sha256=sha(VENDOR/'GTP_DFF_C.v'),
        scope='Same-edge diagnostic source-drop only, increment carry-in and frame-load mask, async reset preserved',
        constraints_changed=False, clock_phase_changed=False, hardware_access=False))
    print('PREPARED', OWN, flush=True)

def simulate():
    prep = json.loads((OWN/'preparation.json').read_bytes())
    candidate = Path(prep['candidate'])
    assert sha(candidate) == prep['candidate_sha256']
    assert sha(Path(prep['original'])) == prep['original_sha256']
    model = Path('C:/modeltech64_10.6e/win64')
    work = OWN/'simulation'
    work.mkdir()
    test = OWN/'tb_source_drop_equivalence.v'
    receipt = dict(status='running', candidate_sha256=sha(candidate), original_sha256=prep['original_sha256'],
        testbench_sha256=sha(test), testbench_parent_sha256=sha(HERE/'tb_source_drop_equivalence.v'),
        vendor_models={str(VENDOR/n): sha(VENDOR/n) for n in ('GTP_DFF_C.v', 'GTP_GRS.v')})
    save(work/'receipt.json', receipt)
    try:
        commands = [[model/'vlib.exe', 'work'],
            [model/'vlog.exe', '-sv', VENDOR/'GTP_DFF_C.v', VENDOR/'GTP_GRS.v', candidate,
             OWN/'ov5640_cdc_reference.v', test],
            [model/'vsim.exe', '-c', '-voptargs=+acc', 'work.tb_source_drop_equivalence', '-do',
             'onerror {quit -code 1 -force}; onbreak {quit -code 1 -force}; run -all; quit -code 0 -force']]
        with (work/'simulation.log').open('xb') as log:
            for command in commands:
                print('SIM_STAGE', command[0].name, flush=True)
                result = subprocess.run([str(x) for x in command], cwd=work, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=120)
                log.write(result.stdout); log.flush()
                assert result.returncode == 0, result.stdout.decode('gb18030','replace')[-3000:]
        output = (work/'simulation.log').read_bytes()
        assert b'PASS SOURCE_DROP_EQUIVALENCE' in output
        assert b'cam_edges=     327708 video_edges=     768005' in output
        assert b'** Error' not in output and b'** Fatal' not in output
        receipt.update(status='PASS', log_sha256=sha(work/'simulation.log'), cam_edges=327708,
            destination_edges=768005, full_frame=307200, wrap=True, async_reset=True, snapshot=True)
        print(output.decode('gb18030','replace')[-1200:], flush=True)
    except Exception as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        receipt['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save(work/'receipt.json', receipt)

def generate_runner():
    sim_path = OWN/'simulation/receipt.json'
    sim = json.loads(sim_path.read_bytes())
    prep = json.loads((OWN/'preparation.json').read_bytes())
    assert sim['status'] == 'PASS' and sim['candidate_sha256'] == sha(OWN/'ov5640_cdc.v')
    assert sim['log_sha256'] == sha(sim_path.parent/'simulation.log')
    upstream = HERE/'build_counter_generated_counter_candidate_sb1gs27w.py'
    text = upstream.read_bytes().decode('utf-8').replace('\r\n','\n')
    text = text.replace('import argparse\n', 'import argparse\nimport sys\nsys.dont_write_bytecode = True\nsys.path.insert(0, '+repr(str(HERE))+')\n')
    old_candidate = str(HERE/'counter_candidate_sb1gs27w/ov5640_cdc.v')
    old_sim = str(HERE/'counter_candidate_sb1gs27w/simulation/receipt.json')
    for old, new in ((repr(old_candidate), repr(str(OWN/'ov5640_cdc.v'))),
        ('ba860f27f8f5a41f702fbb3ace2ada605a17420ad61300dad756498b52400c59', sim['candidate_sha256']),
        (repr(old_sim), repr(str(sim_path))),
        ('6109f4bca356043e574f8f4fcfcd4e40f9391c789c11ef723ddd1ef0435b4625', sha(sim_path))):
        assert old in text, old
        text = text.replace(old, new)
    text = text.replace("HERE / 'current_run.json'", "Path("+repr(str(OWN/'current_run.json'))+")")
    text = text.replace("Same-edge source-drop counter control set to D; preserved record capture candidate",
                        'Explicit vendor async-clear FFs; increment carry-in; same-edge snapshots; preserved adapter')
    marker = '    simulations = []\n'
    bindings = '''    own_simulation = Path(%r)
    own_test = Path(%r)
    own_mapping = Path(%r)
    own_primitive = Path(%r)
    assert sha(own_simulation) == %r
    evidence = json.loads(own_simulation.read_bytes())
    assert evidence['status'] == 'PASS'
    assert evidence['candidate_sha256'] == sha(candidate_counter)
    assert evidence['testbench_sha256'] == sha(own_test) == %r
    assert evidence['log_sha256'] == sha(own_simulation.parent / 'simulation.log')
    assert evidence['cam_edges'] == 327708 and evidence['destination_edges'] == 768005
    assert sha(own_primitive) == %r
    receipt.update(primitive_sha256=sha(own_primitive), mapping_gate_sha256=sha(own_mapping),
                   counter_testbench_sha256=sha(own_test), primitive_runner_sha256=sha(Path(__file__)))
''' % (str(sim_path), str(OWN/'tb_source_drop_equivalence.v'), str(OWN/'mapping.py'),
       str(VENDOR/'GTP_DFF_C.v'), sha(sim_path), sha(OWN/'tb_source_drop_equivalence.v'), sha(VENDOR/'GTP_DFF_C.v'))
    assert text.count(marker) == 1
    text = text.replace(marker, bindings + marker)
    marker = "            assert sha(candidate_counter) == receipt['counter_candidate_sha256']\n"
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''            assert sha(own_simulation) == receipt['counter_simulation_sha256']
            assert sha(own_test) == receipt['counter_testbench_sha256']
            assert sha(own_mapping) == receipt['mapping_gate_sha256']
            assert sha(own_primitive) == receipt['primitive_sha256']
            assert sha(Path(__file__)) == receipt['primitive_runner_sha256']
''')
    # Reject failed synthesis mapping immediately, before spending time in map.
    text = text.replace("for stage in ('compile', 'synthesize', 'dev_map'):",
                        "for stage in ('compile', 'synthesize'):")
    start = text.index('        counter_cells = []\n')
    end = text.index("        script = (FROZEN / 'strong_pnr.tcl')", start)
    text = text[:start] + '''        from mapping import verify_counter_mapping
        proof = verify_counter_mapping(netlist, work / 'synthesize/top_controlsets.txt')
        save(run / 'counter_mapping_proof.json', proof)
        assert proof['status'] == 'PASS', 'Explicit counter mapping gate blocked route: ' + repr(proof['errors'])
        receipt['counter_mapping'] = 'PASS 128 async-clear FFs, all four cameras, no CE pins'
        receipt.setdefault('completed_stages', {})['counter_mapping_verification'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save(run / 'receipt.json', receipt)
        save(Path('''+repr(str(OWN/'current_run.json'))+'''), receipt)
        print('COUNTER_MAPPING_PASS', proof['counter_register_cells'], 'register cells; no CE', flush=True)
        execute('dev_map', [PDS, '-project', work / 'flow.pds', '-run', 'dev_map', '-work_dir', work], work)
''' + text[end:]
    # Stronger inventory gate; no timing/pin/PHY/memory checks are removed.
    text = text.replace('        assert set(expected) == set(base_manifest)\n',
        '        assert len(expected) == len(base_manifest) == 694\n        assert set(expected) == set(base_manifest)\n')
    compile(text, str(OWN/'build.py'), 'exec')
    (OWN/'build.py').write_text(text, encoding='utf-8')
    save(OWN/'runner_proof.json', dict(upstream_sha256=sha(upstream), runner_sha256=sha(OWN/'build.py'),
        simulation_receipt_sha256=sha(sim_path), inventory=694, one_file_diff=True,
        strict_gates='Unchanged PLL56 clocks/exceptions, 112 pins, dedicated PHY, 32 motion banks, 126 STA rows, bitgen gated',
        shared_lock=str(HERE.parent/'fpga/build.lock'), placement_seed=1, random_seed_search=False))
    print('RUNNER_READY', OWN/'build.py', flush=True)

if __name__ == '__main__':
    {'prepare': prepare, 'simulate': simulate, 'generate': generate_runner}[sys.argv[1]]()
