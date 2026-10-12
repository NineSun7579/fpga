"""Read-only production audit; preserve exact original in sim archive."""
from pathlib import Path
import hashlib, json, re, difflib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TX = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
def sha(b): return hashlib.sha256(b).hexdigest()
def norm(b): return b.replace(b'\r\r\n', b'\n').replace(b'\r\n', b'\n')
def tokens(b):
    b = re.sub(rb'/\*.*?\*/|//[^\n]*', b'', norm(b), flags=re.S)
    return re.findall(rb'[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]', b)

candidate = (HERE/'candidate/sfp_video_tx.v').read_bytes()
prod = (TX/'sfp_video_tx.v').read_bytes()
assert tokens(prod) == tokens(candidate), 'Production semantic tokens differ'
diff = b''.join(difflib.diff_bytes(difflib.unified_diff,
    norm(candidate).splitlines(True), norm(prod).splitlines(True),
    fromfile=b'candidate', tofile=b'production', n=0))
(HERE/'production_vs_candidate.diff').write_bytes(diff)

# Reverse only the known candidate changes. Verify against the original hash
# captured before the parent changed production; never assume reconstruction.
original = candidate
nl = b'\r\r\n' if b'\r\r\n' in candidate else b'\r\n'
def reverse(new, old):
    global original
    new = new.replace(b'\n', nl); old = old.replace(b'\n', nl)
    assert original.count(new) == 1
    original = original.replace(new, old)
reverse(b'    reg wait_frame; // Drain continuously; resume payload only at a consumed VS blank.\n', b'')
reverse(b"            pix0       <= `UD 16'b0;\n            wait_frame <= `UD 1'b1;", b"            pix0       <= `UD 16'b0;")
reverse(b"                txd <= `UD (fifo_pop ? ctrl_word : idle_word);", b"                txd <= `UD idle_word;")
reverse(b"                wait_frame <= `UD 1'b1;\n", b'')
reverse(b"                if (wait_frame) begin\n                    txd <= `UD ctrl_word;\n                    txk <= `UD ctrl_k;\n                    pix_pend <= `UD 1'b0;\n                    if (head_vs && !head_de)\n                        wait_frame <= `UD 1'b0;\n                end\n                else if (!pix_pend) begin", b'                if (!pix_pend) begin')
baseline = json.loads((HERE/'source_hashes.json').read_text())
assert sha(original) == baseline[str((TX/'sfp_video_tx.v').relative_to(ROOT))]
archive = HERE/'archived_original'; archive.mkdir(exist_ok=True)
for name, data in [('sfp_video_tx.v',original), ('video_async_fifo.v',(HERE/'candidate/video_async_fifo.v').read_bytes())]:
    p = archive/name
    if p.exists(): assert p.read_bytes() == data
    else: p.write_bytes(data)
assert (TX/'video_async_fifo.v').read_bytes() == (archive/'video_async_fifo.v').read_bytes()
paths = [TX/'sfp_video_tx.v', TX/'video_async_fifo.v', ROOT/'project/source/sfp/sfp_video_rx.v', ROOT/'project/source/sfp/sfp_rx_cam_if.v', ROOT/'project/source/sfp/video_async_fifo.v', archive/'sfp_video_tx.v']
hashes = {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
out = HERE/'production_verification_hashes.json'
if out.exists(): assert json.loads(out.read_text()) == hashes, 'Sources changed during verification'
else: out.write_text(json.dumps(hashes,indent=2)+'\n')
print('PRODUCTION_SEMANTIC_MATCH; byte difference: comment removes "only"')
print('ARCHIVED_ORIGINAL_HASH_VERIFIED; SOURCE_HASHES_STABLE')
print(json.dumps(hashes,indent=2))
