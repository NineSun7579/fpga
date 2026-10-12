"""Quiesce/reconnect the 100H endpoint; all board operations are explicit actions."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import time
import uuid

from board_host import ssh_connect

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "log/100h_motion"
PCI = "/sys/bus/pci/devices/0002:21:00.0"
DEVICE = "/dev/pango_pci_driver"
MODULE = "pango_pci_driver"
QUIT = '''import ctypes as c,re,subprocess,sys
pid=int(sys.argv[1]);verify_only=sys.argv[2]=='check'
tree=subprocess.check_output(['xwininfo','-root','-tree'],timeout=5).decode()
windows=[]
for wid in re.findall(r'(0x[0-9a-fA-F]+) "camview  QUAD THREAD VIEW"',tree):
 p=subprocess.run(['xprop','-id',wid,'_NET_WM_PID'],capture_output=True,text=True,timeout=5)
 m=re.search(r'_NET_WM_PID\\([^)]*\\)\\s*=\\s*(\\d+)',p.stdout)
 if p.returncode==0 and m and int(m[1])==pid: windows.append(wid)
assert len(windows)==1, 'Expected one viewer window associated with PID '+str(pid)
if verify_only: sys.exit(0)
x=c.CDLL('libX11.so.6');t=c.CDLL('libXtst.so.6')
x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p
x.XKeysymToKeycode.argtypes=[c.c_void_p,c.c_ulong];x.XKeysymToKeycode.restype=c.c_uint
x.XSetInputFocus.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_ulong]
x.XFlush.argtypes=[c.c_void_p];x.XCloseDisplay.argtypes=[c.c_void_p]
t.XTestFakeKeyEvent.argtypes=[c.c_void_p,c.c_uint,c.c_int,c.c_ulong]
d=x.XOpenDisplay(None);assert d
try:
 x.XSetInputFocus(d,int(windows[0],16),2,0)
 key=x.XKeysymToKeycode(d,ord('q'));assert key
 assert t.XTestFakeKeyEvent(d,key,1,0)
 assert t.XTestFakeKeyEvent(d,key,0,0)
 x.XFlush(d)
finally: x.XCloseDisplay(d)
'''


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def absolute_remote(value):
    if not isinstance(value, str) or not value.startswith("/") or any(c in value for c in "\x00\r\n"):
        raise ValueError("Expected an absolute remote path")
    return value


class Operation:
    """One locally serialized operation, with an atomic retained state receipt."""
    def __init__(self, action, lock_path):
        self.lock_path = Path(lock_path)
        self.action = action
        self.token = uuid.uuid4().hex
        self.path = LOG / ("board_session_" + self.token + ".json")
        self.receipt = {"action": action, "operation": self.token, "status": "running", "states": []}

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise RuntimeError("Board session lock exists; inspect its owner before removing: " + str(self.lock_path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"pid": os.getpid(), "operation": self.token, "action": self.action}, stream)
            LOG.mkdir(parents=True, exist_ok=True)
            self.state("locked")
        except BaseException:
            self.lock_path.unlink()
            raise
        return self

    def state(self, state, **details):
        self.receipt.update(details)
        self.receipt["state"] = state
        self.receipt["states"].append({"state": state, "time": time.strftime("%Y-%m-%d %H:%M:%S")})
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.receipt, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def __exit__(self, kind, error, traceback):
        try:
            self.receipt["status"] = "failed" if kind else "success"
            if kind:
                self.receipt["error"] = str(error)
            self.state("failed" if kind else "complete")
        finally:
            # Never delete a replacement lock belonging to another operation.
            if load(self.lock_path).get("operation") == self.token:
                self.lock_path.unlink()
            print("Session receipt: " + str(self.path))


class Remote:
    def __init__(self, client):
        self.client = client

    def run(self, command, allowed=(0,), timeout=30):
        deadline = time.monotonic() + timeout
        stdin, stdout, stderr = self.client.exec_command(
            "sudo -S -p '' sh -c " + shlex.quote(command), timeout=timeout)
        channel = stdout.channel
        data, error = bytearray(), bytearray()
        try:
            stdin.write("123456\n")
            stdin.flush()
            channel.shutdown_write()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Remote command deadline exceeded; remote state may have changed: " + command)
                # Drain both streams fairly; do not read either stream to EOF.
                if channel.recv_ready():
                    data.extend(channel.recv(65536))
                if channel.recv_stderr_ready():
                    error.extend(channel.recv_stderr(65536))
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    code = channel.recv_exit_status()
                    break
                time.sleep(0.01)
            text, diagnostic = data.decode(errors="replace"), error.decode(errors="replace")
            if code not in allowed:
                raise RuntimeError("Remote command failed (%s): %s\n%s%s" % (code, command, text, diagnostic))
            return code, text, diagnostic
        finally:
            channel.close()

    def text(self, command, **kw):
        return self.run(command, **kw)[1]

    def owners(self, allow_absent=False):
        self.text("command -v fuser >/dev/null")
        code, _, _ = self.run("test -c " + DEVICE, allowed=(0, 1))
        if code:
            if not allow_absent:
                raise RuntimeError("DMA device is absent or not a character device")
            self.text("test ! -e " + DEVICE + " && test ! -L " + DEVICE)
            return []
        code, text, diagnostic = self.run("fuser " + DEVICE, allowed=(0, 1))
        if code == 1 and (text.strip() or diagnostic.strip()):
            raise RuntimeError("fuser failed instead of reporting no owners: " + text + diagnostic)
        pids = text.split()
        if any(not pid.isdecimal() for pid in pids) or (code == 0 and not pids):
            raise RuntimeError("Unexpected fuser output: " + text + diagnostic)
        return sorted(set(pids))

    def viewers(self):
        self.text("command -v pgrep >/dev/null")
        # Private build name is truncated to 15 characters by Linux comm.
        pids = []
        for name in ('camview', 'camview_motion_'):
            code, text, diagnostic = self.run("pgrep -x " + name, allowed=(0, 1))
            if diagnostic.strip() or (code == 1 and text.strip()):
                raise RuntimeError("pgrep failed: " + text + diagnostic)
            found = text.split()
            if any(not pid.isdecimal() for pid in found) or (code == 0 and not found):
                raise RuntimeError("Unexpected pgrep output: " + text)
            pids.extend(found)
        return sorted(set(pids))


def candidate_hash(remote, path, digest):
    remote.text("test -f " + shlex.quote(path) + " && test ! -L " + shlex.quote(path))
    if remote.text("sha256sum -- " + shlex.quote(path)).split()[0] != digest:
        raise RuntimeError("Candidate viewer binary hash mismatch: " + path)
    remote.text("test -x " + shlex.quote(path))


def viewer_identity(remote, pid, baseline, build):
    exe = remote.text("readlink -f /proc/" + pid + "/exe").strip()
    baseline_exe = remote.text("readlink -f -- " + shlex.quote(baseline["exe"])).strip()
    if exe == baseline_exe:
        return exe
    candidate = build["remote_directory"] + "/camview"
    if exe not in (candidate, build["binary"]):
        raise RuntimeError("Unrecognized DMA/viewer owner %s: %s" % (pid, exe))
    digest = remote.text("sha256sum /proc/" + pid + "/exe").split()[0]
    if digest != build["binary_sha256"]:
        raise RuntimeError("Running candidate hash mismatch: " + pid)
    return exe


def window(remote, pid, baseline, check=False):
    env = baseline["env"]
    command = "env " + " ".join(shlex.quote(key + "=" + env[key]) for key in ("DISPLAY", "XAUTHORITY"))
    remote.text(command + " python3 -c " + shlex.quote(QUIT) + " " + pid + (" check" if check else " quit"))


def stop_viewer(remote, baseline, build, operation, timeout):
    current, viewers = remote.owners(), remote.viewers()
    if len(current) > 1 or viewers != current:
        raise RuntimeError("Expected at most one viewer, identical to DMA owners: %s / %s" % (viewers, current))
    if not current:
        operation.state("viewer_absent")
        return
    pid = current[0]
    viewer_identity(remote, pid, baseline, build)
    window(remote, pid, baseline, check=True)
    operation.state("viewer_stop_requested", previous_pid=pid)
    window(remote, pid, baseline)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        owners, viewers = remote.owners(), remote.viewers()
        exited = remote.run("test ! -d /proc/" + pid, allowed=(0, 1))[0] == 0
        if exited and not owners and not viewers:
            operation.state("viewer_stopped")
            return
        if any(other != pid for other in owners + viewers):
            raise RuntimeError("Another owner/viewer appeared during shutdown")
        time.sleep(0.2)
    raise RuntimeError("Graceful shutdown deadline exceeded; module/PCI left intact; PID " + pid)


def endpoint(remote, identity):
    code, text, _ = remote.run(
        "test -d " + PCI + " && cat " + PCI + "/vendor " + PCI + "/device && "
        "test -L " + PCI + "/driver && basename $(readlink -f " + PCI + "/driver) && "
        "test -d /sys/module/" + MODULE + " && test -c " + DEVICE +
        " && stat -c '%t:%T' " + DEVICE, allowed=(0, 1))
    if code:
        return False
    fields = text.split()
    if len(fields) != 4 or fields[:3] != [identity["vendor"], identity["device"], identity["driver"]]:
        raise RuntimeError("PCI identity/driver mismatch: " + text)
    actual_number = ":".join(str(int(part, 16)) for part in fields[3].split(":"))
    if identity.get("device_number") and actual_number != identity["device_number"]:
        raise RuntimeError("DMA node major/minor mismatch: " + actual_number)
    return True


def execute(args, operation):
    baseline, build = load(args.baseline), load(args.viewer_build)
    for key in ("exe", "cwd", "log"):
        absolute_remote(baseline[key])
    for key in ("binary", "remote_directory"):
        absolute_remote(build[key])
    if not re.fullmatch(r"[0-9a-f]{64}", build["binary_sha256"]):
        raise ValueError("Invalid candidate SHA256")
    environment = dict(baseline["env"])
    if not all(isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
               and isinstance(value, str) and "\x00" not in value for key, value in environment.items()):
        raise ValueError("Invalid saved viewer environment")
    if not all(environment.get(key) for key in ("DISPLAY", "XAUTHORITY")):
        raise ValueError("Saved DISPLAY/XAUTHORITY missing")
    if args.action in ("quiesce", "start"):
        status = load(args.build_status)
        if status.get("stage") != "complete" or status.get("status") != "complete":
            raise RuntimeError("Motion build status is not completed; live viewer remains untouched")
    # Restore is a recovery action and must work after a failed build.
    identity = None
    if args.action == "reconnect":
        if not args.identity_json:
            raise ValueError("reconnect requires --identity-json with baseline vendor, device, driver")
        identity = load(args.identity_json)
        for key in ("vendor", "device"):
            if not re.fullmatch(r"0x[0-9a-fA-F]{4}", identity[key]):
                raise ValueError("Invalid baseline PCI " + key)
            identity[key] = identity[key].lower()
        if identity.get("driver") not in (MODULE, "/sys/bus/pci/drivers/" + MODULE) or identity.get("bdf", "0002:21:00.0") != "0002:21:00.0":
            raise ValueError("Expected baseline BDF and pango_pci_driver")
        identity["driver"] = MODULE
        if identity.get("device_node", DEVICE) != DEVICE:
            raise ValueError("Unexpected baseline DMA node")
        if "device_number" in identity and not re.fullmatch(r"\d+:\d+", identity["device_number"]):
            raise ValueError("Invalid baseline DMA node major/minor")
    operation.state("local_preflight_complete")
    client = ssh_connect(timeout=8)
    remote = Remote(client)
    staged = None
    try:
        if args.action in ("quiesce", "start"):
            candidate_hash(remote, build["binary"], build["binary_sha256"])
        if args.action == "quiesce":
            stop_viewer(remote, baseline, build, operation, args.shutdown_timeout)
            if remote.owners() or remote.viewers():
                raise RuntimeError("Owner/viewer appeared before module unload")
            remote.text("test ! -d /sys/module/" + MODULE + " || rmmod " + MODULE)
            remote.text("test ! -d /sys/module/" + MODULE)
            operation.state("module_unloaded")
            remote.text("test ! -e " + PCI + "/remove || echo 1 > " + PCI + "/remove")
            remote.text("test ! -d " + PCI)
            operation.state("quiesced")
            print("Viewer stopped, module unloaded and PCIe endpoint removed")
        elif args.action == "reconnect":
            if remote.owners(allow_absent=True) or remote.viewers():
                raise RuntimeError("DMA owner/viewer active during reconnect")
            operation.state("rescan_requested", expected_identity=identity)
            remote.text("echo 1 > /sys/bus/pci/rescan")
            deadline = time.monotonic() + args.ready_timeout
            while remote.run("test -d " + PCI, allowed=(0, 1))[0]:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Endpoint did not enumerate before deadline")
                time.sleep(0.2)
            # Validate device before loading the driver.
            actual = remote.text("cat " + PCI + "/vendor " + PCI + "/device").split()
            if actual != [identity["vendor"], identity["device"]]:
                raise RuntimeError("Enumerated PCI identity mismatch: " + str(actual))
            remote.text("test -d /sys/module/" + MODULE + " || insmod /root/ov5640/" + MODULE + ".ko")
            while not endpoint(remote, identity):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Expected endpoint driver/node not ready before deadline")
                time.sleep(0.2)
            if remote.owners() or remote.viewers():
                raise RuntimeError("Owner/viewer appeared during reconnect")
            operation.state("reconnected")
            print("Expected PCIe endpoint, pango driver and DMA character node ready")
        else:
            if args.action == "start":
                binary = build["remote_directory"] + "/camview"
                created = remote.text("mktemp " + shlex.quote(build["remote_directory"] + "/.camview-stage.XXXXXXXX")).strip()
                if not re.fullmatch(re.escape(build["remote_directory"] + "/.camview-stage.") + r"[A-Za-z0-9]+", created):
                    raise RuntimeError("Unexpected staged candidate path")
                staged = created
                operation.state("candidate_stage_created", staged=staged)
                remote.text("cp -- " + shlex.quote(build["binary"]) + " " + shlex.quote(staged) +
                            " && chmod 755 -- " + shlex.quote(staged))
                candidate_hash(remote, staged, build["binary_sha256"])
                environment["CAMVIEW_MOTION"] = "1"
                logfile = build["remote_directory"] + "/runtime.log"
                operation.state("candidate_staged")
            else:
                binary, logfile = baseline["exe"], baseline["log"]
                remote.text("test -f " + shlex.quote(binary) + " && test -x " + shlex.quote(binary))
            # Discover log/cwd failures while the old viewer is still running.
            remote.text("test -d " + shlex.quote(baseline["cwd"]) + " && test -r " +
                        shlex.quote(environment["XAUTHORITY"]) + " && : >> " + shlex.quote(logfile))
            stop_viewer(remote, baseline, build, operation, args.shutdown_timeout)
            if staged:
                remote.text("test ! -L " + shlex.quote(binary) + " && "
                            "{ test ! -e " + shlex.quote(binary) + " || test -f " + shlex.quote(binary) + "; } && "
                            "mv -f -- " + shlex.quote(staged) + " " + shlex.quote(binary))
                staged = None
                candidate_hash(remote, binary, build["binary_sha256"])
                operation.state("candidate_installed")
            if remote.owners() or remote.viewers():
                raise RuntimeError("Owner/viewer appeared before launch")
            launch = ("cd " + shlex.quote(baseline["cwd"]) + " && exec env " +
                      " ".join(shlex.quote(key + "=" + value) for key, value in environment.items()) +
                      " " + shlex.quote(binary))
            operation.state("launch_requested", binary=binary, logfile=logfile)
            pid = remote.text("nohup sh -c " + shlex.quote(launch) + " >> " + shlex.quote(logfile) +
                              " 2>&1 </dev/null & echo $!").strip()
            if not pid.isdecimal():
                raise RuntimeError("Invalid launch PID; inspect log before retry")
            operation.state("launched", launched_pid=pid)
            deadline = time.monotonic() + args.ready_timeout
            while True:
                pids, owners = remote.viewers(), remote.owners()
                if any(other != pid for other in pids + owners):
                    raise RuntimeError("Unexpected owner/viewer after launch")
                if pids == [pid] and owners == [pid]:
                    exe = viewer_identity(remote, pid, baseline, build)
                    expected = remote.text("readlink -f -- " + shlex.quote(binary)).strip()
                    if exe != expected:
                        raise RuntimeError("Launch PID executable mismatch")
                    try:
                        window(remote, pid, baseline, check=True)
                        break
                    except RuntimeError:
                        if time.monotonic() >= deadline:
                            raise
                if remote.run("test -d /proc/" + pid, allowed=(0, 1))[0]:
                    raise RuntimeError("Launched viewer exited; inspect " + logfile)
                if time.monotonic() >= deadline:
                    raise RuntimeError("Viewer readiness deadline exceeded; inspect PID %s and %s" % (pid, logfile))
                time.sleep(0.2)
            operation.state("viewer_ready")
            print(remote.text("tail -35 -- " + shlex.quote(logfile)))
            print("Viewer PID " + pid + "; log " + logfile)
    finally:
        try:
            if staged:
                try:
                    remote.text("rm -f -- " + shlex.quote(staged))
                except Exception as error:
                    # Preserve the original failure and retain the exact staged path.
                    operation.receipt["stage_cleanup_error"] = str(error)
        finally:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("quiesce", "reconnect", "start", "restore"))
    parser.add_argument("--baseline", default=LOG / "viewer_launch_baseline.json", type=Path)
    parser.add_argument("--viewer-build", default=LOG / "viewer_build.json", type=Path)
    parser.add_argument("--build-status", default=ROOT / "project/motion_100h/status.json", type=Path)
    parser.add_argument("--identity-json", type=Path,
                        help='Baseline sysfs identity: vendor, device, driver (name or sysfs path), optional device_number (decimal major:minor)')
    parser.add_argument("--lock", default=LOG / "board_session.lock", type=Path)
    parser.add_argument("--shutdown-timeout", default=45, type=int)
    parser.add_argument("--ready-timeout", default=30, type=int)
    args = parser.parse_args()
    if not (1 <= args.shutdown_timeout <= 300 and 1 <= args.ready_timeout <= 300):
        parser.error("timeouts must be in 1..300 seconds")
    with Operation(args.action, args.lock) as operation:
        execute(args, operation)


if __name__ == "__main__":
    main()
