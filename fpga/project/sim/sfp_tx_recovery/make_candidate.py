"""Byte-preserving, sim-only candidate from the actual50K sources."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TX = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
RX = ROOT / 'project/source/sfp'
out = HERE / 'candidate'
out.mkdir(exist_ok=True)
src = (TX / 'sfp_video_tx.v').read_bytes()
# Production has CRCRLF; preserve its exact newline and comment bytes.
nl = b'\r\r\n' if b'\r\r\n' in src else b'\r\n' if b'\r\n' in src else b'\n'
def replace(old, new):
    global src
    old = old.replace(b'\n', nl)
    new = new.replace(b'\n', nl)
    assert src.count(old) == 1, repr(old)
    src = src.replace(old, new)
replace(b'    reg [15:0] pix0;', b'    reg [15:0] pix0;\n    reg wait_frame; // Drain continuously; resume payload only at a consumed VS blank.')
replace(b"            pix0       <= `UD 16'b0;", b"            pix0       <= `UD 16'b0;\n            wait_frame <= `UD 1'b1;")
replace(b"                txd <= `UD idle_word;\n                txk <= `UD 4'b1001;\n                pix_pend <= `UD 1'b0;", b"                txd <= `UD (fifo_pop ? ctrl_word : idle_word);\n                txk <= `UD 4'b1001;\n                pix_pend <= `UD 1'b0;\n                wait_frame <= `UD 1'b1;")
replace(b'                if (!pix_pend) begin', b"                if (wait_frame) begin\n                    txd <= `UD ctrl_word;\n                    txk <= `UD ctrl_k;\n                    pix_pend <= `UD 1'b0;\n                    if (head_vs && !head_de)\n                        wait_frame <= `UD 1'b0;\n                end\n                else if (!pix_pend) begin")
(out / 'sfp_video_tx.v').write_bytes(src)
(out / 'video_async_fifo.v').write_bytes((TX / 'video_async_fifo.v').read_bytes())
before = (TX / 'sfp_video_tx.v').read_bytes().replace(nl, b'\n').decode('latin1').splitlines(True)
after = src.replace(nl, b'\n').decode('latin1').splitlines(True)
# Zero context keeps the review diff ASCII; candidate retains original bytes.
diff = ''.join(difflib.unified_diff(before, after, 'actual50K/sfp_video_tx.v', 'candidate/sfp_video_tx.v', n=0))
(HERE / 'candidate.diff').write_bytes(diff.encode('latin1'))
files = [TX / 'sfp_video_tx.v', TX / 'video_async_fifo.v', RX / 'sfp_video_rx.v']
manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(HERE / 'source_hashes.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Candidate generated; production files only read.')
