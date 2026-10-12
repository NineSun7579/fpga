"""Extend the endpoint agent's native-memory TB through the real delivery MMIO adapter."""
from make_integrated import ROOT
from integrate_display import MEM


def testbench(mmio):
    raw = (ROOT / 'display_scaler/tb_thumbnail_ddr.sv').read_text()
    raw = raw.replace('module tb_thumbnail_ddr;', 'module tb_thumbnail_integrated;')
    raw = raw.replace("localparam SRC=32'h1000, DST=32'h200000;",
                      "localparam SRC=32'h01800000, DST=32'h0a200000;")
    start = raw.index('    display_thumbnail_ddr #(')
    end = raw.index('    // Physical byte arrays', start)
    declarations = '    wire capture_hold;\n'
    for width, name, direction in mmio:
        declarations += f'    {"reg" if direction == "input" else "wire"} {f"[{width-1}:0] " if width > 1 else ""}host_{name};\n'
    declarations += '''    wire rgb_transactions=dut.rgb_arvalid || dut.rgb_awvalid || dut.rgb_wvalid;
    assign cmd_ready=dut.cmd_ready;
    assign busy=dut.busy;
    assign done=dut.done;
    assign error=dut.error;
    assign config_error=dut.config_error;
    delivery_top_adapter #(.WIDTH(W),.HEIGHT(H),.OUT_HEIGHT(H),.TOP_ROWS(0)) dut (
        .clk(clk),.rst(!rst_n),.capture_hold(capture_hold),
        .camera_state(32'd1),.camera_prev_base(SRC),.camera_published(2'b01),
        .camera_cmd_valid(1'b0),.camera_awvalid(1'b0),.camera_wvalid(1'b0),.camera_abort(1'b0),
'''
    ports = [f'.s_axi_{name}(host_{name})' for _, name, _ in mmio]
    ports += [f'.m_axi_{name}({name})' for _, name, _ in MEM]
    declarations += '        ' + ',\n        '.join(ports) + '\n    );\n'
    declarations += '''    reg [31:0] value;
    reg [1:0] expected_bresp=0;
    task mmio_write(input [31:0] offset,input [31:0] data);
        begin
            @(negedge clk); host_awaddr=32'h40020000+offset; host_awvalid=1;
            host_wdata=data; host_wvalid=0;
            do @(posedge clk); while(!host_awready);
            @(negedge clk); host_awvalid=0; host_wvalid=1;
            do @(posedge clk); while(!host_wready);
            @(negedge clk); host_wvalid=0;
            wait(host_bvalid); if(host_bresp!=expected_bresp) $fatal(1,"FAIL integrated MMIO write");
            @(negedge clk); host_bready=1; @(negedge clk); host_bready=0;
        end
    endtask
    task mmio_read(input [31:0] offset,output [31:0] data);
        begin
            @(negedge clk); host_araddr=32'h40020000+offset; host_arvalid=1;
            do @(posedge clk); while(!host_arready);
            @(negedge clk); host_arvalid=0;
            wait(host_rvalid); if(host_rresp!=0 || !host_rlast) $fatal(1,"FAIL integrated MMIO read");
            data=host_rdata[31:0];
            @(negedge clk); host_rready=1; @(negedge clk); host_rready=0;
        end
    endtask
    always @(posedge clk) if(rst_n && dut.selected_mode && rgb_transactions)
        $fatal(1,"FAIL inactive RGB core issued request");
'''
    raw = raw[:start] + declarations + raw[end:]
    raw = raw.replace('dut.pixels_taken', 'dut.thumb_core.pixels_taken')
    raw = raw.replace('dut.final_b_seen', 'dut.thumb_core.final_b_seen')
    start = raw.index('    task command;')
    end = raw.index('    initial begin', start)
    raw = raw[:start] + '''    task command;
        begin
            mmio_write(32'hb0,1);
            mmio_read(32'hb0,value); if(value!=1) $fatal(1,"FAIL selected mode");
            mmio_read(32'h40,value); if(value!=DST) $fatal(1,"FAIL selected destination");
            mmio_read(32'h60,value); if(value!=N) $fatal(1,"FAIL selected byte count");
            mmio_write(32'h20,1);
            value=0;
            while(!value[1]) mmio_read(32'h10,value);
            expected_bresp=2; mmio_write(32'hb0,0); // held lease forbids mode switch
            expected_bresp=0; mmio_write(32'h20,3);
            if(!busy) $fatal(1,"FAIL command did not start thumbnail");
            expected_bresp=2;
            mmio_write(32'hb0,0); // busy must keep current AXI owner
            mmio_write(32'h20,0); // no release while core owns frame
            mmio_write(32'h40,32'h0a000000); // no destination change in flight
            expected_bresp=0;
            mmio_read(32'hb0,value); if(value!=1) $fatal(1,"FAIL busy changed owner");
        end
    endtask
''' + raw[end:]
    start = raw.index('        invalid_command(')
    end = raw.index('        command();', start)
    raw = raw[:start] + raw[end:]
    raw = raw.replace('            inject=0; reset_all(); command(); wait(done); @(negedge clk);', '''
            expected_bresp=2;
            mmio_write(32'h20,0); mmio_write(32'hb0,0); // quarantine retains lease/owner
            expected_bresp=0;
            inject=0; reset_all(); command(); wait(done); @(negedge clk);''')
    raw = raw.replace('        fd=$fopen("dest_physical.hex","w");', '''
        mmio_read(32'h10,value); if(!value[3] || value[4:0]!=5'b01011)
            $fatal(1,"FAIL successful status");
        mmio_write(32'h20,0);
        mmio_write(32'hb0,0);
        mmio_read(32'hb0,value); if(value!=0) $fatal(1,"FAIL RGB restore mode");
        mmio_read(32'h40,value); if(value!=32'h0a000000) $fatal(1,"FAIL RGB restore dest");
        mmio_read(32'h60,value); if(value!=W*H*3) $fatal(1,"FAIL RGB restore byte count");
        mmio_read(32'h10,value); if(value[4:0]!=0) $fatal(1,"FAIL stale completion after switch");
        fd=$fopen("dest_physical.hex","w");''')
    initial = '\n    initial begin\n'
    for _, name, direction in mmio:
        if direction == 'input':
            value = {'awsize': 4, 'arsize': 4, 'awburst': 1, 'arburst': 1,
                     'wstrb': 65535, 'wlast': 1}.get(name, 0)
            initial += f'        host_{name}={value};\n'
    initial += '    end\n'
    return raw.replace('endmodule', initial + 'endmodule')
