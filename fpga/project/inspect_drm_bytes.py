from pathlib import Path
import shutil
root = Path(__file__).parent
for parent in (root.parent.parent, root.parent, root):
    p = parent / 'AGENTS.md'
    if p.exists():
        print(str(p), p.read_bytes().decode('utf-8', errors='replace'))
target = root / 'source/ov5640/ov5640_ddr/ov5640_ddr_w.v'
for parent in reversed(target.parent.parents):
    if parent != root and root in parent.parents:
        p = parent / 'AGENTS.md'
        if p.exists():
            print(str(p), p.read_bytes().decode('utf-8', errors='replace'))
p = target.parent / 'AGENTS.md'
if p.exists():
    print(str(p), p.read_bytes().decode('utf-8', errors='replace'))
data = target.read_bytes()
print('TARGET', str(target))
for i, line in enumerate(data.splitlines(), 1):
    print('%d: %s' % (i, line.decode('gbk', errors='replace')))
for name in ('vsim', 'vlog', 'vlib', 'python'):
    print('TOOL', name, shutil.which(name))
print('FIFO FILES')
for p in root.rglob('*'):
    if p.is_file() and ('fifo' in p.name.lower() or p.name.lower() == 'modelsim.ini'):
        print(p.relative_to(root))
