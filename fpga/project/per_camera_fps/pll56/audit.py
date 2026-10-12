"""Supplement inherited timing validation with exact zero-failure totals."""
import re
from prepare import sha

def strict_timing(report):
    section = None
    rows = []
    with report.open('rb') as stream:
        # The vendor summary precedes detailed paths and fits this inherited window.
        text = stream.read(262144).decode('ascii', errors='replace')
    for line in text.splitlines():
        match = re.search(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\)', line)
        if match:
            section = match.groups()
        match = re.fullmatch(r'\s*(\w+)\s+(?:(\w+)\s+)?(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*', line)
        if match and section:
            launch, capture, slack, total, failing, endpoints = match.groups()
            assert float(slack) >= 0 and float(total) == 0 and int(failing) == 0, line
            rows.append(dict(section=section, launch=launch, capture=capture or launch,
                             slack=float(slack), total=float(total), failing=int(failing), endpoints=int(endpoints)))
    assert len(rows) == 126, len(rows)
    for corner in ('Slow', 'Fast'):
        for kind in ('Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width'):
            assert any(r['section'] == (kind, corner) for r in rows), (kind, corner)
    return dict(status='PASS', report_sha256=sha(report), rows=rows)

def clock_summary(report):
    with report.open('rb') as stream:
        text = stream.read(262144).decode('ascii', errors='replace')
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(\w+)\s+(\d+\.\d+)\s+\{(\d+\.\d+) (\d+\.\d+)\}\s+(Declared|Generated \([^)]*\))\s+\d+\s+\d+\s+(\{.*\})\s*', line)
        if match:
            name, period, rising, falling, kind, sources = match.groups()
            assert name not in result, name
            result[name] = dict(period=float(period), rising=float(rising), falling=float(falling), kind=kind, sources=sources)
    assert len(result) == 20, ('Clock summary incomplete', len(result))
    return result

def constraints(report, baseline):
    expected = clock_summary(baseline)
    actual = clock_summary(report)
    for cam in (3, 4):
        name = 'cmos%d_pclk' % cam
        assert expected[name]['kind'] == 'Declared' and expected[name]['sources'] == '{' + name + '}'
        # PDS quantizes the 8.9285 ns FDC edge to its 0.001 ns grid and
        # prints 8.9280. The byte-exact FDC check separately binds 8.9285.
        expected[name].update(period=17.857, falling=8.928)
    assert actual == expected, ('Final clock constraints differ', actual, expected)
    return dict(status='PASS', clocks=actual, report_sha256=sha(report))
