"""Attach the V5 exporter/generator/verifier to its existing build event."""
from run_whole import M


if __name__ == '__main__':
    original = M / 'timing_correction_02/finish_when_ready.py'
    scope = {'__name__': 'v5_finish', '__file__': __file__}
    exec(compile(original.read_bytes(), str(original), 'exec'), scope)
    scope['main']()
