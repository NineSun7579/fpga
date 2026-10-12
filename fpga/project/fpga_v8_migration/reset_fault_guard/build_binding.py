"""Byte-exact audited v2 -> minimal separate binding diffs; never edit the source.

Only controller/FIFO compilation candidates are materialized. Large top and
wrappers are reviewable diffs, not another whole/PnR tree.
"""
from pathlib import Path
import hashlib, json, difflib, re

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'whole_candidate_v2_route_01/rtl'
OUT=HERE/'artifacts'
NAMES=['fpga_v8_cooperative_top_v2','fpga_v8_pcie_fifo_h2f',
       'fpga_v8_pango_pcie_top_h2f','fpga_v8_pcie_dma_h2f',
       'fpga_v8_pcie_dma_controller_h2f','fpga_v8_cooperative_core',
       'fpga_v8_coop_control_axil']
RENAMES={n:n+'_rfg01' for n in NAMES}
AUDIT=json.loads((HERE.parent/'whole_reset_contract_01/source_manifest.json').read_text())
AUDIT={entry['path'].replace('\\','/'):entry for entry in AUDIT}

def digest(b): return hashlib.sha256(b).hexdigest()

def audited_bytes(path):
    b=path.read_bytes()
    rel=path.relative_to(HERE.parent.parent).as_posix()
    entry=AUDIT[rel]
    assert len(b)==entry['bytes'] and digest(b)==entry['sha256'],('audited source changed',rel)
    return b

def preserve_line_endings(original, normalized):
    """Keep mixed CRLF/LF original bytes on every unchanged line."""
    raw=original.splitlines(keepends=True)
    old=[line.rstrip(b'\r\n') for line in raw]
    new=normalized.splitlines()
    eol=b'\r\n' if original.count(b'\r\n')>original.count(b'\n')//2 else b'\n'
    result=[]
    for kind,a,z,c,d in difflib.SequenceMatcher(a=old,b=new,autojunk=False).get_opcodes():
        if kind=='equal': result.extend(raw[a:z])
        else:
            for j,line in enumerate(new[c:d]):
                ending=raw[a+j][len(old[a+j]):] if kind=='replace' and z-a==d-c else eol
                result.append(line+ending)
    return b''.join(result)

def replace(b, old, new, count=1):
    old=old.encode();new=new.encode()
    assert b.count(old)==count,(old,b.count(old),count)
    return b.replace(old,new)

def compatibility(source, extra=(), indented=False):
    # Verilog forward references in audited legacy source: declaration hoist only.
    declarations=[]
    def move(m):
        decl=m[0];clean=re.sub(rb'/\*.*?\*/',b'',decl,flags=re.S)
        if b'=' in clean and not clean.lstrip().startswith(b'localparam'):
            assert clean.lstrip().startswith(b'wire'),decl
            left,rhs=clean[:-1].split(b'=',1)
            name=re.search(rb'(\w+)\s*$',left)[1]
            declarations.append(left.rstrip()+b';')
            return b'assign '+name+b' ='+rhs+b';'
        declarations.append(decl);return b''
    pattern=rb'(?m)^'+(rb'[ \t]*' if indented else b'')+rb'(?:wire|reg|localparam)\s+[^;]*;'
    body=re.sub(pattern,move,source)
    at=body.index(b');')+2
    return body[:at]+b'\n'+b'\n'.join(declarations+list(extra))+b'\n'+body[at:]

