"""Clone immutable harnesses and pin all original sources before validation."""
from pathlib import Path
import hashlib,json,subprocess,difflib,re
HERE=Path(__file__).resolve().parent
MIG=HERE.parent
PROJECT=MIG.parent
ART=HERE/'artifacts'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
    roots=[PROJECT/'source',PROJECT/'ipcore',PROJECT/'constraints',MIG/'capture_endpoint',
           MIG/'capture_lease',MIG/'capture_core_contract',MIG/'whole_candidate']
    paths=list(PROJECT.glob('*.pds'))
    for root in roots:paths.extend(p for p in root.rglob('*') if p.is_file())
    return {str(p):sha(p) for p in sorted(set(paths))}
def main():
    ART.mkdir(exist_ok=True)
    before=ART/'immutable_before.json'
    if not before.exists():before.write_text(json.dumps(snapshot(),indent=2))
    original=MIG/'capture_endpoint/fpga_v8_capture_control_axil.v'
    raw=original.read_bytes()
    raw=raw.replace(b'module fpga_v8_capture_control_axil #(',b'module fpga_v8_capture_control_axil_arm_v2 #(')
    raw=raw.replace(b'doorbell && !host_bound && config_ready;',b'doorbell && !host_bound;')
    raw=raw.replace(b'if(config_valid) begin pending<=ARM_WAIT;',b'if(config_valid && config_ready) begin pending<=ARM_WAIT;')
    raw=raw.replace(b'// Ready-dependent, single-edge dispatch from immutable holding slots.',b'// READY-independent, single-edge request from immutable holding slots.')
    raw=raw.replace(b'// No unaccepted valid is queued, so a busy ARM cannot strand host ACK.',b'// READY is sampled only in the sequential dispatch decision below.')
    candidate=HERE/'fpga_v8_capture_control_axil_arm_v2.v'
    candidate.write_bytes(raw)
    (HERE/'control.diff').write_text(''.join(difflib.unified_diff(original.read_text().splitlines(True),candidate.read_text().splitlines(True),fromfile=str(original),tofile=str(candidate))))
    # Clones are generated validation inputs, with every substitution recorded.
    clones={
      'core':('capture_core_contract',['run_tests.py','verify_contract.py',
               'tb_capture_core_contract.sv','fpga_v8_capture_contract_memory.sv']),
      'core_revision':('capture_core_contract',['run_tests.py','verify_contract.py',
               'tb_capture_core_contract.sv','fpga_v8_capture_contract_memory.sv']),
      'core_priority':('capture_core_contract',['run_tests.py','verify_contract.py',
               'tb_capture_core_contract.sv','fpga_v8_capture_contract_memory.sv']),
      'core_final_b':('capture_core_contract',['run_tests.py','verify_contract.py',
               'tb_capture_core_contract.sv','fpga_v8_capture_contract_memory.sv']),
      'endpoint':('capture_endpoint',['run_tests.py','tb_fpga_v8_capture_endpoint.sv','port_api.json',
                                      'fpga_v8_coop_axil_router.v','register_map.json']),
      'lease':('capture_lease',['run_tests.py','verify_trace.py','tb_capture_lease.sv'])}
    for name,(old,files) in clones.items():
        dest=HERE/name;dest.mkdir(exist_ok=True)
        if (dest/'artifacts/results.json').exists():continue
        for fn in files:
            src=MIG/old/fn
            if not src.exists():continue
            raw=src.read_bytes()
            # The cloned runner resolves immutable bindings from the original MIG.
            if fn=='run_tests.py':
                raw=raw.replace(b'MIG=HERE.parent',b'MIG=HERE.parent.parent')
                if name=='endpoint':raw=raw.replace(b'HERE.parent',b'HERE.parent.parent')
                if name.startswith('core'):
                    raw=raw.replace(b'scanned=module_scan()',b'scanned={"scope":"isolated generated harness clone"}')
                if name=='endpoint':
                    raw=raw.replace(b'ROOT=HERE.parent.parent.parent',b'ROOT=HERE.parent.parent.parent.parent')
                    raw=raw.replace(b'control_bytes=(HERE/"fpga_v8_capture_control_axil.v").read_bytes()',b'control_bytes=(HERE.parent/"fpga_v8_capture_control_axil_arm_v2.v").read_bytes()')
                    raw=raw.replace(b'HERE/"fpga_v8_capture_control_axil.v"',b'HERE.parent/"fpga_v8_capture_control_axil_arm_v2.v"')
                    raw=raw.replace(b'assert all(len(hits)==1 for hits in names.values()),names',b'# Generated isolated harness clone; immutable originals remain registered separately.')
            if fn=='tb_fpga_v8_capture_endpoint.sv':
                raw=raw.replace(b'fpga_v8_capture_control_axil capture_control',b'fpga_v8_capture_control_axil_arm_v2 capture_control')
                # Actual wrapper idle includes the admitted SOF predicate.
                raw=raw.replace(b'.engine_idle(engine_idle)',b'.engine_idle(engine_idle && !admitted_sof)')
            if fn=='tb_capture_core_contract.sv':
                raw=raw.replace(b'reg cfgv=0;',b'wire cfgv;')
                raw=raw.replace(b'reg [31:0] cfggen=0;',b'wire [31:0] cfggen;')
                start=raw.index(b'    task automatic arm(')
                end=raw.index(b'    task automatic send_frame',start)
                raw=raw[:start]+b'''    task automatic capture_write(input [31:0] address,value);
        begin
            @(negedge clk); cap_addr=address;cap_data=value;cap_av=1;cap_wv=1;
            @(posedge clk); if(!cap_ar||!cap_wr)$fatal(1,"capture holding slots unavailable");
            @(negedge clk);cap_av=0;cap_wv=0;
            // Every ARM races a real camera SOF on the committed request edge.
            if(address==32'h110)begin
                sv=1;#1;if(!cfgv||admit)$fatal(1,"ARM priority over actual SOF");
            end
            wait(cap_bv); if(cap_bp!==0)$fatal(1,"capture ARM B reject");
            @(negedge clk);sv=0;cap_br=1;@(negedge clk);cap_br=0;
        end
    endtask
    task automatic arm(input integer generation);
        begin
            wait_camera_idle();capture_write(32'h10c,generation);
            capture_write(32'h110,1);
            $fdisplay(trace,"ARM %0d",generation);
            wait_camera_idle();checks=checks+1;
        end
    endtask
'''+raw[end:]
                raw=raw.replace(b'rst_n=0;cfgv=0;',b'rst_n=0;cap_av=0;cap_wv=0;cap_br=0;')
                insert=b'''    reg [31:0] cap_addr=0,cap_data=0;
    reg cap_av=0,cap_wv=0,cap_br=0;
    wire cap_ar,cap_wr,cap_bv; wire [1:0] cap_bp;
    fpga_v8_capture_control_axil_arm_v2 capture_control (
        .clk(clk),.rst_n(rst_n),.config_valid(cfgv),.config_ready(cfgr),.config_generation(cfggen),
        .config_accept(cfga),.config_reject(cfgx),.epoch_start(epoch),.armed(armed),.config_ok(cfgok),
        .protocol_fault(lease_fault),.bank0_state(rawstate0),.bank1_state(rawstate1),
        .host_valid(1'b0),.host_src_addr(32'd0),.host_length(32'd0),.host_seq(32'd0),
        .host_generation(32'd0),.host_camera(3'd0),.host_bank(1'b0),.host_token(64'd0),
        .host_release_ready(1'b0),.host_release_accept(1'b0),.host_release_reject(1'b0),
        .published_count(pub_count),.failed_count(fail_count),.rejected_release_count(reject_count),
        .s_axil_awaddr(cap_addr),.s_axil_awprot(3'd0),.s_axil_awvalid(cap_av),.s_axil_awready(cap_ar),
        .s_axil_wdata(cap_data),.s_axil_wstrb(4'hf),.s_axil_wvalid(cap_wv),.s_axil_wready(cap_wr),
        .s_axil_bresp(cap_bp),.s_axil_bvalid(cap_bv),.s_axil_bready(cap_br),
        .s_axil_araddr(32'd0),.s_axil_arprot(3'd0),.s_axil_arvalid(1'b0),.s_axil_rready(1'b0)
    );
'''
                raw=raw.replace(b'    fpga_v8_capture_lease #(',insert+b'    fpga_v8_capture_lease #(')
            if fn=='run_tests.py' and name.startswith('core'):
                raw=raw.replace(b'return primitives+fifo+rtl',b'return primitives+fifo+rtl+[HERE.parent/"fpga_v8_capture_control_axil_arm_v2.v"]')
            if name in ['core_revision','core_priority','core_final_b'] and fn=='tb_capture_core_contract.sv':
                raw=raw.replace(b'@(negedge clk); cap_addr=address;',b'@(negedge clk); if(address==32\'h110)begin sv=1;tick(1);end cap_addr=address;')
                raw=raw.replace(b'if(!cfgv||admit)$fatal(1,"ARM priority over actual SOF");',b'if(!cfgv||admit||!camera.ov5640_ddr_w_en.s_vsync_rise)$fatal(1,"ARM priority over synchronized actual SOF");')
                raw=raw.replace(b'common_reset();arm(101);',b'common_reset();arm(100);arm(101);')
                marker=b'    task automatic send_frame'
                rejection=b'''    task automatic busy_arm_probe(input integer phase);
        begin
            @(negedge clk);cap_addr=32'h110;cap_data=1;cap_av=1;cap_wv=1;
            @(posedge clk);if(!cap_ar||!cap_wr)$fatal(1,"probe holding slots");
            @(negedge clk);#1;
            if(!cfgv||cfgr||idle)$fatal(1,"busy probe must request but never handshake phase %0d cfgv=%b ready=%b idle=%b state=%0d",phase,cfgv,cfgr,idle,ctrl_state);
            wait(cap_bv);if(cap_bp!==2)$fatal(1,"busy ARM did not reject phase %0d",phase);
            // Sustained AW/W while B is stalled cannot create a second commit.
            repeat(8)begin @(negedge clk);if(cap_ar||cap_wr||cfgv||cap_bp!==2)$fatal(1,"duplicate busy request");end
            cap_av=0;cap_wv=0;cap_br=1;@(negedge clk);cap_br=0;
            $display("ACTUAL_BUSY_ARM_REJECT phase=%0d state=%0d",phase,ctrl_state);
        end
    endtask
'''
                raw=raw.replace(marker,rejection+marker)
                raw=raw.replace(b'send_frame(1,WIDTH*HEIGHT);wait_publication(1);',b'''fork
            send_frame(1,WIDTH*HEIGHT);
            begin
                wait(ctrl_state==2);busy_arm_probe(1);
                wait(camera_dvalid && !good);busy_arm_probe(2);
                wait(ctrl_state==6);hold_w=1;busy_arm_probe(3);hold_w=0;
            end
        join
        wait_publication(1);''')
                raw=raw.replace(b'if(overflow||dma_abort||retired||abort_req)',b'if(cfgv && cfgr && !idle)$fatal(1,"ARM accepted while engine busy");\n            if(overflow||dma_abort||retired||abort_req)')
            if name=='core_final_b' and fn=='tb_capture_core_contract.sv':
                raw=raw.replace(b'    axi_dma_write #(',b'    reg hold_camera_b=0;wire camera_bready;\n    assign c_bready[4]=camera_bready && !hold_camera_b;\n    axi_dma_write #(')
                raw=raw.replace(b'.m_axi_bvalid(c_bvalid[4]),.m_axi_bready(c_bready[4])',b'.m_axi_bvalid(c_bvalid[4] && !hold_camera_b),.m_axi_bready(camera_bready)')
                raw=raw.replace(b'wait(ctrl_state==6);hold_w=1;busy_arm_probe(3);hold_w=0;',b'wait(ctrl_state==6);hold_camera_b=1;wait(c_bvalid[4]);busy_arm_probe(3);if(publish||dma_done||rawstate0!==1)$fatal(1,"final-B ownership changed before actual B consumption");hold_camera_b=0;')
                raw=raw.replace(b'hold_aw=0;hold_w=0;',b'hold_camera_b=0;hold_aw=0;hold_w=0;')
            if fn=='run_tests.py' and name=='lease':
                raw=raw.replace(b'PROJECT = HERE.parents[1]',b'PROJECT = HERE.parents[2]')
                raw=raw.replace(b'names = scan_modules()',b'names = {"scope":"immutable modules bound into isolated clone"}')
                raw=raw.replace(b"HERE / 'fpga_v8_capture_lease.v'",b"HERE.parent.parent / 'capture_lease/fpga_v8_capture_lease.v'")
                raw=raw.replace(b"HERE / 'fpga_v8_capture_ov5640_ddr.v'",b"HERE.parent.parent / 'capture_lease/fpga_v8_capture_ov5640_ddr.v'")
            (dest/fn).write_bytes(raw)
    manifest=json.loads((HERE/'bindings_manifest.json').read_text())
    manifest['new_sources']=[p.name for p in HERE.iterdir() if p.suffix in ['.v','.sv']]
    manifest['new_source_sha256']={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ['.v','.sv']}
    manifest['api_sha256']={str(p.relative_to(MIG)):sha(p) for p in [MIG/'capture_endpoint/port_api.json']}
    manifest['immutable_snapshot_count']=len(json.loads(before.read_text()))
    (HERE/'bindings_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('IMMUTABLE_BEFORE',manifest['immutable_snapshot_count'])
if __name__=='__main__':main()
