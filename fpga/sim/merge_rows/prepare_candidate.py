from pathlib import Path
import hashlib

source = Path(__file__).resolve().parents[3] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/cam2_merge.v'
data = source.read_bytes()
old = b'.wr_en(a_de_r | a_push_eol)'
new = b'.wr_en(a_push | a_push_eol)'
assert data.count(old) + data.count(new) == 1
Path(__file__).with_name('cam2_merge_cap_candidate.v').write_bytes(data.replace(old, new))
print('Production source SHA256:', hashlib.sha256(data).hexdigest())
print('Simulation-only candidate: A pixel gate a_de_r -> a_push')