def build():
    OUT.mkdir(exist_ok=True)
    manifest={}; candidates={};diffs=[]
    for root in (SOURCE,SOURCE.parent/'inputs'):
        for p in root.rglob('*.v'):
            modules=re.findall(rb'\bmodule\s+(\w+)',p.read_bytes())
            assert not set(modules).intersection({s.encode() for s in RENAMES.values()} |
                    {b'fpga_v8_reset_fault_guard'}),('module name collision',p)
    for n in NAMES:
        original=audited_bytes(SOURCE/(n+'.v'))
        b=original.replace(b'\r\n',b'\n')
        for old,new in RENAMES.items():
            b=re.sub(rb'\b'+old.encode()+rb'\b',new.encode(),b)
        if n=='fpga_v8_cooperative_top_v2':
            anchor='    wire                              pcie_rst        ;'
            b=replace(b,anchor,anchor+'''
    wire rfg_smlh, rfg_rdlh, rfg_admit_axi, rfg_admit_pcie;
    wire rfg_fault_axi, rfg_fault_pcie;
    wire rfg_idle_axi, rfg_idle_pcie;
    fpga_v8_reset_fault_guard u_reset_fault_guard (
        .free_clk(free_clk), .button_rst_n(button_rst_n), .perst_n(perst_n),
        .axi_clk(axi_clk), .axi_rst(axi_rst), .ddr_init_done(ddr_init_done),
        .startup_idle_pcie(rfg_idle_pcie),
        .startup_idle_axi(rfg_idle_axi && v8_cap_engine_idle && !v8_cap_armed &&
            v8_cap_bank0_state==0 && v8_cap_bank1_state==0 &&
            !v8_coop_busy && !v8_coop_bridge_busy && !v8_coop_arbiter_busy &&
            v8_coop_bank0_state==0 && v8_coop_bank1_state==0),
        .pcie_clk(pcie_clk), .pcie_rst(pcie_rst),
        .smlh_link_up(rfg_smlh), .rdlh_link_up(rfg_rdlh),
        .fault(), .runtime_active(), .reconfiguration_required(),
        .admit_axi(rfg_admit_axi), .admit_pcie(rfg_admit_pcie),
        .fault_axi(rfg_fault_axi), .fault_pcie(rfg_fault_pcie)
    );''')
            b=replace(b,'.button_rst_n(button_rst_n)    ,',
                        '.i_admit(rfg_admit_pcie), .i_admit_axi(rfg_admit_axi),\n    .startup_idle_axi(rfg_idle_axi), .startup_idle_pcie(rfg_idle_pcie),\n    .button_rst_n(button_rst_n)    ,')
            b=replace(b,'// .smlh_link_up(smlh_link_up)    ,','.smlh_link_up(rfg_smlh),')
            b=replace(b,'// .rdlh_link_up(rdlh_link_up)    ,','.rdlh_link_up(rfg_rdlh),')
            b=replace(b,'.lease_block(v8_cap_lease_block),',
                        '.lease_block(v8_cap_lease_block | !rfg_admit_axi),',2)
            # Do not change manager output: only the wrapper INPUT needs gating.
            b=replace(b,'.lease_block(v8_cap_lease_block | !rfg_admit_axi),\n    .bank0_state',
                        '.lease_block(v8_cap_lease_block),\n    .bank0_state')
            # Two uses: manager input vs endpoint output, distinguish with adjacent reset.
            b=replace(b,'.rst(axi_rst),\n    .config_valid(v8_cap_config_valid),',
                        '.rst(axi_rst),\n    .config_valid(v8_cap_config_valid && rfg_admit_axi),')
            # Endpoint dispatch rejects ARM when closed, no artificial pending ARM.
            b=replace(b,'.config_ready(v8_cap_config_ready),\n    .config_generation',
                        '.config_ready(v8_cap_config_ready && rfg_admit_axi),\n    .config_generation',2)
            # Manager output is not an expression.
            b=replace(b,'.config_valid(v8_cap_config_valid && rfg_admit_axi),\n    .config_ready(v8_cap_config_ready && rfg_admit_axi),',
                        '.config_valid(v8_cap_config_valid && rfg_admit_axi),\n    .config_ready(v8_cap_config_ready),')
            b=replace(b,'.config_ok(v8_cap_config_ok),\n    .protocol_fault(v8_cap_protocol_fault),',
                        '.config_ok(v8_cap_config_ok),\n    .protocol_fault(v8_cap_protocol_fault | rfg_fault_axi),')
            b=replace(b,'.core_clk(axi_clk),\n    .rst_n(~axi_rst),',
                        '.session_fault(rfg_fault_axi),\n    .core_clk(axi_clk),\n    .rst_n(~axi_rst),')
            b=replace(b,'.input_valid(v8_cap_input_valid),\n    .input_ready(v8_cap_input_ready),\n    .input_raw_valid',
                        '.input_valid(v8_cap_input_valid),\n    .input_ready(v8_cap_input_ready && rfg_admit_axi),\n    .input_raw_valid',2)
            # Restore core OUTPUT input_ready and gate its input_valid instead.
            b=replace(b,'.rst_n(~axi_rst),\n    .input_valid(v8_cap_input_valid),\n    .input_ready(v8_cap_input_ready && rfg_admit_axi),',
                        '.rst_n(~axi_rst),\n    .input_valid(v8_cap_input_valid && rfg_admit_axi),\n    .input_ready(v8_cap_input_ready),')
        elif n in NAMES[1:5]:
            # Thread actual PCIe-domain admission level down to the controller.
            at=b.index(b')(\n')+3 if b')(\n' in b else b.index(b')(    ')+2
            b=b[:at]+b'\n    input wire i_admit,\n'+b[at:]
            if n!='fpga_v8_pcie_dma_controller_h2f':
                target={'fpga_v8_pcie_fifo_h2f':'pango_pcie_top(',
                        'fpga_v8_pango_pcie_top_h2f':'u_pcie_dma(',
                        'fpga_v8_pcie_dma_h2f':'u_pcie_dma_controller('}[n]
                # Instance names vary in source; locate renamed module, then port list.
                child={'fpga_v8_pcie_fifo_h2f':NAMES[2],
                       'fpga_v8_pango_pcie_top_h2f':NAMES[3],
                       'fpga_v8_pcie_dma_h2f':NAMES[4]}[n]
                m=re.search(RENAMES[child].encode()+rb'\s*#\(.*?\)\s*\w+\s*\(',b,re.S)
                assert m,child
                b=b[:m.end()]+b'\n    .i_admit(i_admit),'+b[m.end():]
            if n=='fpga_v8_pcie_dma_controller_h2f':
                # COMMAND direction bit24=0 is H2F (authority-changing writes).
                # Keep F2H reads available for RAW STATUS fault readback. Host
                # decorator closes COPY/CLAIM/ACK; this is not a read-DMA fence.
                b=replace(b,"(i_bar1_wr_addr[9:0] == 9'h100);",
                            "(i_bar1_wr_addr[9:0] == 9'h100) && (i_admit || i_bar1_wr_data[24]);")
                b=replace(b,"(i_apb_paddr == 9'h140);",
                            "(i_apb_paddr == 9'h140) && (i_admit || i_apb_pwdata[24]);")
                for k in ('mrd32','mrd64'):
                    b=replace(b,'assign '+k+'_req_vld =','assign '+k+'_req_vld = i_admit &&')
            if n=='fpga_v8_pcie_fifo_h2f':
                b=replace(b,'input wire i_admit,','input wire i_admit, input wire i_admit_axi,')
                at=b.index(b');')
                b=b[:at].rstrip()+b',\n    output wire startup_idle_axi, startup_idle_pcie\n'+b[at:]
                at=b.index(b');')+2
                b=b[:at]+b'''
assign startup_idle_axi = (state == S_IDLE) && !rx_read_pending &&
    (rx_w_queue_count == 0) && (r_state == R_IDLE) && !read_started;
assign startup_idle_pcie = !mrd_rx_busy && !mwr_tx_busy && !rx_copy_active &&
    !fpga_rx_clk_en_r && !fpga_rx_clk_en_d && !rx_fifo_write_en &&
    (data_wry_state == S_DATA_WRY_IDLE);
'''+b[at:]
                b=replace(b,'S_IDLE: if (!fifo_rx_empty) begin',
                            'S_IDLE: if (i_admit_axi && !fifo_rx_empty) begin')
                b=replace(b,'.fpga_rx_done     (fpga_rx_done     )',
                            '.fpga_rx_done     (fpga_rx_done && i_admit)')
                b=replace(b,'if (rx_transaction_complete && (rx_cnt == dma_total_beats) &&',
                            'if (i_admit && rx_transaction_complete && (rx_cnt == dma_total_beats) &&')
        else:
            # Read-only cooperative fault hint: do not feed bridge_error, which can
            # alter active ownership. Preserve busy and existing completion semantics.
            at=b.index(b');') # inject input before closing module header
            b=b[:at].rstrip()+b',\n    input wire session_fault\n'+b[at:]
            if n=='fpga_v8_cooperative_core':
                b=replace(b,'.core_clk(core_clk), .rst_n(rst_n),',
                            '.session_fault(session_fault),\n        .core_clk(core_clk), .rst_n(rst_n),')
            else:
                b=replace(b,'(last_error != 0), bridge_busy',
                            '((last_error != 0) || session_fault), bridge_busy')
                b=replace(b,"32'h6c: read_register = last_error;",
                            "32'h6c: read_register = session_fault ? 32'h52534647 : last_error;")
        candidate=preserve_line_endings(original,b)
        if n==NAMES[1]:
            # W/R/B data-path suffix unchanged except admission from IDLE. In
            # particular no OR of PERST/fault into writer/fabric reset.
            assert b'if (axi_rst) begin\n        state <= S_IDLE;' in b
            assert b'assign axi_bready = (state == S_BRESP_WAIT);' in b
            assert b'assign axi_wvalid = (state == S_WDATA_SEND) && (rx_w_queue_count != 0);' in b
            old_read=original.replace(b'\r\n',b'\n').split(b'///////////////////////// AXI_read ////////////////////////////////')[1]
            new_read=b.split(b'///////////////////////// AXI_read ////////////////////////////////')[1]
            assert old_read==new_read,'F2H AXI read path changed'
        if n==NAMES[0]:
            old=original.replace(b'\r\n',b'\n')
            # Camera/SFP ingress, DDR adapter/fabric, camera DMA wiring untouched.
            ingress=b'\n'.join(old.splitlines()[900:1529])
            assert ingress in b,'camera/SFP ingress wiring changed'
            assert b'.rst(axi_rst)' in b and b'.epoch_start(v8_cap_epoch_start)' in b
        candidates[n]=candidate
        manifest[n]={'original_sha256':digest(original),'candidate_sha256':digest(candidate),
                     'candidate_module':RENAMES[n]}
        # ASCII escaped comments avoid incorrect GBK decoding; patch implementation
        # is byte-level above, diff is a review artifact rather than a text patch tool.
        diff=''.join(difflib.unified_diff([line+'\n' for line in original.decode('ascii','backslashreplace').splitlines()],
              [line+'\n' for line in candidate.decode('ascii','backslashreplace').splitlines()],
              fromfile='audited_v2/'+n+'.v',tofile='candidate/'+RENAMES[n]+'.v'))
        (OUT/(n+'.diff')).write_text(diff,encoding='utf-8')
        diffs.append(diff)
        if n in (NAMES[1],NAMES[4]):
            (OUT/(RENAMES[n]+'.v')).write_bytes(candidate)
            extra=[b'wire fifo_rx_almost_full;'] if n==NAMES[1] else [b'wire total_length_cfg_done;']
            (OUT/('compat_'+RENAMES[n]+'.v')).write_bytes(compatibility(b,extra))
    (OUT/'binding.diff').write_text(''.join(diffs),encoding='utf-8')
    (OUT/'binding_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return candidates

if __name__=='__main__': build()
