"""Read-only source preservation audit; writes only new candidate reports."""
from pathlib import Path
import difflib
import hashlib
import json
from make_six_batch import ROOT

def digest(raw): return hashlib.sha256(raw).hexdigest()

def section(raw, start, end):
    pos = raw.index(start)
    return raw[pos:raw.index(end, pos)]

def main():
    records = json.loads((ROOT / 'six_batch_source_manifest.json').read_text())
    changes, diffs = [], []
    allowed = {'source/pcie_dma/pcie_fifo.v','source/delivery/delivery_regs.v','project/project.pds',
               'main.cpp','thumbnail_delivery.h','thumbnail_delivery_selftest.cpp'}
    for record in records:
        p, q = Path(record['baseline']), Path(record['candidate'])
        before, after = p.read_bytes(), q.read_bytes()
        assert digest(before) == record['before'], f'PROTECTED BASELINE CHANGED: {p}'
        base = ROOT / ('integrated_six' if p.is_relative_to(ROOT / 'integrated_six') else 'six_camera_viewer_src')
        rel = p.relative_to(base).as_posix()
        if before != after:
            assert rel in allowed, rel
            changes.append(str(q.relative_to(ROOT)))
            # Latin-1 is reversible for mixed GBK/UTF-8 bytes; hashes are authoritative.
            diffs += list(difflib.unified_diff(before.decode('latin1').splitlines(True),
                after.decode('latin1').splitlines(True), fromfile=str(p.relative_to(ROOT)), tofile=str(q.relative_to(ROOT))))
        record['current_candidate_sha256'] = digest(after)
    old = (ROOT / 'six_camera_viewer_src/main.cpp').read_bytes()
    new = (ROOT / 'six_camera_batch_viewer_src/main.cpp').read_bytes()
    transport = section(new,b'    struct ThumbnailTransport {',b'    bool cameraTagLocked(')
    prior_transport = section(old,b'    struct ThumbnailTransport {',b'    bool cameraTagLocked(')
    insertion = section(transport,b'        bool readSnapshot(',b'        bool write(')
    assert transport.replace(insertion,b'') == prior_transport
    assert new.replace(insertion,b'') == old, 'Only snapshot transport insertion allowed in main.cpp'
    assert (ROOT/'six_camera_batch_viewer_src/six_dma_layout.h').read_bytes() == (ROOT/'six_camera_viewer_src/six_dma_layout.h').read_bytes()
    assert b'SIGTERM' in old and old.count(b'SIGTERM') == new.count(b'SIGTERM')
    stages = [b'check(source == SourceBanks', b'identity(camera, bank, epoch, source, tag)',
              b'check(io.readTag', b'check(io.readPixels', b'check(get(Jobs)', b'restore();']
    old_reader=(ROOT/'six_camera_viewer_src/thumbnail_delivery.h').read_bytes()
    new_reader=(ROOT/'six_camera_batch_viewer_src/thumbnail_delivery.h').read_bytes()
    assert all(old_reader.count(s)==new_reader.count(s) for s in stages)
    result = dict(baseline_hashes_preserved=len(records), changes=changes,
                  main_only_snapshot_transport_inserted=True, sigterm_preserved=True,
                  reserved_layout_identical=True, validation_stage_counts_preserved=True,
                  pds_run=False, board_access=False, files=records)
    (ROOT/'six_batch_preservation_report.json').write_text(json.dumps(result,indent=2))
    (ROOT/'six_batch_changes.diff').write_text(''.join(diffs),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))

if __name__=='__main__': main()
