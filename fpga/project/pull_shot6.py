# -*- coding: utf-8 -*-
"""pull_shot6.py -- 从 RK3568 分片拉取截图 (stdout 流式, 避免参数长度限制)"""
import sys, base64
sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\project')
import board_ssh

def pull(remote, local):
    cli = board_ssh.connect()
    try:
        rc, out, err = board_ssh.run(cli, f"base64 -w0 {remote} | wc -c", timeout=30)
        total = int(out.strip())
        CH = 240000  # base64 字符分片
        data = b''
        off = 1
        while off <= total:
            rc, out, err = board_ssh.run(
                cli, f"tail -c +{off} {remote}.b64 2>/dev/null | head -c {CH}", timeout=60)
            if not out.strip():
                break
            data += out.strip().encode()
            off += CH
        raw = base64.b64decode(data)
        open(local, 'wb').write(raw)
        import hashlib
        print(local, len(raw), 'bytes  md5(partial-check skipped)')
    finally:
        cli.close()

if __name__ == '__main__':
    cli = board_ssh.connect()
    for f in ('six1', 'six2'):
        rc, out, err = board_ssh.run(cli, f"base64 -w0 /tmp/{f}.png > /tmp/{f}.b64 && wc -c /tmp/{f}.b64", timeout=30)
        print(f, out.strip())
    cli.close()
    pull('/tmp/six1.png.b64', r'C:\Users\NineSun\Desktop\ov56401\project\six1.png')
    pull('/tmp/six2.png.b64', r'C:\Users\NineSun\Desktop\ov56401\project\six2.png')
