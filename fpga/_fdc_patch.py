import shutil

targets = {
    'source/constraints/clock.fdc': [8, 49],
    'source/constraints/cdc.fdc':   [27],
}

for path, linenos in targets.items():
    shutil.copyfile(path, path + '.bak_before_nonpu')
    raw = open(path, 'rb').read()
    lines = raw.split(b'\n')
    for n in linenos:
        i = n - 1
        s = lines[i]
        stripped = s.lstrip()
        indent = s[:len(s) - len(stripped)]
        assert not stripped.startswith(b'#'), 'line %d already commented: %r' % (n, s[:60])
        lines[i] = indent + b'# [NO_NPU 2026-09-12] ' + stripped
    open(path, 'wb').write(b'\n'.join(lines))
    print('patched', path, 'lines', linenos)

for path, linenos in targets.items():
    lines = open(path, 'rb').read().split(b'\n')
    for n in linenos:
        print('  %s:%d -> %s' % (path, n, lines[n-1].decode('latin1', 'replace')[:130]))
