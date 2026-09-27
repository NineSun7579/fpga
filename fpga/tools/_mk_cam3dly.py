# -*- coding: utf-8 -*-
"""Byte-level edit: per-camera runtime DVP sampling delay (IODELAY step).

Adds:
  ov5640_reg.v : DLY_STEP_DEF param, dly_step out reg, REG_DLY_STEP write (0x30),
                 reset to 40.
  ov5640_top.v : reg_dly_step wire, GTP_IODELAY_E2 -> DELAY_STEP_SEL("PORT"),
                 DELAY_STEP(reg_dly_step), .dly_step on the ov5640_reg instance.

Default value 40 == the current IODELAY_STEP for all three cameras, so behaviour
is unchanged until a register write sweeps the delay.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project\source\ov5640"
REG = os.path.join(ROOT, "ov5640_reg.v")
TOP = os.path.join(ROOT, "ov5640_top.v")
BAK = ".bak_cam3dly_20260927"


def edit(path, pairs):
    data = open(path, "rb").read()
    for old, new, cnt in pairs:
        ob, nb = old.encode("latin1"), new.encode("latin1")
        n = data.count(ob)
        assert n == cnt, "count %d != %d for %r in %s" % (n, cnt, old[:70], path)
        data = data.replace(ob, nb)
    open(path, "wb").write(data)
    print("edited", os.path.basename(path))


# ---- backups ----
for p in (REG, TOP):
    if not os.path.exists(p + BAK):
        open(p + BAK, "wb").write(open(p, "rb").read())
        print("backup ->", os.path.basename(p) + BAK)

# ---- ov5640_reg.v ----
reg_pairs = [
    (
        "    parameter        CAM_EN_DEF     = 1'b1,\n",
        "    parameter        CAM_EN_DEF     = 1'b1,\n"
        "    parameter [7:0]  DLY_STEP_DEF   = 8'd40,\n",
        1,
    ),
    (
        "    output reg                        cam_en                        ,\n",
        "    output reg                        cam_en                        ,\n"
        "    output reg [7:0]                  dly_step                      ,\n",
        1,
    ),
    (
        "localparam REG_CAM_EN    = BASE_ADDR + 32'h40;\n",
        "localparam REG_CAM_EN    = BASE_ADDR + 32'h40;\n"
        "// [CAM3DLY 2026-09-27] per-camera DVP sampling delay step (port mode).\n"
        "// Write-only here: offset 0x30 still READS the CAM_WORDS debug counter, so a\n"
        "// write to it was previously a no-op.  Lets the phase be swept on-board.\n"
        "localparam REG_DLY_STEP  = BASE_ADDR + 32'h30;\n",
        1,
    ),
    (
        "            cam_en <= s_axi_wdata[0];\n        end\n    end\n",
        "            cam_en <= s_axi_wdata[0];\n        end\n    end\n"
        "\n"
        "    // [CAM3DLY 2026-09-27] runtime DVP sampling delay for this camera.\n"
        "    always @(posedge clk) begin\n"
        "        if(rst)begin\n"
        "            dly_step <= DLY_STEP_DEF;\n"
        "        end\n"
        "        else if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) && (s_axi_awaddr == REG_DLY_STEP))begin\n"
        "            dly_step <= s_axi_wdata[7:0];\n"
        "        end\n"
        "    end\n",
        1,
    ),
]
edit(REG, reg_pairs)

# ---- ov5640_top.v ----
top_pairs = [
    (
        "    wire [7 : 0] cam_data_dly;\n",
        "    wire [7 : 0] cam_data_dly;\n"
        "    // [CAM3DLY 2026-09-27] runtime DVP sampling delay (from ov5640_reg).\n"
        "    wire [7 : 0] reg_dly_step;\n",
        1,
    ),
    ('        .DELAY_STEP_SEL("PARAMETER"),', '        .DELAY_STEP_SEL("PORT"),', 3),
    ("        .DELAY_STEP (8'b0)", "        .DELAY_STEP (reg_dly_step)", 3),
    (
        "        .cam_en                (cam_en       ),\n",
        "        .cam_en                (cam_en       ),\n"
        "        .dly_step              (reg_dly_step ),\n",
        1,
    ),
]
edit(TOP, top_pairs)
print("OK")
