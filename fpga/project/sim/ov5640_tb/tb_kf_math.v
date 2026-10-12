`timescale 1ns/1ps
module tb_kf_math;
    reg  [5:0] thr0, thr1, thr2;
    reg  [15:0] calc_z, prev_rdata;
    wire [5:0]  zr, zg, zb, xr, xg, xb;
    reg  [5:0]  rr, gg, bb, dr, dg, db;

    assign zr = {1'b0, calc_z[15:11]};
    assign zg = {1'b0, calc_z[10:5]};
    assign zb = {1'b0, calc_z[4:0]};
    assign xr = {1'b0, prev_rdata[15:11]};
    assign xg = {1'b0, prev_rdata[10:5]};
    assign xb = {1'b0, prev_rdata[4:0]};

    always @* begin
        dr = (zr >= xr) ? (zr - xr) : (xr - zr);
        dg = (zg >= xg) ? (zg - xg) : (xg - zg);
        db = (zb >= xb) ? (zb - xb) : (xb - zb);
        if      (dr < thr0) rr = (3*xr + zr) >> 2;
        else if (dr < thr1) rr = (xr + zr)   >> 1;
        else if (dr < thr2) rr = (xr + 3*zr) >> 2;
        else                rr = zr;
        if      (dg < thr0) gg = (3*xg + zg) >> 2;
        else if (dg < thr1) gg = (xg + zg)   >> 1;
        else if (dg < thr2) gg = (xg + 3*zg) >> 2;
        else                gg = zg;
        if      (db < thr0) bb = (3*xb + zb) >> 2;
        else if (db < thr1) bb = (xb + zb)   >> 1;
        else if (db < thr2) bb = (xb + 3*zb) >> 2;
        else                bb = zb;
    end

    wire [15:0] kf_out = { rr[4:0], gg[5:0], bb[4:0] };

    initial begin
        thr0 = 6'd3; thr1 = 6'd8; thr2 = 6'd20;
        calc_z = 16'hE5C0; prev_rdata = 16'hC518;
        #1;
        $display("z=%04X x=%04X zr=%0d zg=%0d zb=%0d xr=%0d xg=%0d xb=%0d",
                 calc_z, prev_rdata, zr, zg, zb, xr, xg, xb);
        $display("dr=%0d dg=%0d db=%0d", dr, dg, db);
        $display("rr=%0d gg=%0d bb=%0d out=%04X", rr, gg, bb, kf_out);
        $finish;
    end
endmodule
