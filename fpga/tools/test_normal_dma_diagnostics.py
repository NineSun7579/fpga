"""Offline regression for single-owner DMA diagnostics and interval gates."""
import ast
import contextlib
import io
import json
from pathlib import Path
import runpy
import shlex
import struct
import sys
import tempfile
import types
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent

def fake_accept(destination, diagnostics):
    clock = [1000.0]
    mapping = bytearray(4194304)
    maps, opens, reads = [], [], []
    words = [63, 307200, 307200, 307200, 307200, 0x00020001, 0x00040003]
    class Mapping:
        def __getitem__(self, key):
            return mapping[key]
        def close(self):
            pass
    def ioctl(fd, code, op, mutate):
        if code & 255 == 2:
            maps.append(op.cmd)
        else:
            reads.append((op.ddr, op.ln))
            if 0x20000120 <= op.ddr <= 0x20000180:
                assert op.ln == 16 and op.ddr % 16 == 0
                value = words[(op.ddr - 0x20000120) // 16]
            else:
                value = int((clock[0] - 1000) * 30) + 1
            mapping[:op.ln] = (struct.pack('<I', value) * ((op.ln + 3) // 4))[:op.ln]
        return 0
    fake_fcntl = types.SimpleNamespace(ioctl=ioctl)
    def open_device(*args):
        opens.append(args)
        return 42
    argv = ['accept_six_streams.py', '--seconds', '30', '--output', str(destination)]
    if diagnostics:
        argv.append('--diagnostics')
    with patch.dict(sys.modules, fcntl=fake_fcntl), patch('sys.argv', argv), \
         patch('os.O_SYNC', 0, create=True), patch('mmap.MAP_SHARED', 1, create=True), \
         patch('mmap.PROT_READ', 1, create=True), patch('mmap.PROT_WRITE', 2, create=True), \
         patch('os.open', open_device), patch('os.close'), \
         patch('mmap.mmap', return_value=Mapping()), \
         patch('time.monotonic', side_effect=lambda: clock[0]), \
         patch('time.sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0] + duration)), \
         contextlib.redirect_stdout(io.StringIO()):
        try:
            runpy.run_path(str(TOOLS / 'accept_six_streams.py'))
        except SystemExit as error:
            assert error.code == 0
    assert len(opens) == 1 and maps == [0, 1], (opens, maps)
    assert json.loads((destination / 'report.json').read_bytes())['pass']
    if diagnostics:
        rows = [json.loads(line) for line in (destination / 'diagnostics_during.jsonl').read_bytes().splitlines()]
        assert len(rows) == 61 and rows[-1]['time'] - rows[0]['time'] == 30
        assert sum(address >= 0x20000120 for address, size in reads) == 61 * 7
        helper = ast.parse((TOOLS / 'read_sfp_diagnostics.py').read_bytes())
        expression = next(node.args[0] for node in ast.walk(helper)
                          if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                          and node.func.attr == 'dumps')
        scope = dict(zip(('status', 'fault5', 'fault6', 'pixels5', 'pixels6', 'states', 'rejects'), words))
        scope.update(values=words, sample=0, time=types.SimpleNamespace(monotonic=lambda: 1000.0))
        expected = eval(compile(ast.Expression(expression), '<helper schema>', 'eval'), scope)
        assert rows[0] == expected
        return rows
    assert not (destination / 'diagnostics_during.jsonl').exists()

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    enabled = root / 'enabled'
    rows = fake_accept(enabled, True)
    fake_accept(root / 'legacy', False)
    before = [dict(rows[0], time=990 + index * 0.5) for index in range(10)]
    after = [dict(rows[-1], time=1031 + index * 0.5) for index in range(10)]
    (enabled / 'board.jsonl').write_text('\n'.join(json.dumps(row) for row in before))
    source = (TOOLS / 'finish_normal_023911.py').read_bytes().decode('ascii')
    gate = source[source.index('        rows = [json.loads(line)'):source.index('        report = json.loads')]
    gate = '\n'.join(line[8:] for line in gate.splitlines())
    def check(samples):
        (enabled / 'diagnostics_during.jsonl').write_text('\n'.join(json.dumps(row) for row in samples))
        failures, saved = [], []
        scope = dict(json=json, EVIDENCE=enabled, final='\n'.join(json.dumps(row) for row in after).encode(),
                     failures=failures, build=types.SimpleNamespace(save=lambda path, value: saved.append(value)))
        exec(gate, scope)
        return failures, saved
    failures, saved = check(rows)
    assert not failures and len(saved[0]['samples']) == 81
    assert saved[0]['samples'] == sorted(saved[0]['samples'], key=lambda row: row['time'])
    for field, value, expected in [('input_pixels', 1, 'input count'), ('short_count', 4, 'short count'),
                                   ('overflow', True, 'overflow'), ('fault', '0x4004b000', 'fresh fault')]:
        changed = json.loads(json.dumps(rows))
        changed[20]['cameras'][0][field] = value
        failures, _ = check(changed)
        assert any(expected in item for item in failures), (field, failures)
    assert check(rows[:49])[0]
    assert check([dict(row, time=1000 + index * 0.1) for index, row in enumerate(rows)])[0]

wrapper = ast.parse((TOOLS / 'verify_six_normal_image.py').read_bytes())
operation = next(node.value for node in ast.walk(wrapper) if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'operations' for target in node.targets))
command = eval(compile(ast.Expression(operation), '<remote command>', 'eval'),
               dict(shlex=shlex, remote='/tmp/offline', delay_code='sequential delay',
                    args=types.SimpleNamespace(seconds=30)))
assert '--diagnostics --seconds 30' in command
assert 'normalDiagPid' not in command and 'while true' not in command and ' & ' not in command
assert command.index('read_sfp_diagnostics.py') < command.index('accept_six_streams.py')
for name in ('accept_six_streams.py', 'verify_six_normal_image.py', 'finish_normal_023911.py'):
    raw = (TOOLS / name).read_bytes()
    raw.decode('ascii')
    ast.parse(raw)
print('PASS: single DMA owner, 61 aligned samples over 30s, exact helper schema, legacy default,')
print('combined 81-sample gates reject transient input/short/overflow/fault and missing duration; sequential command.')
