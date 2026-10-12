"""Isolated byte-preserving snapshot candidates. Never invokes PDS or hardware."""
from pathlib import Path
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parent

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def replace(raw, old, new):
    old, new = old.encode('ascii'), new.encode('ascii')
    assert raw.count(old) == 1, (old, raw.count(old))
    return raw.replace(old, new)

def main():
    rtl = ROOT / 'integrated_six'
    viewer = ROOT / 'six_camera_viewer_src'
    targets = [ROOT / 'integrated_six_batch', ROOT / 'six_camera_batch_viewer_src']
    assert not any(p.exists() for p in targets), 'Refuse to overwrite existing candidates'
    inputs = {p: p.read_bytes() for p in (rtl / 'source').rglob('*') if p.is_file()}
    inputs[rtl / 'project/project.pds'] = (rtl / 'project/project.pds').read_bytes()
    # Copy source inputs, excluding generated moc/build/report artifacts.
    inputs.update({p: p.read_bytes() for p in viewer.rglob('*') if p.is_file()
                   and p.suffix in {'.cpp', '.h', '.pro', '.md', '.py'}
                   and not p.name.startswith('moc_')})
    records = []
    for p, raw in inputs.items():
        base = rtl if p.is_relative_to(rtl) else viewer
        out = targets[0] if base == rtl else targets[1]
        rel = p.relative_to(base).as_posix()
        new = raw
        if rel == 'source/pcie_dma/pcie_fifo.v':
            new = replace(raw, "wire [3:0] r_burst_len = (read_beats_remain >= 32'd16) ? 4'd15 :",
                          "// The delivery AXI-Lite converter retires exactly one 128-bit beat.\n"
                          "wire delivery_register_read = r_cur_addr >= 32'h40020000 &&\n"
                          "                              r_cur_addr <= 32'h40020120;\n"
                          "wire [3:0] r_burst_len = delivery_register_read ? 4'd0 :\n"
                          "                          (read_beats_remain >= 32'd16) ? 4'd15 :")
        elif rel == 'source/delivery/delivery_regs.v':
            new = replace(raw, "s_rdata<=32'h7; // RGB, thumbnail, six-camera ownership",
                          "s_rdata<=32'hf; // RGB, thumbnail, six-camera ownership, register snapshot")
        elif rel == 'project/project.pds':
            def rebase(m):
                path = (base / 'project' / m[2].decode('ascii')).resolve()
                ref = ('../source/' + path.relative_to(base / 'source').as_posix()
                       if path.is_relative_to(base / 'source') else
                       os.path.relpath(path, out / 'project').replace('\\', '/'))
                return m[1] + ref.encode('ascii') + m[3]
            new = re.sub(rb'(\((?:_file|_ip|_ip_source_item) ")([^"]+)(")', rebase, raw)
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(new)
        records.append(dict(baseline=str(p), candidate=str(target), before=sha(raw), after=sha(new)))
    assert all(p.read_bytes() == raw for p, raw in inputs.items()), 'Baseline modified'
    for ref in re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"',
                          (targets[0] / 'project/project.pds').read_bytes()):
        assert (targets[0] / 'project' / ref.decode('ascii')).resolve().exists(), ref
    (ROOT / 'six_batch_source_manifest.json').write_text(json.dumps(records, indent=2))
    print('Generated isolated RTL/viewer inputs; baseline hashes verified:', len(records))

if __name__ == '__main__':
    main()
