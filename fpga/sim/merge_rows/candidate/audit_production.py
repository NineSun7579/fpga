from pathlib import Path
import hashlib
import re

here = Path(__file__).resolve().parent
source = here.parents[3] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/cam2_merge.v'
production = source.read_bytes()
candidate = (here / 'cam2_merge_stream_snapshot.v').read_bytes()

def semantic_text(data):
    data = re.sub(rb'/\*.*?\*/', b'', data, flags=re.S)
    data = re.sub(rb'//[^\r\n]*', b'', data)
    return re.sub(rb'\s+', b'', data)

assert semantic_text(production) == semantic_text(candidate)
lines = [
    'Actual production SHA256: ' + hashlib.sha256(production).hexdigest(),
    'Candidate equivalence: identical RTL after removing comments/whitespace.',
    'All cases compile the production path directly; preserved corner bench unchanged.',
]
cases = ['full62', 'extra62', 'missing62', 'partial62', 'mixed62', 'late62',
         'slow62', 'absent62', 'frame_missing62']
for case in cases:
    log = here / ('production_' + case + '.log')
    text = log.read_text(errors='replace')
    assert 'TEST PASS' in text and 'TEST FAIL' not in text, case
    assert 'source/rtl/cam2_merge.v' in text, case
    selected = [line for line in text.splitlines() if any(marker in line for marker in
                ['FRAME 0 A=', 'FRAME 1 A=', 'SUMMARY frames=', 'MIN_PAIR_SERVICE_CLOCKS=',
                 'SNAPSHOT real=', 'TEST PASS'])]
    lines.append('\n' + log.name)
    lines.extend(selected)
assert all('fullA=0 fullB=0 errors=0' in (here / ('production_' + case + '.log')).read_text()
           for case in cases)
output = '\n'.join(lines) + '\n'
(here / 'production_results.txt').write_text(output)
print(output)
