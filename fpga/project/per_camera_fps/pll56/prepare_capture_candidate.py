"""Create an isolated byte-preserving capture-enable experiment; no vendor launch."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
BASE = HERE / 'build_aai6kbmf/inputs/source/motion/motion_stream_adapter.v'
OUT = HERE / 'capture_candidate'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    raw = BASE.read_bytes()
    newline = b'\r\n' if b'\r\n' in raw else b'\n'
    text = raw.replace(b'\r\n', b'\n')
    old = b'''            // Detector valid is a pulse; snapshot every field together.
            if (strobe) motion_record <= {
                bitmap_word, 16'b0, maxy_word, miny_word, maxx_word, minx_word,
                8'b0, sample_word, block_word,
                29'b0, publish_error, bbox_valid, comparison_valid, publish_sequence
            };
'''
    assert text.count(old) == 1
    assert text.count(b'            motion_record <= 0;\n') == 1
    text = text.replace(old, b'').replace(b'            motion_record <= 0;\n', b'')
    addition = b'''
    // Exact Boolean expansion of strobe && !overflow_reset && !overflow.
    // Keep record capture independent of the event-control priority mux.
    // No flag is retimed; capture and overflow suppression use this same edge.
    wire record_capture = strobe && !overflow_reset &&
        ((queued != 16) || pop || (!rise && (!acquired || !pixel_valid)));
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) motion_record <= 0;
        else if (record_capture) motion_record <= {
            bitmap_word, 16'b0, maxy_word, miny_word, maxx_word, minx_word,
            8'b0, sample_word, block_word,
            29'b0, publish_error, bbox_valid, comparison_valid, publish_sequence
        };
    end
'''
    assert text.count(b'endmodule') == 1
    candidate = text.replace(b'endmodule', addition + b'endmodule').replace(b'\n', newline)
    OUT.mkdir(exist_ok=True)
    path = OUT / 'motion_stream_adapter.v'
    path.write_bytes(candidate)
    for bits in range(128):
        strobe, reset, full, pop, rise, acquired, valid = [bool(bits & (1 << i)) for i in range(7)]
        push = (acquired or rise) and (rise or valid)
        original = strobe and not reset and not (push and full and not pop)
        proposed = strobe and not reset and (not full or pop or (not rise and (not acquired or not valid)))
        assert original == proposed
    receipt = dict(status='prepared_boolean_proof_pass', original=str(BASE), candidate=str(path),
                   original_sha256=sha(raw), candidate_sha256=sha(candidate), boolean_cases=128,
                   changed_file='motion/motion_stream_adapter.v', pipeline_change=False,
                   constraints_change=False, vendor_launched=False,
                   scope='Same-edge record capture only; detector and event-control bytes retained')
    (OUT / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
