"""Capture the RK3568 X11 desktop and runtime evidence without owning DMA."""
import argparse
import json
from pathlib import Path
import re
import shlex
import struct

from PIL import Image
from board_host import ssh_connect
from observe_motion_runtime import viewer_identity


X11 = "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "


def viewer_window(run, pid):
    clients = run(X11 + "xprop -root _NET_CLIENT_LIST")
    windows = []
    for window in re.findall(r"0x[0-9a-fA-F]+", clients):
        owner = run(X11 + "xprop -id " + window + " _NET_WM_PID")
        if re.search(r"=\s*" + re.escape(pid) + r"\s*$", owner):
            info = run(X11 + "xwininfo -id " + window)
            if "Map State: IsViewable" in info:
                windows.append(window)
    if len(windows) != 1:
        raise RuntimeError("Expected exactly one visible X11 window owned by the viewer")
    return windows[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    args = parser.parse_args()
    if not args.label.replace("_", "").isalnum():
        parser.error("label must contain only letters, digits and underscores")
    output = Path(__file__).resolve().parents[2] / "log" / "100h_motion"
    output.mkdir(parents=True, exist_ok=True)
    client = ssh_connect(timeout=8)
    try:
        def run(command):
            stdin, stdout, stderr = client.exec_command(
                "sudo -S sh -c " + shlex.quote(command), timeout=30)
            stdin.write("123456\n")
            stdin.flush()
            data, error = stdout.read(), stderr.read()
            if stdout.channel.recv_exit_status():
                raise RuntimeError(error.decode(errors="replace"))
            return data

        def text(command):
            return run(command).decode(errors="replace")

        identity = viewer_identity(text, output)
        window = viewer_window(text, identity["pid"])
        raw = run(X11 + "xwd -id " + window + " -silent")
        viewer_identity(text, output, identity)
        if viewer_window(text, identity["pid"]) != window:
            raise RuntimeError("Viewer window changed during screenshot")
        fields = struct.unpack(">25I", raw[:100])
        header, version, _, _, width, height, _, order = fields[:8]
        bpp, stride = fields[11:13]
        red, green, blue = fields[14:17]
        colors = fields[19]
        if (version, bpp, order, red, green, blue) != (
                7, 32, 0, 0xff0000, 0xff00, 0xff):
            raise RuntimeError("Unsupported XWD pixel format: " + repr(fields))
        image = Image.frombytes("RGB", (width, height), raw[header + colors * 12:],
                                "raw", "BGRX", stride, 1)
        path = output / (args.label + ".png")
        evidence = run(
            "date; cat /proc/uptime; pgrep -a -x camview; pgrep -a -x camview_motion_; "
            "fuser /dev/pango_pci_driver 2>/dev/null || true; "
            "readlink /proc/" + identity["pid"] + "/fd/2; "
            "tail -70 /proc/" + identity["pid"] + "/fd/2; "
            "grep -c 'flip timeout' /var/log/Xorg.0.log || true")
        viewer_identity(text, output, identity)
        if viewer_window(text, identity["pid"]) != window:
            raise RuntimeError("Viewer window changed during runtime evidence collection")
        image.save(path)
        evidence += ("\nviewer_identity=" + json.dumps(identity, sort_keys=True) +
                     "\nviewer_window=" + window + "\n").encode()
        (output / (args.label + "_runtime.txt")).write_bytes(evidence)
        print(path)
    finally:
        client.close()


if __name__ == "__main__":
    main()
