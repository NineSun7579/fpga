#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""board_push.py -- RK3568 文件推送(exec+base64 通道, sftp 不可用时的替代)
用法: python board_push.py <local> <remote> [--sudo]"""
import sys, base64, hashlib
sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\project')
import board_ssh

local, remote = sys.argv[1], sys.argv[2]
sudo = '--sudo' in sys.argv

data = open(local, 'rb').read()
b64 = base64.b64encode(data).decode()
md5 = hashlib.md5(data).hexdigest()

cli = board_ssh.connect()
try:
    tmp = '/tmp/bp_' + md5[:8]
    # 分块写入 (每块 3KB base64, 避免单条命令过长)
    CH = 3072
    for i in range(0, len(b64), CH):
        chunk = b64[i:i+CH]
        op = '>' if i == 0 else '>>'
        rc, out, err = board_ssh.run(cli, "printf %%s '%s' %s %s.b64" % (chunk, op, tmp), timeout=30)
        assert rc == 0, (rc, err)
    cmd = "base64 -d %s.b64 > %s && md5sum %s && rm -f %s.b64" % (tmp, remote, remote, tmp)
    if sudo:
        cmd = "cp /dev/null /dev/null; " + cmd
        rc, out, err = board_ssh.run(cli, "echo '%s' | sudo -S bash -c %s" % (
            board_ssh.PW, "'" + cmd.replace("'", "'\\''") + "'"), timeout=60)
    else:
        rc, out, err = board_ssh.run(cli, cmd, timeout=60)
    print(out.strip()[-200:])
    ok = md5 in out
    print('MD5_MATCH' if ok else 'MD5_MISMATCH local=%s' % md5)
    sys.exit(0 if ok else 1)
finally:
    cli.close()
