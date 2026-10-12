"""Generate an isolated, byte-preserving PDS clone; never invoke PDS or the board."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import shutil

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
CLONE=ROOT/'integrated'

# width, suffix, direction for the memory-master interface.
MEM=[(32,'araddr','output'),(8,'arlen','output'),(3,'arsize','output'),
     (2,'arburst','output'),(1,'arvalid','output'),(1,'arready','input'),
     (128,'rdata','input'),(2,'rresp','input'),(1,'rlast','input'),
     (1,'rvalid','input'),(1,'rready','output'),(32,'awaddr','output'),
     (8,'awlen','output'),(3,'awsize','output'),(2,'awburst','output'),
     (1,'awvalid','output'),(1,'awready','input'),(128,'wdata','output'),
     (16,'wstrb','output'),(1,'wlast','output'),(1,'wvalid','output'),
     (1,'wready','input'),(2,'bresp','input'),(1,'bvalid','input'),(1,'bready','output')]
MMIO=[(7,'awid','input'),(32,'awaddr','input'),(8,'awlen','input'),
      (3,'awsize','input'),(2,'awburst','input'),(1,'awlock','input'),
      (4,'awcache','input'),(3,'awprot','input'),(4,'awqos','input'),
      (4,'awregion','input'),(1,'awvalid','input'),(1,'awready','output'),
      (128,'wdata','input'),(16,'wstrb','input'),(1,'wlast','input'),
      (1,'wvalid','input'),(1,'wready','output'),(7,'bid','output'),
      (2,'bresp','output'),(1,'bvalid','output'),(1,'bready','input'),
      (7,'arid','input'),(32,'araddr','input'),(8,'arlen','input'),
      (3,'arsize','input'),(2,'arburst','input'),(1,'arlock','input'),
      (4,'arcache','input'),(3,'arprot','input'),(4,'arqos','input'),
      (4,'arregion','input'),(1,'arvalid','input'),(1,'arready','output'),
      (7,'rid','output'),(128,'rdata','output'),(2,'rresp','output'),
      (1,'rlast','output'),(1,'rvalid','output'),(1,'rready','input')]
AXIL=[(32,'awaddr'),(1,'awvalid'),(1,'awready'),(32,'wdata'),(4,'wstrb'),
      (1,'wvalid'),(1,'wready'),(2,'bresp'),(1,'bvalid'),(1,'bready'),
      (32,'araddr'),(1,'arvalid'),(1,'arready'),(32,'rdata'),(2,'rresp'),
      (1,'rvalid'),(1,'rready')]

def width(w): return f'[{w-1}:0] ' if w>1 else ''
def decl(w,n,d='wire'): return f'{d} {width(w)}{n};'
def replace_once(raw,old,new):
    assert raw.count(old)==1, (old[:100],raw.count(old))
    return raw.replace(old,new,1)
def hashes():
    paths=[p for d in ['source','ipcore'] for p in (BASE/d).rglob('*') if p.is_file()]
    paths.append(BASE/'project/project.pds')
    return {str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def adapter():
    ports=['input wire clk, rst','output wire capture_hold',
           'input wire [31:0] camera_state, camera_prev_base',
           'input wire [1:0] camera_published',
           'input wire camera_cmd_valid, camera_awvalid, camera_wvalid, camera_abort']
    ports += [f'{d} wire {width(w)}s_axi_{n}' for w,n,d in MMIO]
    ports += [f'{d} wire {width(w)}m_axi_{n}' for w,n,d in MEM]
    s='`timescale 1ns/1ps\nmodule delivery_top_adapter #(parameter WIDTH=640, HEIGHT=480, OUT_HEIGHT=640, TOP_ROWS=80) (\n'
    s+=',\n'.join(ports)+'\n);\n'
    s+='\n'.join(decl(w,'l_'+n) for w,n in AXIL)+'\n'
    s+='wire cmd_valid,cmd_ready,busy,done,error,config_error;\nwire [31:0] src,dst;\n'
    s+='axi_to_axi_lite #(.AXI_ID_LEN(7)) mmio_bridge (\n.axi_clk(clk),.axi_rst(rst),\n'
    connections=[]
    for _,n,_ in MMIO:
        value='s_axi_'+n
        if n in ['awprot','arprot']: value+='[1:0]'
        if n=='awlock': value="{1'b0,s_axi_awlock}"
        connections.append(f'.s_axi_{n}({value})')
    connections += [f'.m_axil_{n}(l_{n})' for _,n in AXIL]
    s+=',\n'.join(connections)+'\n);\n'
    s+='delivery_regs #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.OUT_HEIGHT(OUT_HEIGHT)) regs (\n.clk(clk),.rst(rst),\n'
    s+=',\n'.join(f'.s_{n}(l_{n})' for _,n in AXIL)+',\n'
    s+='\n'.join(['.capture_hold(capture_hold),',
        '.camera_state(camera_state),.camera_prev_base(camera_prev_base),',
        '.camera_published(camera_published),.camera_cmd_valid(camera_cmd_valid),',
        '.camera_awvalid(camera_awvalid),.camera_wvalid(camera_wvalid),.camera_abort(camera_abort),',
        '.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_src(src),.cmd_dst(dst),',
        '.core_busy(busy),.core_done(done),.core_error(error),.core_config_error(config_error));'])+'\n'
    s+='delivery_rgb_ddr #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.OUT_HEIGHT(OUT_HEIGHT),.TOP_ROWS(TOP_ROWS)) core (\n'
    s+='.clk(clk),.rst_n(!rst),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_src(src),.cmd_dst(dst),\n'
    s+='.busy(busy),.done(done),.error(error),.config_error(config_error),\n'
    s+=',\n'.join(f'.m_axi_{n}(m_axi_{n})' for _,n,_ in MEM)+'\n);\nendmodule\n'
    return s.encode('ascii')

def extend_arb(raw):
    start=raw.index(b'    // ---- master 5')
    end=raw.index(b'    // ---- slave',start)
    block=raw[start:end].replace(b'master 5',b'master 6 (delivery)').replace(b'm5_',b'm6_')
    raw=raw[:end]+block+raw[end:]
    raw=replace_once(raw,b'wire [5:0] req_v',b'wire [6:0] req_v')
    raw=replace_once(raw,b'{m5_awvalid,',b'{m6_awvalid, m5_awvalid,')
    raw=replace_once(raw,b"wire [5:0] rr_mask = 6'b111111",b"wire [6:0] rr_mask = 7'b1111111")
    raw=replace_once(raw,b'wire [5:0] req_hi',b'wire [6:0] req_hi')
    raw=raw.replace(b"req_hi[4] ? 3'd4 : 3'd5",b"req_hi[4] ? 3'd4 : req_hi[5] ? 3'd5 : 3'd6")
    raw=raw.replace(b"req_v[4] ? 3'd4 : 3'd5",b"req_v[4] ? 3'd4 : req_v[5] ? 3'd5 : 3'd6")
    # Extend each existing AW/W/B mux without changing selection/retirement logic.
    for field in ['awid','awaddr','awlen','awsize','awburst','awlock','awcache','awprot']:
        pattern=rb"eff_sel == 3'd5 \? m5_"+field.encode()+rb'\s*:'
        raw,count=re.subn(pattern,f"eff_sel == 3'd6 ? m6_{field} : ".encode()+b'\\g<0>',raw)
        assert count==1,(field,count)
    for field in ['wdata','wstrb','wlast','wvalid','bready']:
        pattern=rb"owner == 3'd5 \? m5_"+field.encode()+rb'\s*:'
        raw,count=re.subn(pattern,f"owner == 3'd6 ? m6_{field} : ".encode()+b'\\g<0>',raw)
        assert count==1,(field,count)
    for field in ['awready','wready','bvalid','bid','bresp']:
        pattern=rb'    assign m5_'+field.encode()+rb'[^;]+;'
        match=re.search(pattern,raw); assert match
        new=match[0].replace(b'm5_',b'm6_').replace(b"3'd5",b"3'd6")
        raw=raw[:match.end()]+b'\n'+new+raw[match.end():]
    raw=replace_once(raw,b"rr        <= (eff_sel == 3'd5)",b"rr        <= (eff_sel == 3'd6)")
    return raw

def wire_top(raw):
    # S06 has only these two active tieoffs in the current top.
    for n in ['arvalid','rready']:
        pattern=rb'assign npu_s4_axi_'+n.encode()+rb'\s*=\s*[^;]+;'
        raw,count=re.subn(pattern,b'',raw); assert count==1
    # Replace dead M02 response tieoffs with a proper AXI register bridge.
    raw,count=re.subn(rb'assign npu_reg_axi_\w+\s*=\s*[^;]+;',b'',raw)
    assert count==11,count
    for n,w in [('awid',7),('awlen',8),('bid',7),('rid',7)]:
        pattern=rb'(wire\s+)\[[^\]]+\](\s+npu_reg_axi_'+n.encode()+rb'\b)'
        raw,count=re.subn(pattern,rb'\g<1>'+f'[{w-1}:0]'.encode()+rb'\g<2>',raw)
        assert count==1,(n,count)
    text='\n// DELIVERY: isolated cam5 DDR preprocessing integration.\n'
    text+='wire delivery_hold;\nwire [31:0] delivery_prev;\nwire [1:0] delivery_published;\n'
    text+='\n'.join(decl(w,'delivery_'+n) for w,n,_ in MEM)+'\n'
    # Missing retired NPU request declarations were implicit nets in the baseline.
    for w,n,_ in MMIO:
        name='npu_reg_axi_'+n
        if not re.search(rb'\bwire\s+(?:\[[^\]]+\]\s*)?'+name.encode()+rb'\b',raw):
            text+=decl(w,name)+'\n'
    declarations=text
    text=''
    text+="assign npu_s4_axi_arid=4'hd;\n"
    for n in ['araddr','arlen','arsize','arburst','arvalid','rready']:
        value='delivery_'+n+('[3:0]' if n=='arlen' else '')
        text+=f'assign npu_s4_axi_{n}={value};\n'
    text+="assign npu_s4_axi_arlock=0;\nassign npu_s4_axi_arcache=0;\nassign npu_s4_axi_arprot=0;\n"
    for n in ['arready','rdata','rresp','rlast','rvalid']:
        text+=f'assign delivery_{n}=npu_s4_axi_{n};\n'
    text+='delivery_top_adapter delivery_u (\n.clk(axi_clk),.rst(axi_rst),\n'
    text+='.capture_hold(delivery_hold),.camera_state(cam5_diag_state),.camera_prev_base(delivery_prev),\n'
    text+='.camera_published(delivery_published),.camera_cmd_valid(cam5_cmd_valid),\n'
    text+='.camera_awvalid(cam5_axi_awvalid),.camera_wvalid(cam5_axi_wvalid),.camera_abort(cam5_dma_abort),\n'
    text+=',\n'.join(f'.s_axi_{n}(npu_reg_axi_{n})' for _,n,_ in MMIO)+',\n'
    text+=',\n'.join(f'.m_axi_{n}(delivery_{n})' for _,n,_ in MEM)+'\n);\n'
    raw=replace_once(raw,b'ddr_w_arb u_ddr_w_arb (',declarations.encode()+b'\nddr_w_arb u_ddr_w_arb (')
    end=raw.rindex(b'endmodule')
    raw=raw[:end]+text.encode()+b'\n'+raw[end:]
    arb_ports=[]
    for n in ['awid','awaddr','awlen','awsize','awburst','awlock','awcache','awprot',
              'awvalid','awready','wdata','wstrb','wlast','wvalid','wready','bid','bresp','bvalid','bready']:
        value={ 'awid':"4'hd",'awlock':"1'b0",'awcache':"4'd0",'awprot':"3'd0",'bid':''}.get(n,'delivery_'+n)
        arb_ports.append(f'.m6_{n}({value}),')
    raw=replace_once(raw,b'    .s_awid     (arb_s_awid',('\n'.join(arb_ports)+'\n    .s_awid     (arb_s_awid').encode())
    # Change only cam5's top-level admission/monitor connections, not camera RTL.
    a=raw.index(b') cam5_ov5640_ddr ('); b=raw.index(b');',a)
    block=raw[a:b]
    block=replace_once(block,b".axi_cam_en     (1'b1)",b'.axi_cam_en     (!delivery_hold)')
    block=replace_once(block,b'.prev_frame_base()',b'.prev_frame_base(delivery_prev)')
    block=replace_once(block,b'.xdma_req  ()',b'.xdma_req  (delivery_published)')
    raw=raw[:a]+block+raw[b:]
    return raw

def fix_f2h_completion(raw):
    # FIFO consumption is prefetch, not PCIe completion.  Request bits cover
    # launch until TX busy takes over; TX busy drops on the final accepted
    # payload of the entire request, including all MPS-sized packets.
    raw = replace_once(raw,
        b'.i_mwr_tx_busy              (~fpga_tx_done              )',
        b'.i_mwr_tx_busy              (mwr32_req | mwr64_req | mwr_tx_busy)')
    # The controller emits 10 bits (zero encodes 1024 DW).  Matching its
    # output width prevents an undriven bit 10 entering the TX length decode.
    raw = replace_once(raw, b'wire        [10:0]              req_length;',
                            b'wire        [9:0]               req_length;')
    return replace_once(raw, b'.i_req_length               (req_length                 )',
                             b".i_req_length               ({1'b0, req_length}         )")

def fix_f2h_read_length(raw):
    # Both the transmitter output and prefetch controller input are 11 bits.
    return replace_once(raw, b'wire      [9:0]     mwr_rd_length;',
                             b'wire      [10:0]    mwr_rd_length;')

def main():
    before=hashes()
    production_modules=set()
    for p in (BASE/'source').rglob('*.v'):
        production_modules.update(re.findall(rb'\bmodule\s+(\w+)',p.read_bytes()))
    new_modules=set()
    for raw in [adapter(),*(p.read_bytes() for p in (ROOT/'rtl').glob('*.v'))]:
        modules=set(re.findall(rb'\bmodule\s+(\w+)',raw))
        assert not modules & (production_modules|new_modules),'Delivery module collision'
        new_modules.update(modules)
    CLONE.mkdir(exist_ok=True)
    for folder in ['source','ipcore']:
        shutil.copytree(BASE/folder,CLONE/folder,dirs_exist_ok=True)
    (CLONE/'project').mkdir(exist_ok=True)
    if (BASE/'project/ipcore').exists():
        shutil.copytree(BASE/'project/ipcore',CLONE/'project/ipcore',dirs_exist_ok=True)
    # The project references a target PCF outside project; preserve it if supplied.
    if (BASE/'device_map/top.pcf').exists():
        (CLONE/'device_map').mkdir(exist_ok=True)
        shutil.copy2(BASE/'device_map/top.pcf',CLONE/'device_map/top.pcf')
    changed={}
    for relative,fn in [('source/top.v',wire_top),('source/axi_crossbar/ddr_w_arb.v',extend_arb),
                       ('source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma.v',fix_f2h_completion),
                       ('source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_tx_top.v',fix_f2h_read_length)]:
        original=(BASE/relative).read_bytes(); candidate=fn(original)
        (CLONE/relative).write_bytes(candidate)
        changed[relative]={'before':hashlib.sha256(original).hexdigest(),
                           'after':hashlib.sha256(candidate).hexdigest()}
        diff=''.join(difflib.unified_diff(original.decode('gbk','replace').splitlines(True),
                                         candidate.decode('gbk','replace').splitlines(True),
                                         fromfile=relative,tofile='integrated/'+relative))
        (ROOT/(Path(relative).name+'.diff')).write_text(diff,encoding='utf-8')
    dst=CLONE/'source/delivery'; dst.mkdir(exist_ok=True)
    for p in (ROOT/'rtl').glob('*.v'): shutil.copy2(p,dst/p.name)
    (dst/'delivery_top_adapter.v').write_bytes(adapter())
    project=(BASE/'project/project.pds').read_bytes()
    marker=b'(_widget wgt_my_design_src'
    pos=project.index(b'(_input',project.index(marker))+len(b'(_input')
    entries=b''.join(f'\n                (_file "../source/delivery/{p.name}" (_format verilog) (_timespec "2026-10-08T00:00:00"))'.encode()
                     for p in sorted(dst.glob('*.v')))
    project=project[:pos]+entries+project[pos:]
    (CLONE/'project/project.pds').write_bytes(project)
    # Resolve every synthesis/IP/constraint source; generated output records are excluded.
    refs=re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"',project)
    source_refs=[x for x in refs if x.startswith((b'../source/',b'../ipcore/',b'ipcore/'))]
    missing=[x.decode() for x in source_refs if not (CLONE/'project'/x.decode()).exists()]
    assert not missing,missing
    assert before==hashes(),'Production changed during clone generation'
    report={'production_files_unchanged':len(before),'changed_clone_files':changed,
            'resolved_source_references':len(source_refs),'project':str(CLONE/'project/project.pds'),
            'mmio_slot':'0x40020000..0x400200ff','read_master':'crossbar S06, id 0xd',
            'new_modules_collision_checked':sorted(n.decode() for n in new_modules),
            'write_master':'ddr_w_arb m6, id 0xd','immutable_input':'cam5 admission hold + drain + published bank',
            'pds_executed':False,'board_accessed':False}
    (ROOT/'integration_manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
