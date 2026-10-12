"""Deterministic byte transformations; no writes outside this new directory."""
from pathlib import Path
import difflib
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
ART=HERE/'artifacts'
FROZEN=HERE.parent/'whole_candidate/inputs'
MOTION=HERE.parent.parent/'motion_100h'
OLD=HERE.parent/'pcie_retirement_contract'
FIFO_REL=Path('source/pcie_dma/pcie_fifo.v')
CTRL_REL=Path('source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_controller.v')
FIFO_SHA='c6bcf1f48328ff250e097ad1bbe0e49e8e52001138fe15f9db697da1ddf62027'
CTRL_SHA='0ff0f5c28650e8eb91da5bc39a26c6498874cafe0b51ccfa1847872c3cbacc53'
RETIRED_SHA='b87bf5946dd599461ebd7d0a6e1d4925124692f33a43c0877cb8e41d27158a18'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def api(b): return b[:b.index(b');')+2].split(b'#(',1)[1]

def compatibility(source,extra):
    declarations=[]
    def move(m):
        decl=m[0];clean=re.sub(rb'/\*.*?\*/',b'',decl,flags=re.S)
        attribute=re.match(rb'\(\*.*?\*\)\s*',clean)
        prefix=attribute[0] if attribute else b''
        if attribute:clean=clean[len(prefix):]
        if b'=' in clean and not clean.lstrip().startswith(b'localparam'):
            assert clean.lstrip().startswith(b'wire'),decl
            left,rhs=clean[:-1].split(b'=',1);name=re.search(rb'(\w+)\s*$',left)[1]
            declarations.append(prefix+left.rstrip()+b';')
            return b'assign '+name+b' ='+rhs+b';'
        declarations.append(decl);return b''
    # Attributes stay attached to a hoisted declaration. Do not leave them
    # accidentally attached to the next always block during normalization.
    body=re.sub(rb'(?m)^(?:\(\*[^\n]*?\*\)\s*)?(?:wire|reg|localparam)\s+[^;]*;',move,source)
    at=body.index(b');')+2
    return body[:at]+b'\n// Declaration-only ModelSim compatibility.\n'+b'\n'.join(declarations+extra)+b'\n'+body[at:],len(declarations)

class Edits:
    def __init__(self,b): self.b=b;self.records=[];self.eol=b'\r\n' if b'\r\n' in b else b'\n'
    def replace(self,old,new,label):
        old=old.replace(b'\n',self.eol) if self.eol==b'\r\n' and b'\r\n' not in old else old
        new=new.replace(b'\r\n',b'\n').replace(b'\n',self.eol)
        assert self.b.count(old)==1,(label,self.b.count(old))
        self.b=self.b.replace(old,new,1)
        self.records.append(dict(label=label,old_sha256=hashlib.sha256(old).hexdigest(),
                                 new_sha256=hashlib.sha256(new).hexdigest(),old_bytes=len(old),new_bytes=len(new)))
    def section(self,start,end,new,label):
        a=self.b.index(start);z=self.b.index(end,a)
        self.replace(self.b[a:z],new,label)

