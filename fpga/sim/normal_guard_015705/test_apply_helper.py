"""Exercise apply gates against temporary fake evidence, never real production."""
import contextlib
import io
import json
import shutil
import tempfile
from pathlib import Path
import prepare_apply as helper

original_here = helper.HERE
def save(path, value):
    path.write_text(json.dumps(value), encoding='ascii')

with tempfile.TemporaryDirectory(prefix='normal_gate_test_') as tmp:
    root = Path(tmp)
    here = root / 'candidate'
    shutil.copytree(original_here, here, ignore=shutil.ignore_patterns('normal_work'))
    rtl = root / 'production_fixture'
    shutil.copytree(helper.RTL, rtl)
    evidence = root / 'log/six_guard_board_20261003'
    evidence.mkdir(parents=True)
    bit = root / 'fake.sbit'
    bit.write_bytes(b'fixture-only')
    digest = helper.sha(bit.read_bytes())
    result = {'pass': True, 'failures': [], 'actual_last_burn_sha256': digest}
    handoff = {'stage': 'finished', 'status': 'verified', 'result': result, 'bit_sha256': digest}
    save(evidence / 'workflow_result.json', result)
    save(root / 'log/six_guard_015705_handoff.json', handoff)
    save(evidence / 'colorbar_geometry.json', {'geometry_pass': True})
    (evidence / 'rk3568_guard_screen.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')
    save(evidence / 'actual_last_burn.json', {'sha256': digest, 'bitstream': str(bit)})
    helper.HERE, helper.ROOT, helper.RTL = here, root, rtl
    original = {n: (rtl / n).read_bytes() for n in helper.NAMES}
    checks = []
    def rejected(label):
        try:
            helper.apply_normal()
        except (RuntimeError, FileNotFoundError):
            assert all((rtl / n).read_bytes() == b for n, b in original.items())
            checks.append(label)
        else:
            raise AssertionError('unsafe acceptance: ' + label)
    result['pass'] = False
    save(evidence / 'workflow_result.json', result)
    rejected('failed guard refused before any writes')
    result['pass'] = True
    save(evidence / 'workflow_result.json', result)
    handoff['stage'] = 'restoring_viewer'
    save(root / 'log/six_guard_015705_handoff.json', handoff)
    rejected('pending owner refused before any writes')
    handoff['stage'] = 'finished'
    save(root / 'log/six_guard_015705_handoff.json', handoff)
    save(evidence / 'colorbar_geometry.json', {'geometry_pass': False})
    rejected('failed geometry refused before any writes')
    save(evidence / 'colorbar_geometry.json', {'geometry_pass': True})
    candidate = here / 'normal/hdmi_ddr_ov5640_top.v'
    exact = candidate.read_bytes()
    candidate.write_bytes(exact + b'\n')
    rejected('candidate SHA mismatch refused before any writes')
    candidate.write_bytes(exact)
    with contextlib.redirect_stdout(io.StringIO()):
        helper.apply_normal()
    assert (rtl / candidate.name).read_bytes() == exact
    assert all((rtl / n).read_bytes() == original[n] for n in helper.NAMES if n != candidate.name)
    checks.append('all gates satisfied applies only one exact top file in fixture')
    save(original_here / 'helper_test_result.json', {'pass': True, 'scope': 'temporary fixtures only', 'checks': checks})
    print('HELPER PASS: ' + '; '.join(checks))
