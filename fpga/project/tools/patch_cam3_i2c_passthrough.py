#!/usr/bin/env python3
"""Byte-level patch: host-writable SCCB (I2C) passthrough for the OV5640 cameras.

Files (all GBK, must stay byte-preserving outside the patched spots):
  source/ov5640/ov5640/ov5640.v      - PT FSM on dri_clk + i2c master mux
  source/ov5640/ov5640_top.v         - PT wiring + result CDC back to video_clk
  source/ov5640/ov5640_reg.v         - PT command/status/readback AXI registers

New AXI-Lite registers (16-byte aligned, CAM segment page):
  BASE + 0x100  REG_I2C_CMD   W   {bit24 rw(0=wr,1=rd), [23:8] reg addr, [7:0] data}
  BASE + 0x110  REG_I2C_RD    R   {24'b0, rdata[7:0]}
  BASE + 0x120  REG_I2C_STAT  R   {30'b0, done_latched, ack(1=NACK)}

For cam3 BASE=0x2000_0400 these are 0x2000_0500/0x0510/0x0520, which the M01
decoder routes to m3 (page addr[11:10]==01) and the crossbar/PCIe both reach.
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_bytes()


def write(name, data):
    (ROOT / name).write_bytes(data)


def eol_of(data):
    return b"\r\n" if b"\r\n" in data else b"\n"


def sub_once(data, old, new, label):
    n = data.count(old)
    if n != 1:
        raise SystemExit("ANCHOR FAIL [%s]: expected 1 match, found %d" % (label, n))
    return data.replace(old, new, 1)


def patch_v():
    name = "source/ov5640/ov5640/ov5640.v"
    data = read(name)
    eol = eol_of(data)
    shutil.copyfile(ROOT / name, ROOT / (name + ".bak_pt_20260926"))

    # 1) add PT ports at the end of the port list
    old = b"    output reg [31:0]         dbg_vsync_raw          //raw cam_vsync rising edges (cam_pclk domain)"
    new = b"    output reg [31:0]         dbg_vsync_raw          ,//raw cam_vsync rising edges (cam_pclk domain)" + eol + eol + (
        b"    // [PT 2026-09-26] host SCCB passthrough (handshake on dri_clk)" + eol
        + b"    input                     pt_req_toggle         ," + eol
        + b"    input                     pt_rw                 ," + eol
        + b"    input  [15:0]             pt_addr               ," + eol
        + b"    input  [ 7:0]             pt_wdata              ," + eol
        + b"    output [ 7:0]             pt_rdata              ," + eol
        + b"    output                    pt_ack                ," + eol
        + b"    output                    pt_done_toggle"
    )
    data = sub_once(data, old, new, "ov5640 ports")

    # 2) cfg-FSM outputs become cfg_*; i2c_* are now mux outputs
    old = b"wire            i2c_rh_wl;"
    new = (old + eol
           + b"wire            cfg_exec;" + eol
           + b"wire   [23:0]   cfg_data;" + eol
           + b"wire            cfg_rh_wl;")
    data = sub_once(data, old, new, "ov5640 cfg wires")

    data = sub_once(data, b"    .i2c_exec     (i2c_exec),",
                    b"    .i2c_exec     (cfg_exec),", "ov5640 cfg .i2c_exec")
    data = sub_once(data, b"    .i2c_data     (i2c_data),",
                    b"    .i2c_data     (cfg_data),", "ov5640 cfg .i2c_data")
    data = sub_once(data, b"    .i2c_rh_wl    (i2c_rh_wl),",
                    b"    .i2c_rh_wl    (cfg_rh_wl),", "ov5640 cfg .i2c_rh_wl")

    # 3) dbg ID capture: sample read/write at transaction start
    old = (b"// [DBG] SCCB health: latch first two read bytes (OV5640 ID 0x56,0x40) + NACK op count"
           + eol + b"reg [3:0] dbg_rd_cnt;")
    new = (b"// [DBG] SCCB health: latch first two read bytes (OV5640 ID 0x56,0x40) + NACK op count" + eol
           + b"// [PT 2026-09-26] latch read/write at transaction start: i2c_rh_wl flips to 0" + eol
           + b"// at init_reg_cnt==2 during the 2nd read, so sampling it at i2c_done missed ID_L." + eol
           + b"reg i2c_was_read;" + eol
           + b"always @(posedge dri_clk or negedge rst_n) begin" + eol
           + b"    if(!rst_n)        i2c_was_read <= 1'b0;" + eol
           + b"    else if(i2c_exec) i2c_was_read <= i2c_rh_wl;" + eol
           + b"end" + eol
           + b"reg [3:0] dbg_rd_cnt;")
    data = sub_once(data, old, new, "ov5640 dbg latch")

    data = sub_once(data, b"        if(i2c_rh_wl && (dbg_rd_cnt < 4'd2)) begin",
                    b"        if(i2c_was_read && (dbg_rd_cnt < 4'd2)) begin", "ov5640 dbg cond")

    # 4) PT FSM + master mux, after the i2c/sys debug block
    anchor = b"                                            1'b0, cam_rst_n};"
    block = eol + (
        b"// [PT 2026-09-26] host SCCB passthrough FSM (dri_clk domain). After sensor" + eol
        + b"// init completes, a host command issues exactly one transaction on the shared" + eol
        + b"// master; cfg_* is the autonomous init table. Results are handed back with a" + eol
        + b"// done-toggle (data held stable; CDC to video_clk lives in ov5640_top)." + eol
        + b"reg         pt_req_s1, pt_req_s2, pt_req_s3;" + eol
        + b"always @(posedge dri_clk or negedge rst_n) begin" + eol
        + b"    if(!rst_n) {pt_req_s1, pt_req_s2, pt_req_s3} <= 3'b0;" + eol
        + b"    else       {pt_req_s1, pt_req_s2, pt_req_s3} <= {pt_req_toggle, pt_req_s1, pt_req_s2};" + eol
        + b"end" + eol
        + b"wire pt_req_pulse = pt_req_s2 ^ pt_req_s3;" + eol
        + eol
        + b"reg  pt_pending;" + eol
        + b"reg  pt_busy;" + eol
        + b"wire pt_take = pt_pending & cam_init_done & ~pt_busy;" + eol
        + b"always @(posedge dri_clk or negedge rst_n) begin" + eol
        + b"    if(!rst_n)          pt_pending <= 1'b0;" + eol
        + b"    else if(pt_req_pulse) pt_pending <= 1'b1;" + eol
        + b"    else if(pt_take)      pt_pending <= 1'b0;" + eol
        + b"end" + eol
        + b"always @(posedge dri_clk or negedge rst_n) begin" + eol
        + b"    if(!rst_n)        pt_busy <= 1'b0;" + eol
        + b"    else if(pt_take)  pt_busy <= 1'b1;" + eol
        + b"    else if(i2c_done) pt_busy <= 1'b0;" + eol
        + b"end" + eol
        + eol
        + b"assign i2c_exec  = cfg_exec | pt_take;" + eol
        + b"assign i2c_data  = pt_take ? {pt_addr, pt_wdata} : cfg_data;" + eol
        + b"assign i2c_rh_wl = pt_take ? pt_rw : cfg_rh_wl;" + eol
        + eol
        + b"reg [7:0] pt_rdata_r;" + eol
        + b"reg       pt_ack_r;" + eol
        + b"reg       pt_done_toggle_r;" + eol
        + b"always @(posedge dri_clk or negedge rst_n) begin" + eol
        + b"    if(!rst_n) begin" + eol
        + b"        pt_rdata_r       <= 8'd0;" + eol
        + b"        pt_ack_r         <= 1'b0;" + eol
        + b"        pt_done_toggle_r <= 1'b0;" + eol
        + b"    end" + eol
        + b"    else if(i2c_done && pt_busy) begin" + eol
        + b"        pt_rdata_r       <= i2c_data_r;" + eol
        + b"        pt_ack_r         <= i2c_ack;" + eol
        + b"        pt_done_toggle_r <= ~pt_done_toggle_r;" + eol
        + b"    end" + eol
        + b"end" + eol
        + b"assign pt_rdata       = pt_rdata_r;" + eol
        + b"assign pt_ack         = pt_ack_r;" + eol
        + b"assign pt_done_toggle = pt_done_toggle_r;"
    )
    data = sub_once(data, anchor, anchor + block, "ov5640 pt fsm")
    write(name, data)
    print("patched", name)


def patch_top():
    name = "source/ov5640/ov5640_top.v"
    data = read(name)
    eol = eol_of(data)
    shutil.copyfile(ROOT / name, ROOT / (name + ".bak_pt_20260926"))

    block = (
        b"    // [PT 2026-09-26] host SCCB passthrough: video_clk (ov5640_reg) <-> dri_clk" + eol
        + b"    // (ov5640/i2c_dri). Command path is data+toggle (stable data; the toggle is" + eol
        + b"    // synchronized in dri_clk inside ov5640). Result path is 2-FF synced here." + eol
        + b"    wire        pt_req_toggle;" + eol
        + b"    wire        pt_rw;" + eol
        + b"    wire [15:0] pt_addr;" + eol
        + b"    wire [ 7:0] pt_wdata;" + eol
        + b"    wire [ 7:0] pt_rdata;" + eol
        + b"    wire        pt_ack;" + eol
        + b"    wire        pt_done_toggle;" + eol
        + b"    reg         pt_done_s1, pt_done_s2;" + eol
        + b"    reg  [7:0]  pt_rdata_s1, pt_rdata_s2;" + eol
        + b"    reg         pt_ack_s1, pt_ack_s2;" + eol
        + b"    always @(posedge video_clk) begin" + eol
        + b"        if(video_rst) begin" + eol
        + b"            pt_done_s1  <= 1'b0;" + eol
        + b"            pt_done_s2  <= 1'b0;" + eol
        + b"            pt_rdata_s1 <= 8'd0;" + eol
        + b"            pt_rdata_s2 <= 8'd0;" + eol
        + b"            pt_ack_s1   <= 1'b0;" + eol
        + b"            pt_ack_s2   <= 1'b0;" + eol
        + b"        end" + eol
        + b"        else begin" + eol
        + b"            pt_done_s1  <= pt_done_toggle;" + eol
        + b"            pt_done_s2  <= pt_done_s1;" + eol
        + b"            pt_rdata_s1 <= pt_rdata;" + eol
        + b"            pt_rdata_s2 <= pt_rdata_s1;" + eol
        + b"            pt_ack_s1   <= pt_ack;" + eol
        + b"            pt_ack_s2   <= pt_ack_s1;" + eol
        + b"        end" + eol
        + b"    end" + eol
        + eol
        + b"    ov5640 #("
    )
    data = sub_once(data, b"    ov5640 #(", block, "ov5640_top pt cdc")

    old = b"        .dbg_vsync_raw      (dbg_vsync_raw )"
    new = (b"        .dbg_vsync_raw      (dbg_vsync_raw )," + eol + eol
           + b"        // [PT 2026-09-26] host SCCB passthrough" + eol
           + b"        .pt_req_toggle      (pt_req_toggle)," + eol
           + b"        .pt_rw              (pt_rw        )," + eol
           + b"        .pt_addr            (pt_addr      )," + eol
           + b"        .pt_wdata           (pt_wdata     )," + eol
           + b"        .pt_rdata           (pt_rdata     )," + eol
           + b"        .pt_ack             (pt_ack       )," + eol
           + b"        .pt_done_toggle     (pt_done_toggle)" + eol)
    data = sub_once(data, old, new, "ov5640_top ov5640 pt ports")

    old = b"        .dbg_clk_status        (dbg_clk_status)" + eol + b"    );"
    new = (b"        .dbg_clk_status        (dbg_clk_status)," + eol + eol
           + b"        // [PT 2026-09-26] host SCCB passthrough" + eol
           + b"        .pt_req_toggle         (pt_req_toggle )," + eol
           + b"        .pt_addr               (pt_addr       )," + eol
           + b"        .pt_wdata              (pt_wdata      )," + eol
           + b"        .pt_rw                 (pt_rw         )," + eol
           + b"        .pt_rdata              (pt_rdata_s2   )," + eol
           + b"        .pt_ack                (pt_ack_s2     )," + eol
           + b"        .pt_done_toggle        (pt_done_s2    )" + eol
           + b"    );")
    data = sub_once(data, old, new, "ov5640_top reg pt ports")

    write(name, data)
    print("patched", name)


def patch_reg():
    name = "source/ov5640/ov5640_reg.v"
    data = read(name)
    eol = eol_of(data)
    shutil.copyfile(ROOT / name, ROOT / (name + ".bak_pt_20260926"))

    old = b"    input  [31:0]                     dbg_clk_status" + eol + b");"
    new = (b"    input  [31:0]                     dbg_clk_status," + eol + eol
           + b"    // [PT 2026-09-26] host SCCB passthrough (video_clk domain; CDC in ov5640_top)" + eol
           + b"    output reg                        pt_req_toggle," + eol
           + b"    output reg  [15:0]                pt_addr," + eol
           + b"    output reg  [ 7:0]                pt_wdata," + eol
           + b"    output reg                        pt_rw," + eol
           + b"    input       [ 7:0]                pt_rdata," + eol
           + b"    input                             pt_ack," + eol
           + b"    input                             pt_done_toggle" + eol
           + b");")
    data = sub_once(data, old, new, "ov5640_reg ports")

    old = b"localparam REG_DBG_ZOUT      = BASE_ADDR + 32'h90;"
    new = (old + eol
           + b"// [PT 2026-09-26] host SCCB passthrough (cam3 page: BASE+0x100..0x12F)" + eol
           + b"localparam REG_I2C_CMD  = BASE_ADDR + 32'h100;" + eol
           + b"localparam REG_I2C_RD   = BASE_ADDR + 32'h110;" + eol
           + b"localparam REG_I2C_STAT = BASE_ADDR + 32'h120;")
    data = sub_once(data, old, new, "ov5640_reg localparams")

    old = (b"            cam_addr_2 <= s_axi_wdata;" + eol
           + b"        end" + eol
           + b"    end")
    new = (old + eol + eol
           + b"    // [PT 2026-09-26] host SCCB passthrough command + result latch." + eol
           + b"    //   Any write to REG_I2C_CMD issues one SCCB transaction (after sensor" + eol
           + b"    //   init). done/ack/rdata are latched back for polling reads." + eol
           + b"    reg        pt_done_lat;" + eol
           + b"    reg [ 7:0] pt_rdata_lat;" + eol
           + b"    reg        pt_ack_lat;" + eol
           + b"    reg        pt_done_d;" + eol
           + b"    always @(posedge clk) begin" + eol
           + b"        if(rst) begin" + eol
           + b"            pt_addr       <= 16'd0;" + eol
           + b"            pt_wdata      <= 8'd0;" + eol
           + b"            pt_rw         <= 1'b0;" + eol
           + b"            pt_req_toggle <= 1'b0;" + eol
           + b"            pt_done_lat   <= 1'b0;" + eol
           + b"            pt_rdata_lat  <= 8'd0;" + eol
           + b"            pt_ack_lat    <= 1'b0;" + eol
           + b"            pt_done_d     <= 1'b0;" + eol
           + b"        end" + eol
           + b"        else begin" + eol
           + b"            pt_done_d <= pt_done_toggle;" + eol
           + b"            if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) &&" + eol
           + b"               (s_axi_awaddr == REG_I2C_CMD)) begin" + eol
           + b"                pt_addr       <= s_axi_wdata[23:8];" + eol
           + b"                pt_wdata      <= s_axi_wdata[7:0];" + eol
           + b"                pt_rw         <= s_axi_wdata[24];" + eol
           + b"                pt_req_toggle <= ~pt_req_toggle;" + eol
           + b"                pt_done_lat   <= 1'b0;" + eol
           + b"            end" + eol
           + b"            if(pt_done_toggle ^ pt_done_d) begin" + eol
           + b"                pt_rdata_lat <= pt_rdata;" + eol
           + b"                pt_ack_lat   <= pt_ack;" + eol
           + b"                pt_done_lat  <= 1'b1;" + eol
           + b"            end" + eol
           + b"        end" + eol
           + b"    end")
    data = sub_once(data, old, new, "ov5640_reg pt logic")

    old = b"                    REG_DBG_AXI_NOW:   rdata <= dbg_sys_status;"
    new = (old + eol
           + b"                    REG_I2C_RD:        rdata <= {{(AXI_ADDR_WIDTH-8){1'b0}}, pt_rdata_lat};" + eol
           + b"                    REG_I2C_STAT:      rdata <= {{(AXI_ADDR_WIDTH-2){1'b0}}, pt_done_lat, pt_ack_lat};")
    data = sub_once(data, old, new, "ov5640_reg read case")

    write(name, data)
    print("patched", name)


if __name__ == "__main__":
    patch_v()
    patch_top()
    patch_reg()
    print("ALL PATCHES APPLIED")
