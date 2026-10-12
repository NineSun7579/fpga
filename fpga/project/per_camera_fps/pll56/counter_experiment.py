"""Private counter experiment: byte-preserving preparation and report-bound diagnosis."""
from pathlib import Path
import hashlib
import json
import re
import tempfile

HERE = Path(__file__).resolve().parent
BASE = HERE / 'build_capture_538dxoxa'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, data):
    p.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

def prepare():
    out = Path(tempfile.mkdtemp(prefix='counter_candidate_', dir=HERE))
    source = BASE / 'inputs/source/ov5640/ov5640/ov5640_cdc.v'
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
// ADS Synthesis User Guide section 5.17, PDF pages 96-100:
// A 64-register threshold moves this 32-bit synchronous control set to D.
// Keep this attribute confined to the diagnostic drop counter.
module pll56_source_drop_counter (
    input clk, input rst, input frame, input increment,
    output reg [31:0] value
) /* synthesis syn_reduce_controlset_size = 64 syn_useioff = 0 */;
    always @(posedge clk or posedge rst) begin
        if (rst) value <= 0;
        else if (frame) value <= {31'd0, increment};
        else if (increment) value <= value + 1'b1;
    end
endmodule
'''
    candidate = out / 'ov5640_cdc.v'
    candidate.write_bytes(text.replace(b'\n', nl))
    # No other declaration in the private input inventory has this module name.
    for f in (BASE / 'inputs/source').rglob('*.v'):
        assert not re.search(rb'\bmodule\s+pll56_source_drop_counter\b', f.read_bytes()), f
    ref = out / 'ov5640_cdc_reference.v'
    ref.write_bytes(raw.replace(b'module ov5640_cdc #(', b'module ov5640_cdc_reference #(', 1))
    rows = {}
    for name in ['build_aai6kbmf', 'build_mfwcoqj3', BASE.name]:
        run = HERE / name
        d = json.loads((run / 'final_sta_analysis.json').read_bytes())
        assert sha(run / 'final_sta/report_timing/top.rtr') == d['report_sha256']
        assert len(d['summary_rows']) == 126
        rows[name] = dict(report_sha256=d['report_sha256'], failing_rows=d['failing_rows'],
            hold=[r for r in d['summary_rows'] if r['section'][0]=='Hold'],
            violations=[{k:v for k,v in x.items() if k!='detail'} for x in d['violated_paths']])
    save(out / 'sta_diagnosis.json', rows)
    # Retain exact netlist cone evidence for the record rewrite, including LUT INITs.
    cones = {}
    for name in ['build_aai6kbmf', BASE.name]:
        net = HERE / name / 'work/synthesize/top_syn.vm'
        rawnet = net.read_bytes()
        pos = rawnet.find(b'GTP_DFF_CE /* \\motion_record[136]')
        assert pos >= 0
        mod = rawnet[rawnet.rfind(b'\nmodule ', 0, pos):rawnet.find(b'\nendmodule', pos)]
        wanted = [b'N368', b'N77'] if name=='build_aai6kbmf' else [b'record_capture', b'_N147638']
        blocks = []
        for cell in re.finditer(rb'\n    GTP_[^;]+;', mod):
            if any(re.search(rb'\.(?:Z|Z5)\s*\('+re.escape(n)+rb'\)', cell.group()) for n in wanted):
                blocks.append(cell.group().decode('ascii','replace'))
        cones[name] = dict(netlist_sha256=sha(net), evidence=blocks)
    save(out / 'record_mapping_evidence.json', cones)
    receipt = dict(status='prepared', original=str(source), candidate=str(candidate),
        original_sha256=sha(source), candidate_sha256=sha(candidate),
        base_build=str(BASE), scope='Same-edge diagnostic source-drop counter only',
        attribute_reference='ADS Synthesis User Guide section 5.17, PDF pages 96-100',
        vendor_launched=False, constraints_changed=False, clock_phase_changed=False,
        fifo_and_snapshot_logic_preserved=True)
    save(out / 'preparation.json', receipt)
    print(out, flush=True)
    return out

if __name__ == '__main__':
    prepare()
