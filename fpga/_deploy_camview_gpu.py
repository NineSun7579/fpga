#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deploy the GPU (QOpenGLWidget) camview to the board and build it."""
import sys
from board_ssh import connect, run

LOCAL = r"C:\Users\NineSun\Desktop\ov56401\project\host\camview\main.cpp"
REMOTE = "/root/ov5640/camview"
STAGE = "/tmp/main_gpu_20260927.cpp"


def sh(cli, cmd, timeout=300, sudo=True):
    print("$ " + cmd)
    rc, out, err = run(cli, cmd, timeout=timeout, sudo=sudo)
    sys.stdout.write(out)
    if err.strip():
        sys.stdout.write("[stderr] " + err[-3000:])
    print("(rc=%d)\n" % rc)
    return rc, out, err


def main():
    cli = connect()
    try:
        sftp = cli.open_sftp()
        sftp.put(LOCAL, STAGE)
        sftp.close()

        sh(cli, "cp %s %s/main.cpp.gpu_20260927" % (STAGE, REMOTE))
        sh(cli, "cp -n %s/main.cpp %s/main.cpp.bak_cpu_20260927" % (REMOTE, REMOTE))
        sh(cli, "cp -n %s/camview %s/camview.bak_cpu_20260927" % (REMOTE, REMOTE))
        sh(cli, "cp %s %s/main.cpp" % (REMOTE + "/main.cpp.gpu_20260927", REMOTE))
        sh(cli, "cd %s && qmake && make -j4" % REMOTE)
        sh(cli, "ls -la %s/ | grep -E 'camview|main.cpp'" % REMOTE)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
