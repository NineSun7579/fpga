from pathlib import Path
import hashlib, json, sys

root = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
prod = root / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
initial = json.loads((here / 'initial_hashes.json').read_text())
tx = prod / 'sfp_video_tx.v'
fifo = prod / 'video_async_fifo.v'
assert digest(fifo) == initial[str(fifo.relative_to(root))], 'FIFO changed'
assert digest(here/'candidate/sfp_video_tx.v') == initial[str((here/'candidate/sfp_video_tx.v').relative_to(root))], 'Candidate changed'
if sys.argv[1] == 'apply':
    assert digest(tx) == initial[str(tx.relative_to(root))], 'Production changed since archive'
    for log, marker in [('candidate.log', b'TB_PASS recovery'), ('full_candidate.log', b'TB_PASS full')]:
        assert marker in (here/log).read_bytes(), 'Candidate test did not pass'
    tx.write_bytes((here/'candidate/sfp_video_tx.v').read_bytes())
assert tx.read_bytes() == (here/'candidate/sfp_video_tx.v').read_bytes()
assert digest(here/'archived_original/sfp_video_tx.v') == initial[str(tx.relative_to(root))]
result = {str(p.relative_to(root)): digest(p) for p in [tx, fifo, here/'candidate/sfp_video_tx.v', here/'archived_original/sfp_video_tx.v']}
(here / ('production_hashes_'+sys.argv[1]+'.json')).write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
