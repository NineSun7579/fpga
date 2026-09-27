#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_camview.py : SSH/SFTP 部署 camview（替代串口 push_dualcam.py）

用法:
    python tools/deploy_camview.py build     # 上传 host/camview/main.cpp + 板上重编
    python tools/deploy_camview.py run       # 启动 camview（run_camview.sh 守护）
    python tools/deploy_camview.py status    # 查看进程/窗口/驱动状态
"""
import paramiko, hashlib, os, sys, time

HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "host", "camview", "main.cpp")
DST = "/root/ov5640/camview/main.cpp"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15,
              auth_timeout=15, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, timeout=600, sudo=True):
    if sudo:
        cmd = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    rc = out.channel.recv_exit_status()
    return rc, o, e


def do_build(c):
    data = open(SRC, "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    print("本地 %s  %d bytes  md5=%s" % (SRC, len(data), md5))
    sftp = c.open_sftp()
    sftp.put(SRC, "/tmp/main.cpp.new")
    sftp.close()
    rc, o, e = run(c, "cp /tmp/main.cpp.new %s && chown root:root %s && md5sum %s" % (DST, DST, DST))
    print(o.strip(), e.strip())
    if md5 not in o:
        raise SystemExit("远端 md5 不一致，中止")
    print("远端 md5 一致 OK")

    # NOTE: never use `pkill -f camview` over SSH -- the current shell's own
    # command line contains the path ".../camview" and would match/kill itself.
    run(c, "killall -9 camview 2>/dev/null; pkill -f '[r]un_camview' 2>/dev/null; sleep 1; true")

    print("== 板上重编 ==")
    rc, o, e = run(c,
        "cd /root/ov5640/camview && rm -f camview Makefile *.o moc_* .qmake.stash && "
        "/usr/lib/qt5/bin/qmake && make -j4 > /tmp/mk.log 2>&1; echo RC=$?; "
        "grep -aiE 'error' /tmp/mk.log | head -10; ls -la camview", timeout=900)
    print(o.strip())
    if "RC=0" not in o:
        rc, o, e = run(c, "tail -20 /tmp/mk.log")
        print("编译失败，日志尾部:\n" + o)
        raise SystemExit(1)
    print("编译 OK")


def do_run(c):
    run(c, "killall -9 camview 2>/dev/null; pkill -f '[r]un_camview' 2>/dev/null; sleep 1; true")
    run(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null & sleep 12; true")
    do_status(c)


def do_status(c):
    rc, o, e = run(c,
        "echo ---PROC---; ps aux | grep -a './camview' | grep -v grep | head -3; "
        "echo ---WIN---; DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -root _NET_CLIENT_LIST 2>/dev/null | grep -oE '0x[0-9a-f]+' | while read id; do "
        "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id \"$id\" _NET_WM_NAME 2>/dev/null; done | grep -a camview; "
        "echo ---DRV---; ls -l /dev/pango_pci_driver; lspci -nn | grep -i 0755; echo DONE")
    print(o.strip())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    c = conn()
    try:
        if mode == "build":
            do_build(c)
        elif mode == "run":
            do_run(c)
        elif mode == "status":
            do_status(c)
        else:
            print(__doc__)
    finally:
        c.close()


if __name__ == "__main__":
    main()
