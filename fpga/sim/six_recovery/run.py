"""Read-only RTL audit and isolated ModelSim startup/frame recovery regressions."""
from pathlib import Path
import hashlib
import os
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
SIM = Path(os.environ.get("MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))


def audit_top():
    raw = (PROJECT / "source/top.v").read_bytes()
    text = re.sub(rb"/\*.*?\*/|//[^\r\n]*", b"", raw, flags=re.S)
    block = re.search(rb"reg\s+\[15:0\]\s+camera_startup_count\s*=.*?\nend\s*\r?\n", text, re.S)
    assert block, "top startup reset block absent"
    # Preserve the actual source bytes, including comments, for compilation.
    start = raw.index(b"reg [15:0] camera_startup_count")
    end = raw.index(b"\nend", start) + len(b"\nend")
    (HERE / "top_startup_block.vh").write_bytes(raw[start:end] + b"\n")
    ports = re.findall(rb"\.clk_50m_rst_n\s*\(\s*([^)]*)\)", text)
    assert ports == [b"camera_ctrl_rst_n"] * 4, ports
    report = ["PASS top camera reset ports: four use camera_ctrl_rst_n"]
    for cam in (5, 6):
        prefix = f"cam{cam}"
        bodies = []
        for instance in (prefix + "_ov5640_ddr", prefix + "_axi_dma_write"):
            match = re.search(instance.encode() + rb"\s*\((.*?)\);", text, re.S)
            assert match, instance
            bodies.append(dict((p.decode(), n.strip().decode()) for p, n in
                               re.findall(rb"\.(\w+)\s*\(\s*([^)]*)\)", match[1])))
        camera, dma = bodies
        for cp, dp, net in (("dma_done", "data_in_last", prefix + "_dma_done"),
                            ("dma_abort_req", "abort_req", prefix + "_dma_abort_req"),
                            ("dma_abort", "data_in_abort", prefix + "_dma_abort"),
                            ("axi_data_available", "data_in_available", prefix + "_s_data_available")):
            assert camera[cp] == dma[dp] == net, (prefix, cp, dp)
        report.append(f"PASS top {prefix}: completion, abort request, abort retirement, credits connected")
    (HERE / "top_audit.log").write_text("\n".join(report) + "\n", encoding="ascii")
    print("\n".join(report), flush=True)
    return hashlib.sha256(raw).hexdigest()


def run_case(name, commands, expected):
    script = "onerror {quit -code 1 -force}\n" + commands + "\nrun -all\nquit -code 0 -force\n"
    (HERE / (name + ".do")).write_text(script, encoding="ascii")
    log = HERE / (name + ".log")
    result = subprocess.run([str(SIM / "vsim.exe"), "-c", "-do", name + ".do", "-l", str(log)],
                            cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    output = log.read_bytes() if log.exists() else result.stdout
    passed = result.returncode == 0 and expected in output and not re.search(rb"\*\* (?:Error|Fatal)", output)
    lines = [line.decode("ascii", errors="replace") for line in output.splitlines() if b"PASS " in line]
    print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
    print("\n".join(lines) if passed else output[-6000:].decode("ascii", errors="replace"), flush=True)
    return passed, lines


def main():
    top_hash = audit_top()
    jobs = [("camera_startup", """vlib work_startup
vlog -work work_startup -sv +incdir+. ../../source/ov5640/ov5640/ov5640.v ../../source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v ../../source/ov5640/ov5640/i2c_dir.v ../../source/ov5640/ov5640/cmos_capture.v cdc_idle_stub.sv tb_camera_startup.sv
vsim -voptargs=+acc work_startup.tb_camera_startup""", b"PASS CAMERA STARTUP external_resets=0 release_edge=65536 cameras=4 commands_each=264")]
    recovery = """../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v ../../source/ov5640/ov5640_ddr/ov5640_ddr.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v"""
    jobs.append(("frame_recovery", f"""vlib work_frame
vlog -work work_frame -sv {recovery} ../dma_timeout_repro/fifo_models.sv ../dma_timeout_repro/tb_frame_recovery.sv
vsim -voptargs=+acc work_frame.tb_frame_recovery""", b"PASS FRAME RECOVERY success=10 abort=7 AW=61 B=61"))
    jobs.append(("credit_recovery", f"""vlib work_credit
vlog -work work_credit -sv {recovery} ../dma_timeout_repro/fifo_models.sv ../dma_timeout_repro/tb_credit_recovery.sv
vsim -voptargs=+acc work_credit.tb_credit_recovery""", b"PASS FRAME RECOVERY success=10 abort=7 AW=58 B=58"))
    vendor = (PROJECT / "sim/dma_timeout_repro/frame_recovery_vendor.do").read_bytes().decode("ascii")
    vendor = vendor.replace("work_vendor", "work_frame_vendor").replace("tb_frame_recovery.sv", "../dma_timeout_repro/tb_frame_recovery.sv")
    vendor = vendor.replace("onerror {quit -code 1 -force}\n", "").split("run -all")[0].strip()
    jobs.append(("frame_recovery_vendor", vendor, b"PASS FRAME RECOVERY success=10 abort=7 AW=1425 B=1425"))
    passed = True
    summary = []
    for name, commands, expected in jobs:
        ok, lines = run_case(name, commands, expected)
        passed &= ok
        summary += [f"{name}: {'PASS' if ok else 'FAIL'}"] + lines
    unchanged = hashlib.sha256((PROJECT / "source/top.v").read_bytes()).hexdigest() == top_hash
    passed &= unchanged
    summary += [f"top.v unchanged during run: {unchanged}", "OVERALL " + ("PASS" if passed else "FAIL")]
    (HERE / "results.log").write_text("\n".join(summary) + "\n", encoding="ascii")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
