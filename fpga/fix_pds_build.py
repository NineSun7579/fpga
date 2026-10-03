# -*- coding: utf-8 -*-
"""fix_pds_build.py -- project_build/project.pds 补齐缺失的源文件登记
对照 project/project.pds 的源文件集合, 补上 project_build 缺失且磁盘上存在的 .v"""
import os, re, datetime

os.chdir(r'C:\Users\NineSun\Desktop\ov56401\project')
TS = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

main_t = open('project/project.pds', 'rb').read().decode('utf-8')
bld_t  = open('project_build/project.pds', 'rb').read().decode('utf-8')

main_files = set(re.findall(r'_file \"(\.\./source/[^\"]+\.v)\"', main_t))
bld_files  = set(re.findall(r'_file \"(\.\./source/[^\"]+\.v)\"', bld_t))

missing = sorted(f for f in (main_files - bld_files) if os.path.exists(f.lstrip('./')))
print('missing in project_build (and exist on disk):')
for f in missing:
    print(' ', f)

blk = ''.join(
    '(_file "%s"\n                    (_format verilog)\n                    (_timespec "%s")\n                )\n                ' % (f, TS)
    for f in missing)
if blk:
    anchor = '(_file "../source/sfp/sfp_rx_link.v"'
    i = bld_t.find(anchor)
    assert i > 0
    bld_t = bld_t[:i] + blk + bld_t[i:]
    open('project_build/project.pds', 'wb').write(bld_t.encode('utf-8'))
    print('patched %d files into project_build/project.pds' % len(missing))
else:
    print('nothing to patch')
