"""Prepare only an isolated register table; never write production RTL."""
from pathlib import Path
import hashlib
import re

here = Path(__file__).resolve().parent
src = here.parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/reg_config.v'
b = src.read_bytes()
original = b
changes = [(b'381100', b'381110'), (b'3801a0', b'380180'), (b'38059f', b'3805bf')]
for old, new in changes:
    token = b"24'h" + old
    assert b.count(token) == 1, token
    b = b.replace(token, b"24'h" + new)
# Existing comments describe the old window. Preserve encoding and replace only
# affected ASCII comments in the isolated copy.
b = b.replace(b'ISP window X offset = 0 (VGA config)', b'ISP window X offset = 16 (horizontal margin candidate)')
b = b.replace(b'X start = 672   (crop 1280 wide, centered)', b'X start = 640 (1344-wide window; 32 extra sensor columns each side)')
b = b.replace(b'X end = 1951    (672+1280-1)', b'X end = 1983 (640+1344-1)')
b = b.replace(b'crop 1280x960 -> sub-sample 2:1 -> 640x480', b'crop 1344x960 -> horizontal ISP margin 16 -> output 640x480')
out = here / 'candidate/reg_config.v'
out.parent.mkdir(exist_ok=True)
out.write_bytes(b)
def table(data):
    return [(int(i), int(v,16)) for i,v in re.findall(rb'(\d+)\s*:reg_data\s*<=24\x27h([0-9a-fA-F]{6})',data)]
a, c = dict(table(original)), dict(table(b))
diff = [(i, f'{a[i]:06x}', f'{c[i]:06x}') for i in a if a[i]!=c[i]]
assert diff == [(147,'381100','381110'),(316,'3801a0','380180'),(320,'38059f','3805bf')], diff
print('Register changes:', diff)
print('Source SHA256:', hashlib.sha256(original).hexdigest())
print('Candidate SHA256:', hashlib.sha256(b).hexdigest())
print('Output, HTS, VTS, PLL, RGB565, scaler, vertical window unchanged.')
