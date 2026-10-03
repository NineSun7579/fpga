# -*- coding: utf-8 -*-
"""reg_pds_sfp.py -- 在 project/project.pds 与 project_build/project.pds 登记 SFP 新文件"""
import os, datetime

os.chdir(r'C:\Users\NineSun\Desktop\ov56401\project')
TS = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

SRC_FILES = [
    '../source/sfp/sfp_rx_link.v',
    '../source/sfp/sfp_video_rx.v',
    '../source/sfp/sfp_rx_cam_if.v',
    '../source/sfp/video_async_fifo.v',
]

def ip_block(ipdir_rel, ipdir_local, idfname):
    lines = ['(_ip "%s/%s.idf"' % (ipdir_rel, idfname),
             '                    (_timespec "%s")' % TS]
    for root, dirs, files in os.walk(ipdir_local):
        dirs.sort()
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), ipdir_local).replace(os.sep, '/')
            if rel.endswith('.idf'):
                continue
            lines.append('                    (_ip_source_item "%s/%s"' % (ipdir_rel, rel))
            lines.append('                        (_timespec "%s")' % TS)
            lines.append('                    )')
    lines.append('                )')
    return '\n                '.join(lines)

for pds in ['project/project.pds', 'project_build/project.pds']:
    raw = open(pds, 'rb').read()
    t = raw.decode('utf-8')
    if 'sfp_rx_link' in t:
        print(pds, 'ALREADY registered, skip')
        continue
    # 1) 源文件: 插在第一个 (_file "../source/ 前
    src_block = ''.join(
        '(_file "%s"\n                    (_format verilog)\n                    (_timespec "%s")\n                )\n                ' % (f, TS)
        for f in SRC_FILES)
    anchor = '(_file "../source/'
    i = t.find(anchor)
    assert i > 0, pds
    t = t[:i] + src_block + t[i:]
    # 2) IP: 插在 pcie_test _ip 前
    ipb = ip_block('../ipcore/hsst_sfp', 'ipcore/hsst_sfp', 'hsst_sfp')
    j = t.find('(_ip "../ipcore/pcie_test/pcie_test.idf"')
    assert j > 0, pds + ' no pcie ip anchor'
    t = t[:j] + ipb + '\n                ' + t[j:]
    # 3) 约束: 插在 cdc.fdc 前
    c = t.find('(_file "../source/constraints/cdc.fdc"')
    assert c > 0, pds + ' no cdc anchor'
    con = '(_file "../source/constraints/sfp.fdc"\n                    (_format fdc)\n                    (_timespec "%s")\n                )\n                ' % TS
    t = t[:c] + con + t[c:]
    open(pds, 'wb').write(t.encode('utf-8'))
    print(pds, 'registered OK')