def build():
    ART.mkdir(exist_ok=True)
    for root in (FROZEN,MOTION):
        assert sha(root/FIFO_REL)==FIFO_SHA
        assert sha(root/CTRL_REL)==CTRL_SHA
    retired=OLD/'artifacts/fpga_v8_pcie_fifo_retired.v'
    assert sha(retired)==RETIRED_SHA
    frozen_fifo=(FROZEN/FIFO_REL).read_bytes();frozen_ctrl=(FROZEN/CTRL_REL).read_bytes()
    f=Edits(retired.read_bytes())
    f.replace(b'module fpga_v8_pcie_fifo_retired #(',b'module fpga_v8_pcie_fifo_h2f #(','unique FIFO module')
    f.replace(b'pango_pcie_top #(',b'fpga_v8_pango_pcie_top_h2f #(','bind unique production shell')
    f.section(b'reg [31 : 0] rx_cnt;',b'//////////////tx/////////////////',
              (HERE/'rtl/rx_receiver.vh').read_bytes()+b'\n\n','H2F RAM byte reassembly and completion')
    f.replace(b'.wr_en        (fpga_rx_clk_en_d   )',b'.wr_en        (rx_fifo_write_en   )','RX FIFO write enable')
    f.replace(b'.wr_data      (fpga_rx_data       )',b'.wr_data      (rx_fifo_write_data )','RX FIFO packed payload')
    f.section(b'localparam S_IDLE       = 3\'d0;',b'////////////////////////////////////////////////////////////////////////',
              (HERE/'rtl/axi_write_engine.vh').read_bytes()+b'\n\n','AXI write reservation queue and single outstanding burst')
    old=(b'else if (!fpga_data_valid && !fpga_rx_done &&\n'
         b'             (fpga_rx_addr_r == total_beats) &&\n'
         b'             (rx_cnt == dma_total_beats) && fifo_rx_empty &&')
    f.replace(old,b'else if (!fpga_data_valid && !fpga_rx_done && rx_transaction_complete &&\n'
                  b'             (rx_cnt == dma_total_beats) && fifo_rx_empty &&','consume retirement only after packed final chunk')
    assert api(f.b)==api(frozen_fifo)
    txmarker=b'wire         fifo_tx_empty'
    assert f.b[f.b.index(txmarker):]==frozen_fifo[frozen_fifo.index(txmarker):]
    c=Edits(frozen_ctrl)
    c.replace(b'module ips2l_pcie_dma_controller #(',b'module fpga_v8_pcie_dma_controller_h2f #(','unique controller module')
    # Preserve F2H chunk calculation and 32-bit wrap behavior exactly. H2F
    # alone uses current-address boundary and coherent upper/lower carry.
    c.replace(b'reg     [31:0]      dma_total_length;',b'reg [31:0] h2f_chunk_host_high;\nreg     [31:0]      dma_total_length;','H2F host upper word register')
    c.section(b'assign chunk_cur_size      =',b'// Initialize internal chunk variables',
        b'''wire [31:0] h2f_chunk_capacity = (chunk_boundary_limit < CHUNK_SIZE_MAX) ? chunk_boundary_limit : CHUNK_SIZE_MAX;
wire [31:0] h2f_chunk_size = (chunk_rem_bytes < h2f_chunk_capacity) ? chunk_rem_bytes : h2f_chunk_capacity;
// CMD is latched on this same edge. Select its incoming direction for the
// first length, keeping F2H outputs identical from command acceptance onward.
wire h2f_length_cmd_is_write = (device_ep && dma_cmd_reg_vld) ? dma_wr_data[24] :
    (device_rc && apb_cmd_reg_vld) ? apb_pwdata[24] : dma_wr_rd_cmd_flag;
assign chunk_cur_size = !dma_wr_rd_cmd_flag ? h2f_chunk_size :
    ((chunk_rem_bytes[31:CHUNK_SIZE_LOG2] == 0) ? chunk_rem_bytes : CHUNK_SIZE_MAX);
assign is_last_chunk = !dma_wr_rd_cmd_flag ? (chunk_rem_bytes <= chunk_cur_size) :
                                           (chunk_rem_bytes <= CHUNK_SIZE_MAX);
wire [32:0] h2f_host_low_next = {1'b0,chunk_host_addr}+{1'b0,chunk_cur_size};
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) h2f_chunk_host_high <= 0;
    else if (total_length_cfg_done)
        h2f_chunk_host_high <= device_ep ? dma_cmd_h_addr : apb_cmd_h_addr;
    else if (chunk_done && chunk_loop_active && !dma_wr_rd_cmd_flag)
        h2f_chunk_host_high <= h2f_chunk_host_high + h2f_host_low_next[32];
end

''','H2F boundary min and 64-bit carry')
    c.replace(b'else if (total_length_cfg_done)\n        o_ddr3_length <= (total_length_val <= CHUNK_SIZE_MAX) ? total_length_val : CHUNK_SIZE_MAX;',
         b'else if (total_length_cfg_done)\n        o_ddr3_length <= !h2f_length_cmd_is_write ? h2f_chunk_size :\n            ((total_length_val <= CHUNK_SIZE_MAX) ? total_length_val : CHUNK_SIZE_MAX);','first H2F chunk byte length with incoming CMD direction')
    c.replace(b'o_req_length <= {1\'b0, chunk_cur_size[11:2]};',
        b'o_req_length <= !dma_wr_rd_cmd_flag ? ((chunk_cur_size+32\'d3)>>2) : {1\'b0, chunk_cur_size[11:2]};','subsequent chunk DWORD count')
    c.replace(b'if (device_ep)\n            o_req_length <= dma_cmd_reg[9:0];',
        b'if (!dma_wr_rd_cmd_flag && chunk_loop_active)\n            o_req_length <= ((chunk_cur_size+32\'d3)>>2);\n        else if (device_ep)\n            o_req_length <= dma_cmd_reg[9:0];','first H2F chunk DWORD count')
    c.replace(b'else if (l_addr_cfg_done)\n        o_req_addr[63:32] <= device_ep ? dma_cmd_h_addr : apb_cmd_h_addr;',
        b'else if (!dma_wr_rd_cmd_flag && chunk_loop_active)\n        o_req_addr[63:32] <= h2f_chunk_host_high;\n    else if (l_addr_cfg_done)\n        o_req_addr[63:32] <= device_ep ? dma_cmd_h_addr : apb_cmd_h_addr;','H2F coherent request high word')
    c.replace(b'assign cross_4kb_boundary = ~l_addr_cfg_done ? 1\'b0 :',
        b'assign cross_4kb_boundary = (!dma_wr_rd_cmd_flag && chunk_loop_active) ?\n        ((chunk_host_addr[1:0] != 0) || (chunk_cur_size == 0) ||\n         (chunk_cur_size > chunk_boundary_limit)) :\n                            ~l_addr_cfg_done ? 1\'b0 :','H2F current chunk boundary check, retain F2H expression')
    c.replace(b'wire is_final_chunk = (chunk_rem_bytes <= CHUNK_SIZE_MAX);',
        b'wire is_final_chunk = !dma_wr_rd_cmd_flag ? (chunk_rem_bytes <= chunk_cur_size) :\n                                          (chunk_rem_bytes <= CHUNK_SIZE_MAX);','H2F last chunk decision')
    assert api(c.b)==api(frozen_ctrl)
    # MSI, active tracking and controller request state machines unchanged.
    msi_start=b'// 1.'
    old_msi=frozen_ctrl[frozen_ctrl.index(msi_start):]
    new_msi=c.b[c.b.index(msi_start):]
    # Only the explicit last-chunk predicate changes inside this suffix.
    assert old_msi.replace(b'wire is_final_chunk = (chunk_rem_bytes <= CHUNK_SIZE_MAX);',
        b'wire is_final_chunk = !dma_wr_rd_cmd_flag ? (chunk_rem_bytes <= chunk_cur_size) :'+c.eol+
        b'                                          (chunk_rem_bytes <= CHUNK_SIZE_MAX);')==new_msi
    generated={ 'fpga_v8_pcie_fifo_h2f.v':(f.b,frozen_fifo,f.records),
                'fpga_v8_pcie_dma_controller_h2f.v':(c.b,frozen_ctrl,c.records)}
    # Concrete production binding clones: renamings only, no vendor-IP edits.
    for rel,newname,replacements in [
        ('ips2l_pcie_dma.v','fpga_v8_pcie_dma_h2f',[(b'ips2l_pcie_dma_controller #(',b'fpga_v8_pcie_dma_controller_h2f #(')]),
        ('pango_pcie_top.v','fpga_v8_pango_pcie_top_h2f',[(b'ips2l_pcie_dma #(',b'fpga_v8_pcie_dma_h2f #(')])]:
        src=(FROZEN/'source/pcie_dma/pcie_dma_ctrl'/rel).read_bytes();e=Edits(src)
        oldname=Path(rel).stem.encode()
        e.replace(b'module '+oldname+b' #(',b'module '+newname.encode()+b' #(','unique production binding module')
        for a,b in replacements:e.replace(a,b,'bind unique candidate child')
        assert api(src)==api(e.b)
        generated[newname+'.v']=(e.b,src,e.records)
    manifest={}
    for name,(data,original,records) in generated.items():
        target=ART/name;target.write_bytes(data)
        (ART/(name+'.diff')).write_text(''.join(difflib.unified_diff(
            original.decode('gbk',errors='replace').splitlines(True),data.decode('gbk',errors='replace').splitlines(True),
            fromfile='frozen/'+name,tofile='candidate/'+name)),encoding='utf-8')
        manifest[name]=dict(sha256=sha(target),frozen_sha256=hashlib.sha256(original).hexdigest(),
                            api_identical=True,edits=records)
    for name,src,extra in [
        ('baseline_fifo.v',retired.read_bytes(),[b'wire fifo_rx_almost_full;']),
        ('baseline_controller.v',frozen_ctrl,[b'wire total_length_cfg_done;']),
        ('candidate_fifo.v',f.b,[b'wire fifo_rx_almost_full;']),
        ('candidate_controller.v',c.b,[b'wire total_length_cfg_done;'])]:
        data,count=compatibility(src,extra);(ART/name).write_bytes(data)
        manifest[name]=dict(sha256=sha(ART/name),hoisted_declarations=count,
                            explicit_existing_implicit_nets=[x.decode() for x in extra])
    manifest['invariants']=dict(fifo_tx_and_axi_read_suffix_byte_identical=True,
        final_b_retirement_source_sha256=RETIRED_SHA,controller_msi_logic_identical_except_final_chunk_predicate=True)
    (ART/'edit_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':build()
