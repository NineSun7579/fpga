"""Main-assistant-only completion attachment; export/generate/verify V7, no flashing."""
from run_whole import M, WORK


if __name__ == '__main__':
    original = M / 'timing_correction_02/finish_when_ready.py'
    source = original.read_bytes()
    old = b"assert info['Name'].lower()=='python.exe' and 'run_whole.py' in info['CommandLine'],info"
    new = b"assert info['Name'].lower()=='python.exe' and 'run_whole.py' in info['CommandLine'],info\n            assert (WORK/'tc05_regression_acceptance.json').exists(), 'V7 preparation evidence unavailable'"
    assert source.count(old) == 1
    source = source.replace(old, new)
    scope = {'__name__': 'v7_finish', '__file__': __file__}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
