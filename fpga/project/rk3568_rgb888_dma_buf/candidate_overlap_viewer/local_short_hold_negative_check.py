"""Prove the post-release fixture rejects the original fair copy ordering."""
from pathlib import Path
import os
import resource
import shlex
import subprocess

root = Path(__file__).resolve().parent
build = root / "local_build"
protocol = (build / "protocol.cpp").read_text()
fair = (root.parent / "candidate_fair_viewer" / "main.cpp").read_text(encoding="utf-8-sig")
start = "class PangoDev {"
end = "volatile sig_atomic_t PangoDev::timeoutHit_ = 0;"
old_class = fair[fair.index(start):fair.index(end) + len(end)]
# Accept the new optional argument so rejection tests copy order, not compilation.
old_class = old_class.replace("std::shared_ptr<scheme2::Input>& input) {",
    "std::shared_ptr<scheme2::Input>& input, scheme2::PrefetchTiming* = nullptr) {")
mutant = protocol[:protocol.index(start)] + old_class + protocol[protocol.index(end) + len(end):]
source = build / "short_hold_old_order.cpp"
source.write_text(mutant)
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "Qt5Core", "Qt5Gui"], text=True))
binary = build / "short_hold_old_order"
subprocess.run(["g++", "-std=c++17", "-O2", "-fPIC", "-pthread", "-I" + str(root),
    str(source), "-o", str(binary), *flags,
    "-Wl,--wrap=open,--wrap=close,--wrap=raise,--wrap=mmap,--wrap=munmap,--wrap=ioctl"], check=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
env = dict(os.environ, DETVIEW_FPGA_INFER_RGB="1", DETVIEW_FPGA_PREFETCH_TIMING="0")
result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=15)
(build / "short_hold_negative.log").write_text(result.stdout + result.stderr)
assert result.returncode != 0
assert "regs[0x10] == 0 && regs[0x120] == 0 && regs[0x90] == regs[0x50]" in result.stderr
print("SHORT_HOLD_NEGATIVE_PASS: original fair copy order rejected at actual copy boundary")
