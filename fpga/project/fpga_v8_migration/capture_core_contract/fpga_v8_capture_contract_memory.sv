`timescale 1ns/1ps
// Testbench memory extension around the UNMODIFIED vendor scheduling stub.
// The stub supplies AW/AR delays, unthrottleable W/R, accepted-AW WID and LAST.
// Its synthetic read pattern is replaced by transaction-backed 256 MiB memory.
module fpga_v8_capture_contract_memory (
    input clk, input rst_n,
    input [3:0] awid, input [27:0] awaddr, input [3:0] awlen,
    input awvalid, output awready,
    input [127:0] wdata, input [15:0] wstrb,
    output wready, output wlast, output [3:0] wid,
    input [3:0] arid, input [27:0] araddr, input [3:0] arlen,
    input arvalid, output arready,
    output [3:0] rid, output reg [127:0] rdata=0,
    output rlast, output rvalid,
    input hold_aw, input hold_w, input hold_ar, input hold_r,
    output write_active, output read_active,
    output integer writes=0, output integer reads=0
);
    wire [127:0] scheduler_pattern;
    fpga_v8_vendor_ddr_stub #(.CORE_MEMORY(0), .CAMERA_BURSTS(1)) scheduler (
        .clk(clk), .rst_n(rst_n), .awid(awid), .awaddr(awaddr), .awlen(awlen),
        .awvalid(awvalid), .awready(awready), .wdata(wdata), .wstrb(wstrb),
        .wready(wready), .wlast(wlast), .wid(wid),
        .arid(arid), .araddr(araddr), .arlen(arlen), .arvalid(arvalid), .arready(arready),
        .rid(rid), .rdata(scheduler_pattern), .rlast(rlast), .rvalid(rvalid),
        .hold_aw(hold_aw), .hold_w(hold_w), .hold_ar(hold_ar), .hold_r(hold_r),
        .hold_final_output(1'b0), .write_active(write_active), .read_active(read_active),
        .consumed_words(), .emitted_words()
    );
    // Exact physical byte addresses, sparse storage at 16-byte aligned keys.
    reg [127:0] memory [int unsigned];
    integer write_pointer, read_pointer, write_left, read_left, lane, fd;
    reg [3:0] accepted_id;
    reg [127:0] replacement;
    reg reset_seen=0;
    function automatic [127:0] get_word(input integer address);
        if(memory.exists(address)) get_word=memory[address];
        else get_word={16{8'ha5}};
    endfunction
    task automatic dump(input integer address, input integer byte_length, input string name);
        integer n, stream;
        reg [127:0] word;
        begin
            stream=$fopen(name,"wb");
            for(n=0;n<byte_length;n=n+1) begin
                word=get_word((address+n)&32'hfffffff0);
                $fwrite(stream,"%c",word[((address+n)%16)*8+:8]);
            end
            $fclose(stream);
        end
    endtask
    initial fd=$fopen("memory_trace.txt","w");
    always @(posedge clk) begin
        if(!rst_n) begin
            if(!reset_seen) $fdisplay(fd,"RESET");
            reset_seen=1;
            write_left=0; read_left=0; write_pointer=0; read_pointer=0;
        end else begin
            reset_seen=0;
            if(awvalid&&awready) begin
                if(write_left!=0) $fatal(1,"memory overlapping vendor AW");
                write_pointer=awaddr; write_left=awlen+1; accepted_id=awid;
                $fdisplay(fd,"AW %08h %0d %0d",awaddr,awid,write_left);
            end
            if(wready) begin
                if(write_left<=0||wid!==accepted_id||wlast!==(write_left==1)||
                   $isunknown({wdata,wstrb,wid,wlast})) $fatal(1,"memory W obligation/ID/X/Z");
                replacement=get_word(write_pointer);
                for(lane=0;lane<16;lane=lane+1)
                    if(wstrb[lane]) replacement[lane*8+:8]=wdata[lane*8+:8];
                memory[write_pointer]=replacement;
                $fdisplay(fd,"W %08h %0d %032h %04h %0d",write_pointer,wid,wdata,wstrb,wlast);
                writes=writes+1; write_pointer=write_pointer+16; write_left=write_left-1;
            end
            if(arvalid&&arready) begin
                if(read_left!=0) $fatal(1,"memory overlapping vendor AR");
                read_pointer=araddr; read_left=arlen+1;
                $fdisplay(fd,"AR %08h %0d %0d",araddr,arid,read_left);
            end
        end
    end
    // Stub registers R at posedge; memory resolves that emitted address before
    // the adapter samples it at the NEXT posedge. No forced DUT internals.
    always @(negedge clk) begin
        if(!rst_n) rdata=0;
        else if(rvalid) begin
            if(read_left<=0||rlast!==(read_left==1)) $fatal(1,"memory R obligation/last");
            rdata=get_word(read_pointer);
            if($isunknown(rdata)) $fatal(1,"unknown physical memory R word");
            $fdisplay(fd,"R %08h %0d %032h %0d",read_pointer,rid,rdata,rlast);
            read_pointer=read_pointer+16; read_left=read_left-1; reads=reads+1;
        end
    end
endmodule
