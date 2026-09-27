#!/usr/bin/env python3
"""_put.py <local> [remote] -- scp a file to the RK3568 board /tmp (powell-tolerant)."""
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
import paramiko  # noqa: E402

HOST = "192.168.10.203"
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
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1.5)
    raise SystemExit("ssh connect failed: %s" % last)


def main():
    local = sys.argv[1]
    remote = sys.argv[2] if len(sys.argv) > 2 else "/tmp/" + os.path.basename(local)
    cli = connect()
    try:
        sftp = cli.open_sftp()
        sftp.put(local, remote)
        sftp.close()
        print("put %s -> %s" % (local, remote))
    finally:
        cli.close()


if __name__ == "__main__":
    main()
