#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clean reload pango driver + restart GPU camview, then verify streaming."""
import sys, time
from board_ssh import connect, run


def sh(cli, cmd, timeout=180, sudo=True):
    print("$ " + cmd)
    rc, out, err = run(cli, cmd, timeout=timeout, sudo=sudo)
    sys.stdout.write(out)
    if err.strip():
        sys.stdout.write("[stderr] " + err[-2500:])
    print("(rc=%d)\n" % rc)
    return rc, out, err


def main():
    cli = connect()
    try:
        sh(cli, "pkill -f 'run_camview[.]sh'; sleep 1; pkill -x camview; sleep 2; pkill -9 -x camview; sleep 1; "
                "lsmod | grep pango || echo NO_MOD")
        sh(cli, "rmmod pango_pci_driver 2>&1; sleep 1; lsmod | grep pango || echo MOD_GONE")
        sh(cli, "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; lsmod | grep pango")
        sh(cli, "echo [DMESG]; dmesg | tail -8")
        sh(cli, "rm -f /tmp/camview.lock; "
                "setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & echo STARTED")
        time.sleep(14)
        sh(cli, "echo [LOG]; tail -n 8 /tmp/camview.log")
        sh(cli, "echo [PROC]; ps -eo pid,etimes,pcpu,args | grep camview | grep -v grep")
        sh(cli, "echo [H]; timeout 3 top -H -b -n2 -p $(pgrep -x camview | head -1) | tail -14")
        sh(cli, "echo [TOP]; top -bn1 | head -9")
        sh(cli, "cd /root/ov5640/qshot && DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "
                "./qshot /tmp/gpu_now.png >/dev/null 2>&1; chmod 644 /tmp/gpu_now.png; ls -la /tmp/gpu_now.png")
        sftp = cli.open_sftp()
        sftp.get("/tmp/gpu_now.png", r"C:\Users\NineSun\AppData\Local\Temp\opencode\gpu_now.png")
        sftp.close()
        print("pulled /tmp/gpu_now.png")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
