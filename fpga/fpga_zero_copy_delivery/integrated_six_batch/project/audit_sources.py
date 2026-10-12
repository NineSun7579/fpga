"""Byte-level closure evidence; writes only inside the isolated project."""
from pathlib import Path
import hashlib
import json
import re

project = Path(__file__).resolve().parent
root = project.parent.parent
old = root / 'integrated_six/source'
new = project.parent / 'source'
digest = lambda raw: hashlib.sha256(raw).hexdigest()
changes = []
for p in old.rglob('*'):
    if not p.is_file():
        continue
    relative = p.relative_to(old)
    before, after = p.read_bytes(), (new / relative).read_bytes()
    if before != after:
        changes.append(relative.as_posix())
assert sorted(changes) == ['delivery/delivery_regs.v', 'pcie_dma/pcie_fifo.v'], changes
before = (old / 'delivery/delivery_regs.v').read_bytes()
assert before.replace(b"s_rdata<=32'h7; // RGB, thumbnail, six-camera ownership",
                      b"s_rdata<=32'hf; // RGB, thumbnail, six-camera ownership, register snapshot") == (new / 'delivery/delivery_regs.v').read_bytes()
before = (old / 'pcie_dma/pcie_fifo.v').read_bytes()
assert before.replace(b"wire [3:0] r_burst_len = (read_beats_remain >= 32'd16) ? 4'd15 :",
    b"// The delivery AXI-Lite converter retires exactly one 128-bit beat.\n"
    b"wire delivery_register_read = r_cur_addr >= 32'h40020000 &&\n"
    b"                              r_cur_addr <= 32'h40020120;\n"
    b"wire [3:0] r_burst_len = delivery_register_read ? 4'd0 :\n"
    b"                          (read_beats_remain >= 32'd16) ? 4'd15 :") == (new / 'pcie_dma/pcie_fifo.v').read_bytes()
records = json.loads((root / 'six_batch_source_manifest.json').read_text())
assert all(digest(Path(r['baseline']).read_bytes()) == r['before'] for r in records)
receipt = json.loads((root / 'six_batch_pds_manifest.json').read_text())
assert all(digest((root / p).read_bytes()) == h for p,h in receipt['inputs'].items()
           if Path(p).name != 'project.pds')
sim = root / 'sim_six_batch'
raw = (new / 'pcie_dma/pcie_fifo.v').read_bytes()
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
assert normalized == (sim / 'pcie_fifo_modelsim.v').read_bytes(), 'Simulation model drift'
log = (sim / 'six_batch_modelsim.log').read_text()
assert 'SIX_BATCH_ENGINE_PASS' in log and 'Errors: 0' in log
negative = (sim / 'six_batch_baseline_negative.log').read_text()
assert '** Fatal: register burst not single beat' in negative
result = dict(changes=changes, baseline_hashes_preserved=len(records),
              unchanged_from_original_pds_source_inputs=True,
              constraints_and_camera_byte_identical=True,
              capability_bit3_and_register_burst_exact_generator_transform=True,
              simulation_model_matches_current_rtl=True,
              existing_engine_pass_lines=[x for x in log.splitlines() if 'ENGINE_PASS' in x],
              negative_control='Fatal: register burst not single beat',
              sources={str(p.relative_to(new)):digest(p.read_bytes()) for p in new.rglob('*') if p.is_file()},
              test_artifact_hashes={str(p.relative_to(root)):digest(p.read_bytes()) for p in
                  (sim / 'six_batch_tb.sv', sim / 'run.do', sim / 'vendor_endpoint_stubs.v',
                   sim / 'six_batch_modelsim.log', sim / 'six_batch_baseline_negative.log')})
generated = ('compile','synthesize','device_map','place_route','report_timing',
             'generate_bitstream','generate_netlist')
references = re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"',
                        (project / 'project.pds').read_bytes())
external = {}
for reference in references:
    p = (project / reference.decode('ascii')).resolve()
    if p.is_relative_to(project) and p.relative_to(project).parts[0] in generated:
        continue
    if p.is_file():
        external[str(p)] = dict(sha256=digest(p.read_bytes()), bytes=p.stat().st_size)
result['resolved_reference_inputs'] = external
(project / 'timing_source_audit.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('sources','test_artifact_hashes','resolved_reference_inputs')}, indent=2))
