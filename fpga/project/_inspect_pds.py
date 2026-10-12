import re, sys

for f in ['project_build/project.pds', 'project/project.pds']:
    b = open(f, 'rb').read().decode('latin1')
    print('=' * 20, f, 'len', len(b))
    for pat in [r'[^\s"\']*pcie[^\s"\']*', r'bar[0-9]_', r'BAR[0-9]']:
        hits = sorted(set(re.findall(pat, b, re.I)))
        if hits:
            print('  PAT', pat, '->', hits[:20])
