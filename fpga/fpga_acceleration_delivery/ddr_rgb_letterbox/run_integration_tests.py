"""Compile the isolated project RTL and simulate actual adapters/crossbar/arbiter."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import build_integration as build

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'integration_artifacts'
BIN=Path('C:/modeltech64_10.6e/win64')

def run(argv,log,cwd=OUT):
    p=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,
                     errors='replace',timeout=120)
    text=p.stdout+p.stderr; log.write_text(text)
    if p.returncode or '** Error' in text or '** Fatal' in text or 'FAIL ' in text:
        raise RuntimeError(f'{log}\n{text[-5000:]}')
    return text

def testbench():
    # Start from byte-exact endpoint TB, replace its direct command/master wiring
    # with the real integrated host MMIO bridge, S06 read crossbar, m6 writer.
    raw=(ROOT/'sim/tb_delivery_rgb_ddr.sv').read_text()
    raw=raw.replace('module tb_delivery_rgb_ddr;','module tb_delivery_integration;')
    raw=raw.replace('parameter W=4, H=3, OH=5, TOP=1, STALL=1, FAULT=0;',
                    'parameter W=4, H=3, OH=5, TOP=1, STALL=1, FAULT=0;')
    start=raw.index('    delivery_rgb_ddr #'); end=raw.index('    reg [7:0] expected',start)
    declaration='\nwire capture_hold;\nreg [31:0] camera_state=4;\nreg [1:0] published=0;\n'
    declaration+='wire [31:0] prev_base=32\'h01800000;\nreg camera_cmd=0,camera_aw=0,camera_w=0;\n'
    declaration+='\n'.join(build.decl(w,'ep_'+n) for w,n,_ in build.MEM)+'\n'
    declaration+='\n'.join(build.decl(w,'host_'+n,'reg' if d=='input' else 'wire')
                            for w,n,d in build.MMIO)+'\n'
    declaration+='\n'.join(build.decl(w,'mmio_'+n) for w,n,_ in build.MMIO)+'\n'
    declaration+='delivery_top_adapter #(.WIDTH(W),.HEIGHT(H),.OUT_HEIGHT(OH),.TOP_ROWS(TOP)) dut (\n'
    declaration+='.clk(clk),.rst(!rst_n),.capture_hold(capture_hold),.camera_state(camera_state),\n'
    declaration+='.camera_prev_base(prev_base),.camera_published(published),.camera_cmd_valid(camera_cmd),\n'
    declaration+='.camera_awvalid(camera_aw),.camera_wvalid(camera_w),.camera_abort(1\'b0),\n'
    declaration+=',\n'.join(f'.s_axi_{n}(mmio_{n})' for _,n,_ in build.MMIO)+',\n'
    declaration+=',\n'.join(f'.m_axi_{n}(ep_{n})' for _,n,_ in build.MEM)+'\n);\n'
    declaration+='wire [3:0] slave_awid;\ninteger camera_writes[0:5];\n'
    declaration+='wire [5:0] c_awready,c_wready;\nreg [5:0] c_pending=0;\ninteger c;\n'
    declaration+='always @(posedge clk) if(!rst_n) c_pending<=0; else for(c=0;c<6;c=c+1) begin\n'
    declaration+='if(c_awready[c]) c_pending[c]<=1; if(c_wready[c] && c_pending[c]) c_pending[c]<=0; end\n'
    arb=[]
    for m in range(7):
        for n in ['awid','awaddr','awlen','awsize','awburst','awlock','awcache','awprot',
                  'awvalid','awready','wdata','wstrb','wlast','wvalid','wready','bid','bresp','bvalid','bready']:
            if m==6:
                value={'awid':"4'hd",'awlock':"1'b0",'awcache':"4'd0",'awprot':"3'd0",'bid':''}.get(n,'ep_'+n)
            else:
                value={'awid':f"4'd{m}",'awaddr':f"32'h{0x100000+m*16:08x}",
                       'awlen':"8'd0",'awsize':"3'd4",'awburst':"2'd1",'awlock':"1'b0",
                       'awcache':"4'd0",'awprot':"3'd0",'awvalid':"1'b1",'awready':f'c_awready[{m}]',
                       'wdata':f"128'd{m+1}",'wstrb':"16'hffff",'wlast':"1'b1",'wvalid':f'c_pending[{m}]',
                       'wready':f'c_wready[{m}]','bid':'','bresp':'','bvalid':'','bready':"1'b1"}[n]
            arb.append(f'.m{m}_{n}({value})')
    for n in ['awid','awaddr','awlen','awsize','awburst','awlock','awcache','awprot','awvalid','awready',
              'wdata','wstrb','wlast','wvalid','wready','bid','bresp','bvalid','bready']:
        value={'awid':'slave_awid','awlock':'','awcache':'','awprot':'','bid':"4'd0"}.get(n,n)
        arb.append(f'.s_{n}({value})')
    declaration+='ddr_w_arb arb (.clk(clk),.rst(!rst_n),\n'+',\n'.join(arb)+'\n);\n'
    # Real S00->M02 register transactions and S06->M00 reads. Disable M00 writes
    # exactly as current top does; writer goes through camera arbiter separately.
    xbar=['.clk(clk)', '.rst(!rst_n)']
    for m in range(7):
        for w,n,d in build.MMIO:
            # Slave-side IDs are four bits; unused inputs are explicit zeros.
            if m==0: value='host_'+n
            elif m==6 and n.startswith(('ar','r')):
                value={'arid':"4'hd",'arlock':"1'b0",'arcache':"4'd0",'arprot':"3'd0",
                       'arqos':"4'd0",'arregion':None,'rid':''}.get(n,'ep_'+n)
            else: value=f"{4 if n in ['awid','arid','bid','rid'] else w}'d0" if d=='input' else ''
            if n in ['awregion','arregion']: continue # No region on slave interfaces
            xbar.append(f'.s0{m}_axi_{n}({value})')
        for n in ['awuser','wuser','buser','aruser','ruser']:
            xbar.append(f'.s0{m}_axi_{n}()')
    for m in range(3):
        for w,n,d in build.MMIO:
            # AXI crossbar master directions are opposite to MMIO slave.
            if m==2: value='mmio_'+n
            elif m==0 and n.startswith(('ar','r')):
                value={'arid':'','arlock':'','arcache':'','arprot':'','arqos':'','arregion':'',
                       'rid':"7'h6d"}.get(n,n)
            else: value='' if d=='input' else f"{w}'d0"
            xbar.append(f'.m0{m}_axi_{n}({value})')
        for n in ['awuser','wuser','buser','aruser','ruser']:
            xbar.append(f'.m0{m}_axi_{n}()')
    declaration+='axi_crossbar_7x3 #(.M00_CONNECT_READ(7\'b1111101),.M00_CONNECT_WRITE(7\'d0),\n'
    declaration+='.M01_CONNECT_READ(7\'d1),.M01_CONNECT_WRITE(7\'d1),\n'
    declaration+='.M02_CONNECT_READ(7\'d1),.M02_CONNECT_WRITE(7\'d1)) xbar (\n'
    declaration+=',\n'.join(xbar)+'\n);\n'
    declaration+='''
    reg [31:0] value;
    reg [1:0] expected_bresp=0, expected_rresp=0;
    task mmio_write(input [31:0] offset,input [31:0] data);
        begin
            @(negedge clk); host_awaddr=32'h40020000+offset; host_awvalid=1;
            host_wdata=data; host_wvalid=0;
            do @(posedge clk); while (!host_awready);
            @(negedge clk); host_awvalid=0; host_wvalid=1;
            do @(posedge clk); while (!host_wready);
            @(negedge clk); host_wvalid=0;
            wait(host_bvalid); if(host_bresp!=expected_bresp) $fatal(1,"FAIL MMIO write");
            @(negedge clk); host_bready=1; @(negedge clk); host_bready=0;
        end
    endtask
    task mmio_read(input [31:0] offset,output [31:0] data);
        begin
            @(negedge clk); host_araddr=32'h40020000+offset; host_arvalid=1;
            do @(posedge clk); while(!host_arready);
            @(negedge clk); host_arvalid=0;
            wait(host_rvalid); if(host_rresp!=expected_rresp || !host_rlast) $fatal(1,"FAIL MMIO read");
            data=host_rdata[31:0];
            // Check response remains stable under independent host backpressure.
            repeat(3) @(negedge clk);
            if(host_rdata[31:0]!==data || !host_rvalid) $fatal(1,"FAIL MMIO read stall");
            host_rready=1; @(negedge clk); host_rready=0;
        end
    endtask
'''
    raw=raw[:start]+declaration+raw[end:]
    # Camera requests share the DDR model; validate routing and count separately.
    raw=raw.replace('reg [31:0] saved_aw;', 'reg [31:0] saved_aw;\n    reg [3:0] saved_owner;')
    raw=raw.replace("araddr!==32'h1000+read_count*16", "araddr!==32'h01800000+read_count*16")
    raw=raw.replace("(araddr-32'h1000)*2", "(araddr-32'h01800000)*2")
    raw=raw.replace("if (got_aw || awaddr!==32'h200000+write_count*16 || awlen!=(WORDS-write_count>=16 ? 15 : WORDS-write_count-1) || awsize!=4 || awburst!=1)",
                     "if (got_aw || (slave_awid==13 && (awaddr!==32'h0a000000+write_count*16 || awlen!=(WORDS-write_count>=16 ? 15 : WORDS-write_count-1))) || awsize!=4 || awburst!=1)")
    raw=raw.replace("(saved_aw-32'h200000)*2+j*16", "(saved_aw-32'h0a000000)*2+j*16")
    raw=raw.replace('saved_aw=awaddr; got_aw=1;', 'saved_aw=awaddr; saved_owner=slave_awid; got_aw=1;')
    raw=raw.replace('if (FAULT==0 || frame>0) begin', 'if (saved_owner==13 && (FAULT==0 || frame>0)) begin')
    raw=raw.replace('$fdisplay(fd,"%0d %08h %032h %04h",frame,saved_aw,saved_w,saved_strb);\n                write_count=write_count+1;',
        '''if(saved_owner==13) begin
                    $fdisplay(fd,"%0d %08h %032h %04h",frame,saved_aw,saved_w,saved_strb);
                    write_count=write_count+1;
                end else begin
                    if(saved_owner>5 || saved_w!==saved_owner+1) $fatal(1,"FAIL camera data routing");
                    camera_writes[saved_owner]=camera_writes[saved_owner]+1;
                end''')
    # Check completion at the endpoint; other cameras may already own the bus.
    raw=raw.replace('if (done && (rvalid || rd_delay>=0 || got_aw || got_w || bvalid))',
                    'if (dut.done && (ep_bvalid || ep_awvalid || ep_wvalid || ep_rvalid))')
    start=raw.index('    task command;'); end=raw.index('    initial begin',start)
    raw=raw[:start]+raw[end:]
    start=raw.index('        bad_address('); end=raw.index('        $fclose(fd);',start)
    raw=raw[:start]+'''
        for(i=0;i<6;i=i+1) camera_writes[i]=0;
        mmio_read(0,value); if(value!=32'h444c5632) $fatal(1,"FAIL signature");
        expected_bresp=2;
        mmio_write(32'h20,2); // reject submission before hold/freeze
        mmio_write(32'h40,32'h0b000000); // no arbitrary destination
        expected_bresp=0; expected_rresp=2;
        mmio_read(32'ha0,value); // exact register decode
        expected_rresp=0;
        mmio_write(32'h20,1);
        repeat(40) @(negedge clk);
        mmio_read(32'h10,value); if(value[1]) $fatal(1,"FAIL froze busy camera");
        camera_state=1; camera_cmd=1;
        repeat(40) @(negedge clk);
        mmio_read(32'h10,value); if(value[1]) $fatal(1,"FAIL froze queued camera");
        camera_cmd=0;
        repeat(40) @(negedge clk);
        mmio_read(32'h10,value); if(value[1]) $fatal(1,"FAIL froze unpublished bank");
        published=1;
        repeat(5) @(negedge clk);
        mmio_read(32'h10,value); if((value&3)!=3) $fatal(1,"FAIL freeze acknowledgment");
        mmio_read(32'h30,value); if(value!=32'h01800000) $fatal(1,"FAIL bank latch");
        for(frame=0;frame<2;frame=frame+1) begin
            read_count=0; write_count=0;
            mmio_write(32'h20,3);
            expected_bresp=2; mmio_write(32'h20,0); expected_bresp=0;
            if(!capture_hold) $fatal(1,"FAIL released a busy source");
            value=0;
            while(!(value&8)) mmio_read(32'h10,value);
            if(value&32'h74 || read_count!=READS || write_count!=WORDS) $fatal(1,"FAIL completion");
            mmio_read(32'h90,value); if(value!=frame+1) $fatal(1,"FAIL job counter");
            repeat(10) @(negedge clk);
        end
        mmio_write(32'h20,0); mmio_read(32'h10,value);
        if(value&7 || capture_hold) $fatal(1,"FAIL release");
        for(i=0;i<6;i=i+1) if(camera_writes[i]<1) $fatal(1,"FAIL camera starvation");
''' +raw[end:]
    raw=raw.replace('PASS tb_delivery_rgb_ddr','PASS tb_delivery_integration')
    initial='\n    initial begin\n'
    for _,n,d in build.MMIO:
        if d=='input':
            val={'awid':0,'arid':0,'awsize':4,'arsize':4,'awburst':1,'arburst':1,'wstrb':65535,'wlast':1}.get(n,0)
            initial+=f'        host_{n}={val};\n'
    initial+='    end\n'
    return raw.replace('endmodule',initial+'endmodule')

def main():
    OUT.mkdir(exist_ok=True)
    lib=OUT/'work'
    if not lib.exists(): run([BIN/'vlib.exe',lib],OUT/'vlib.log')
    clone=build.CLONE
    project=(clone/'project/project.pds').read_bytes()
    # Compile ordinary project design RTL, preserving production encoding.
    design=project[project.index(b'(_widget wgt_my_design_src'):project.index(b'(_widget wgt_my_ips_src')]
    refs=re.findall(rb'\(_file "([^"]+)"',design)
    sources=[(clone/'project'/x.decode()).resolve() for x in refs]
    # Current production PCIe/top sources rely on PDS declaration-order tolerance
    # and repeated declarations. Preserve them; don't conflate a ModelSim parser
    # incompatibility with validation of the new standard-Verilog adapter.
    legacy={'top.v','ips2l_pcie_dma.v','ips2l_pcie_dma_controller.v','pango_pcie_top.v','pcie_fifo.v'}
    checked_sources=[p for p in sources if p.name not in legacy]
    log=run([BIN/'vlog.exe','-work',lib,'-vlog01compat',*checked_sources],OUT/'project_rtl_compile.log')
    assert 'Errors: 0' in log
    # Vendor encrypted IP is reserved for PDS; test actual unencrypted fabric here.
    tb=OUT/'tb_delivery_integration.sv'; tb.write_text(testbench())
    run([BIN/'vlog.exe','-work',lib,'-sv',tb],OUT/'tb_compile.log')
    (OUT/'expected.hex').write_text(''.join(f'{b:02x}\n' for f in range(2)
                                      for b in __import__('run_tests').oracle(4,3,5,1,f)))
    log=run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,
             'tb_delivery_integration','-do','onerror {quit -code 2}; run -all; quit -code 0'],
            OUT/'simulation.log')
    assert 'PASS tb_delivery_integration' in log
    (OUT/'expected.hex').write_text(''.join(f'{b:02x}\n' for f in range(2)
                                      for b in __import__('run_tests').oracle(64,3,5,1,f)))
    log=run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,
             'tb_delivery_integration','-gW=64',
             '-do','onerror {quit -code 2}; run -all; quit -code 0'],
            OUT/'burst16_simulation.log')
    assert 'PASS tb_delivery_integration' in log
    run([BIN/'vlog.exe','-work',lib,'-sv',ROOT/'sim/tb_delivery_camera_hold.sv'],OUT/'camera_hold_compile.log')
    log=run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,
             'tb_delivery_camera_hold','-do','onerror {quit -code 2}; run -all; quit -code 0'],
            OUT/'camera_hold_simulation.log')
    assert 'PASS production camera admission' in log
    run(['wsl','-d','Ubuntu-24.04','--','g++','-std=c++17','-Wall','-Wextra','-Werror',
         '-fsyntax-only','-I/mnt/d/race/ov56401/project/fpga_v8_migration',
         '/mnt/d/race/fpga/git/fpga/fpga/fpga_acceleration_delivery/ddr_rgb_letterbox/host/linux_provider.cpp'],
        OUT/'provider_compile.log')
    run(['wsl','-d','Ubuntu-24.04','--','bash','-lc',
         'g++ -std=c++17 -fPIC -Wall -Wextra -Werror -fsyntax-only '
         '-I/mnt/d/race/ov56401/project/fpga_v8_migration '
         '-I/mnt/d/race/ov56401/project/fpga_v8_migration/current_viewer_native_candidate_02/src '
         '$(pkg-config --cflags Qt5Core) '
         '/mnt/d/race/fpga/git/fpga/fpga/fpga_acceleration_delivery/ddr_rgb_letterbox/host/paired_preprocess.cpp'],
        OUT/'benchmark_compile.log')
    report={'project_ordinary_rtl_files_compiled':len(checked_sources),
            'PDS_legacy_sources_not_ModelSim_compiled':sorted(legacy),
            'simulated':'real MMIO bridge + S00/M02 + S06/M00 crossbar + 7-master DDR arbiter',
            'camera_masters':'six continuous competing writers, data routing and no starvation checked',
            'freeze_checks':'busy, queued-command and unpublished-bank rejection; stable published bank acknowledgment',
            'production_frame_admission':'hold permits current frame data; blocks subsequent SOF; resumes only on new SOF',
            'bytes_compared':2040,'host_provider_linux_syntax':'pass -Wall -Wextra -Werror',
            'host_benchmark_linux_syntax':'pass -Wall -Wextra -Werror, retained RKNN header + local Qt5',
            'vendor_ip_elaboration':'not run (encrypted IP needs PDS)','board_access':False,'pds_run':False}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))

if __name__=='__main__': main()
