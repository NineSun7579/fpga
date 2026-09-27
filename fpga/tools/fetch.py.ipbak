#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch.py -- retrying SFTP get/put for the RK3568 board (flaky-link tolerant).

Usage:
  python tools/fetch.py get <remote> <local>
  python tools/fetch.py put <local> <remote>
"""
import sys
import time
import warnings

warnings.filterwarnings("ignore")
import paramiko  # noqa: E402

HOST = "192.168.10.241"
USER, PW = "linaro", "123456"


def connect(tries=8):
    last = None
    for _ in range(tries):
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
    raise SystemExit("sftp connect failed after %d tries: %s" % (tries, last))


def main():
    mode, a, b = sys.argv[1], sys.argv[2], sys.argv[3]
    cli = connect()
    try:
        sftp = cli.open_sftp()
        if mode == "get":
            sftp.get(a, b)
        elif mode == "put":
            sftp.put(a, b)
        else:
            raise SystemExit("mode must be get|put")
        sftp.close()
        print("%s OK: %s -> %s" % (mode, a, b))
    finally:
        cli.close()


if __name__ == "__main__":
    main()
