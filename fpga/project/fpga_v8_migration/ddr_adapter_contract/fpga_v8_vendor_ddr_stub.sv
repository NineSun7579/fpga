`timescale 1ns/1ps
// Behavioral vendor consumer: W has no VALID, R has no READY.
// This is an independent scheduled controller stub, not the DDR3 vendor IP.
module fpga_v8_vendor_ddr_stub #(
    parameter integer SRC_BUS=32, OUT_BYTES=60, OUT_BUS=64, CAMERA_BURSTS=24,
    parameter integer CORE_MEMORY=0
) (
    input wire clk, rst_n,
    input wire [3:0] awid, input wire [27:0] awaddr, input wire [3:0] awlen,
    input wire awvalid, output reg awready=0,
    input wire [127:0] wdata, input wire [15:0] wstrb,
    output reg wready=0, output wire wlast, output wire [3:0] wid,
    input wire [3:0] arid, input wire [27:0] araddr, input wire [3:0] arlen,
    input wire arvalid, output reg arready=0,
    output reg [3:0] rid=0, output reg [127:0] rdata=0,
    output reg rlast=0, output reg rvalid=0,
    input wire hold_aw, hold_ar, hold_w, hold_r, hold_final_output,
    output reg write_active=0, read_active=0,
    output integer consumed_words=0, emitted_words=0
);
    reg [31:0] rng=32'h392a8465;
    reg [27:0] write_addr, read_addr;
    reg [3:0] write_id, read_id;
    integer write_beats, write_beat, read_beats, read_beat, cycles=0;
    reg [7:0] source_mem[0:SRC_BUS-1], golden_mem[0:OUT_BYTES-1];
    reg [7:0] output0[0:OUT_BUS+15], output1[0:OUT_BUS+15];
    reg [7:0] camera_mem[0:6*CAMERA_BURSTS*256-1];
    integer fd, k, owner, tx, offset, lane;
    assign wid=write_id;
    assign wlast=wready && write_beat+1==write_beats;
    function [127:0] pattern(input [27:0] address);
        integer n;
        for(n=0;n<16;n=n+1) pattern[n*8+:8]=((address>>4)*13+n*17+31)&255;
    endfunction
    function [7:0] camera_byte(input integer o,t,b,l);
        camera_byte=(o*37+t*19+b*11+l*7)&255;
    endfunction
    task load_source(input integer seq);
        string name;
        begin
            name=$sformatf("source_%0d.hex",seq); $readmemh(name,source_mem);
            name=$sformatf("golden_%0d.hex",seq); $readmemh(name,golden_mem);
        end
    endtask
    task audit_memory;
        integer o,t,b,l,n,beats,stream;
        begin
            stream=$fopen("vendor_output.bin","wb");
            for(n=0;n<OUT_BYTES;n=n+1) begin
                if(output0[n]!==golden_mem[n]) $fatal(1,"vendor full output mismatch byte %0d",n);
                $fwrite(stream,"%c",output0[n]);
            end
            $fclose(stream);
            stream=$fopen("vendor_output1.bin","wb");
            for(n=0;n<OUT_BYTES;n=n+1) $fwrite(stream,"%c",output1[n]);
            $fclose(stream);
            for(n=OUT_BYTES;n<OUT_BUS+16;n=n+1)
                if(output0[n]!==8'ha5 || output1[n]!==8'ha5) $fatal(1,"vendor output guard changed");
            stream=$fopen("vendor_camera.bin","wb");
            for(o=0;o<6;o=o+1)
                for(t=0;t<CAMERA_BURSTS;t=t+1) begin
                    case(t%4) 0:beats=16;1:beats=3;2:beats=5;default:beats=1;endcase
                    for(b=0;b<16;b=b+1)
                        for(l=0;l<16;l=l+1) begin
                            n=(o*CAMERA_BURSTS+t)*256+b*16+l;
                            if(camera_mem[n]!==((b<beats)?camera_byte(o,t,b,l):8'ha5))
                                $fatal(1,"vendor camera/guard mismatch %0d",n);
                            $fwrite(stream,"%c",camera_mem[n]);
                        end
                end
            $fclose(stream);
        end
    endtask
    initial fd=$fopen("vendor_trace.txt","w");
    always @(posedge clk) begin
        if(!rst_n) begin
            rng<=32'h392a8465; awready<=0; arready<=0; wready<=0; rvalid<=0;
            write_active<=0; read_active<=0; rlast<=0; rid<=0; rdata<=0;
            consumed_words<=0; emitted_words<=0; write_beat<=0; read_beat<=0;
            for(k=0;k<OUT_BUS+16;k=k+1) begin output0[k]=8'ha5; output1[k]=8'ha5; end
            for(k=0;k<6*CAMERA_BURSTS*256;k=k+1) camera_mem[k]=8'ha5;
            $fwrite(fd,"RESET\n");
        end else begin
            cycles<=cycles+1; rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            awready<=!hold_aw && !write_active && rng[4];
            arready<=!hold_ar && !read_active && !rvalid && rng[8];
            wready<=write_active && !hold_w && rng[11] &&
                !(hold_final_output && write_addr==28'h8000000+OUT_BUS-16);
            rvalid<=0; rlast<=0;
            if(awvalid && awready) begin
                if(write_active) $fatal(1,"vendor overlapping AW");
                write_active<=1; write_addr<=awaddr; write_id<=awid;
                write_beats<=awlen+1; write_beat<=0; awready<=0;
                $fwrite(fd,"AW %07x %0d %0d\n",awaddr,awid,awlen+1);
            end
            if(wready) begin
                if(!write_active || $isunknown({wdata,wstrb,wid,wlast})) $fatal(1,"vendor ghost W");
                consumed_words<=consumed_words+1;
                $fwrite(fd,"W %07x %0d %032x %04x %0d\n",write_addr+write_beat*16,wid,wdata,wstrb,wlast);
                if(CORE_MEMORY) begin
                    if(write_addr>=28'h1000000 && write_addr<28'h1600000) begin
                        owner=(write_addr-28'h1000000)/28'h0100000;
                        tx=(write_addr-(28'h1000000+owner*28'h0100000))/256;
                        if(wstrb!==16'hffff || tx>=CAMERA_BURSTS) $fatal(1,"vendor camera address/strobe");
                        for(lane=0;lane<16;lane=lane+1) begin
                            if(wdata[lane*8+:8]!==camera_byte(owner,tx,write_beat,lane)) $fatal(1,"vendor camera complete word");
                            camera_mem[(owner*CAMERA_BURSTS+tx)*256+write_beat*16+lane]<=wdata[lane*8+:8];
                        end
                    end else begin
                        offset=write_addr+write_beat*16-((write_addr>=28'h8200000)?28'h8200000:28'h8000000);
                        if(offset<0 || offset>=OUT_BUS) $fatal(1,"vendor output physical address");
                        if(wstrb!==((OUT_BYTES-offset>=16)?16'hffff:((1<<(OUT_BYTES-offset))-1))) $fatal(1,"vendor partial WSTRB");
                        for(lane=0;lane<16;lane=lane+1) if(wstrb[lane]) begin
                            if(wdata[lane*8+:8]!==golden_mem[offset+lane]) $fatal(1,"vendor RGB output byte %0d",offset+lane);
                            if(write_addr>=28'h8200000) output1[offset+lane]<=wdata[lane*8+:8];
                            else output0[offset+lane]<=wdata[lane*8+:8];
                        end
                    end
                end
                write_beat<=write_beat+1;
                if(wlast) begin write_active<=0; wready<=0; end
            end
            if(arvalid && arready) begin
                if(read_active || rvalid) $fatal(1,"vendor overlapping AR");
                read_active<=1; read_addr<=araddr; read_id<=arid;
                read_beats<=arlen+1; read_beat<=0; arready<=0;
                $fwrite(fd,"AR %07x %0d %0d\n",araddr,arid,arlen+1);
            end
            if(read_active && !hold_r && (rng[14] || rng[15])) begin
                rid<=read_id; rlast<=read_beat+1==read_beats; rvalid<=1;
                if(CORE_MEMORY) begin
                    if(read_addr+read_beat*16<28'h0100000 || read_addr+read_beat*16+16>28'h0100000+SRC_BUS) $fatal(1,"vendor source read bounds");
                    for(lane=0;lane<16;lane=lane+1) rdata[lane*8+:8]<=source_mem[read_addr+read_beat*16-28'h0100000+lane];
                end else rdata<=pattern(read_addr+read_beat*16);
                read_beat<=read_beat+1; emitted_words<=emitted_words+1;
                if(read_beat+1==read_beats) read_active<=0;
            end
        end
    end
endmodule
