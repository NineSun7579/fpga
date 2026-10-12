#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""board_ssh.py -- RK3568 board access over the LAN (192.168.10.x).
SSH linaro/linaro; helper CLI used by the deploy/verify steps.
Note: the board IP changed from 192.168.137.4 to 192.168.10.203; update
HOST below whenever the DHCP lease changes.

Usage:
  python board_ssh.py run "<shell command>"
  python board_ssh.py put <local> <remote>
  python board_ssh.py get <remote> <local>
"""
import sys, paramiko

HOST = '192.168.10.203'
USER, PW = 'linaro', '123456'


def connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, 22, USER, PW, timeout=8, allow_agent=False, look_for_keys=False)
    return cli


def run(cli, cmd, timeout=120, sudo=False):
    if sudo:
        cmd = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main():
    cli = connect()
    try:
        mode = sys.argv[1] if len(sys.argv) > 1 else 'run'
        if mode == 'run':
            rc, out, err = run(cli, sys.argv[2], timeout=300, sudo=('--sudo' in sys.argv))
            print(out)
            if err.strip():
                print('[stderr]', err[-1500:])
            sys.exit(rc)
        elif mode == 'put':
            sftp = cli.open_sftp()
            sftp.put(sys.argv[2], sys.argv[3])
            sftp.close()
            print('put OK')
        elif mode == 'get':
            sftp = cli.open_sftp()
            sftp.get(sys.argv[2], sys.argv[3])
            sftp.close()
            print('get OK')
    finally:
        cli.close()


if __name__ == '__main__':
    main()
