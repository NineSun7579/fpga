"""Prove the actual-acquisition poll fixture catches the old lock-held wait."""
import os
from pathlib import Path
import shlex
import subprocess

root = Path(__file__).resolve().parent
unit = (root / "local_build/protocol.cpp").read_text()
block = "lock.unlock();\n                QThread::msleep(1);\n                lock.relock();"
assert unit.count(block) == 1
mutant = root / "local_build/protocol_poll_mutant.cpp"
mutant.write_text(unit.replace(block, "QThread::msleep(1);"))
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "Qt5Core", "Qt5Gui"], text=True))
binary = root / "local_build/protocol_poll_mutant"
subprocess.run(["g++", "-std=c++17", "-O2", "-fPIC", "-pthread", "-I.",
                str(mutant), "-o", str(binary), *flags,
                "-Wl,--wrap=open,--wrap=close,--wrap=raise,--wrap=mmap,--wrap=munmap,--wrap=ioctl"],
               cwd=root, check=True)
env = dict(os.environ, DETVIEW_FPGA_INFER_RGB="1")
result = subprocess.run([str(binary)], cwd=root, env=env, capture_output=True,
                        text=True, timeout=15)
(root / "local_build/poll_negative.log").write_text(result.stdout + result.stderr)
assert result.returncode != 0
assert "uncertain FPGA admission/conversion deadline" in result.stderr
print("FAIR_NEGATIVE_CHECK_PASS old lock-held poll rejected at FPGA deadline")
