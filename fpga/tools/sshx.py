#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sshx.py -- retrying SSH runner for the RK3568 board (flaky link tolerant).

Usage:
  python sshx.py "<shell command>" [--sudo] [--timeout 300] [--tries 8]
Exit code = remote exit status (0 if all tries fail? no -> 255).
"""
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import paramiko  # noqa: E402

HOST = "192.168.10.203"
USER, PW = "linaro", "123456"


def connect(tries=8):
    last = None
    for i in range(tries):
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            cli.connect(HOST, 22, USER, PW, timeout=10,
                        banner_timeout=15, auth_timeout=15,
                        allow_agent=False, look_for_keys=False)
            return cli
        except Exception as e:  # noqa: BLE001
            last = e
            try:
                cli.close()
            except Exception:
                pass
            time.sleep(1.5)
    raise SystemExit("ssh connect failed after %d tries: %s" % (tries, last))


def main():
    args = [a for a in sys.argv[1:]]
    sudo = "--sudo" in args
    tries = 8
    timeout = 300
    if "--tries" in args:
        tries = int(args[args.index("--tries") + 1])
    if "--timeout" in args:
        timeout = int(args[args.index("--timeout") + 1])
    pos = [a for a in args if not a.startswith("--") and a not in
           (str(tries), str(timeout))]
    cmd = pos[0] if pos else "echo no-cmd"
    if sudo:
        cmd = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    cli = connect(tries)
    try:
        _, out, err = cli.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        rc = out.channel.recv_exit_status()
        sys.stdout.write(o)
        if e.strip():
            sys.stdout.write("[stderr] " + e[-2000:] + "\n")
        print("[rc=%d]" % rc)
        sys.exit(rc)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
