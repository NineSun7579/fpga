#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the camview help-text tail (R/+/-/H lines were mangled by an earlier
patch that inserted real newlines instead of backslash-n escapes)."""
from pathlib import Path

p = Path(r'C:/Users/NineSun/Desktop/ov56401/project/host/camview/main.cpp')
raw = p.read_bytes()
raw = raw.replace(b'// ZTESTMARKER12345\n', b'')

BSN = b'\\n'          # backslash + n
Q = b'"'
EOL = b'\n'

def u(s):             # utf-8 bytes of a str
    return s.encode('utf-8')

start = raw.find(u('        "  R         '))
assert start > 0, 'R line not found'
tail_marker = u('        "') + u('\u6309 H \u5173\u95ed\u5e2e\u52a9') + b'";'
end = raw.find(tail_marker)
assert end > start, (start, end)
endline = raw.find(b'\n', end) + 1

replacement = b''.join([
    u('        "  R         ') + u('\u9510\u5316 \u5f00/\u5173 (cam1)') + BSN + Q + EOL,
    u('        "  +/-       ') + u('\u9510\u5316\u5f3a\u5ea6 2..6') + BSN + Q + EOL,
    u('        "  H         ') + u('\u663e\u793a / \u9690\u85cf\u672c\u5e2e\u52a9') + BSN + Q + EOL,
    u('        "') + BSN + Q + EOL,
    u('        "') + u('\u6309 H \u5173\u95ed\u5e2e\u52a9') + b'";' + EOL,
])
raw = raw[:start] + replacement + raw[endline:]
p.write_bytes(raw)

t = raw.decode('utf-8')
i = t.index('  R   ')
print(t[i-14:i+300])
