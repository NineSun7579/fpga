"""Generate a connected component-only endpoint/capture/lease/DMA PDS project."""
from pathlib import Path
import re,json,hashlib,subprocess
HERE=Path(__file__).resolve().parent;MIG=HERE.parent;PROJECT=MIG.parent
WORK=HERE/'component_01'
def ports(path):
    text=path.read_bytes().decode('ascii',errors='replace').split(');',1)[0]
    text=re.sub(r'//[^\n]*','',text)
    body=text[text.index('input'):]
    result=[];direction=width=''
    for item in body.split(','):
        item=item.strip()
        m=re.match(r'(input|output|inout)\s+(?:(?:wire|reg)\s+)?(\[[^\]]+\])?\s*(\w+)',item)
        if m:direction,width,name=m.group(1),m.group(2) or '',m.group(3)
        else:name=item
        result.append((direction,width,name))
    return result
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    WORK.mkdir(exist_ok=True)
    wrapper=HERE/'fpga_v8_capture_arm_contract_wrapper.sv'
    endpoint=MIG/'cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v'
    dma=PROJECT/'source/axi_dma/axi_dma_write.v'
    wp=ports(wrapper);ep=ports(endpoint);dp=ports(dma)
    drop={'dma_abort','dma_done','axi_data_ready','axi_cmd_ready'}
    top=[p for p in wp if not p[2].startswith('s_axil_') and p[2] not in drop]
    top += [p for p in ep if p[2].startswith('s_axi_')]
    top += [p for p in dp if p[2].startswith('m_axi_')]
    def width(w):return w.replace('DATA_WIDTH','128').replace('AXI_128','128').replace('AXI_DATA_WIDTH','128').replace('KEEP_WIDTH','16').replace('ID_WIDTH','4')
    # Wrapper sensor DATA_WIDTH is 16; endpoint ID_WIDTH is 7.
    header=[]
    for d,w,n in top:
        if n=='s_data':w='[15:0]'
        elif n.startswith('s_axi_'):w=w.replace('ID_WIDTH','7')
        else:w=width(w)
        header.append(f'    {d} wire {w} {n}')
    lines=['module fpga_v8_capture_arm_loop_top (',',\n'.join(header),' );']
    for d,w,n in wp:
        if n.startswith('s_axil_') or n in drop:lines.append(f'wire {width(w)} {n};')
    lines+=['fpga_v8_capture_arm_contract_wrapper capture_pair (',',\n'.join(f'.{n}({n})' for d,w,n in wp),');']
    lines+=['fpga_v8_coop_axi128_endpoint endpoint (',',\n'.join(f'.{n}({n.replace("m_axil_","s_axil_")})' for d,w,n in ep),');']
    mapping={'clk':'clk','rst':'!rst_n','cmd_valid':'axi_cmd_valid','cmd_addr':'axi_cmd_addr',
             'cmd_len':'axi_cmd_len','cmd_id':"4'd3",'cmd_ready':'axi_cmd_ready',
             'data_in_available':'axi_data_available','abort_req':'dma_abort_req',
             'data_in_abort':'dma_abort','data_in':'axi_data','data_in_keep':"16'hffff",
             'data_in_valid':'axi_data_valid','data_in_last':'dma_done','data_in_ready':'axi_data_ready'}
    lines+=['axi_dma_write #(.WAIT_FOR_DATA(1),.BURST_LEN(16)) dma (',
            ',\n'.join(f'.{n}({mapping.get(n,n)})' for d,w,n in dp),');','endmodule']
    generated=WORK/'fpga_v8_capture_arm_loop_top.v';generated.write_text('\n'.join(lines)+'\n')
    sources=[generated,wrapper,HERE/'fpga_v8_capture_control_axil_arm_v2.v',endpoint,
             MIG/'capture_lease/fpga_v8_capture_lease.v',MIG/'capture_lease/fpga_v8_capture_ov5640_ddr.v',dma,
             PROJECT/'source/axi_dma/stream_pipe.v']
    sources += [PROJECT/'source/ov5640/ov5640_ddr'/(n+'.v') for n in ['ov5640_ddr_w','ov5640_ddr_w_ctrl','ov5640_ddr_w_en']]
    for n in ['ov5640_ddr_fifo','ov5640_ddr_fifo_DRM']:
        root=PROJECT/'ipcore'/n;sources += [root/(n+'.v')]+sorted((root/'rtl').glob('ipm*.v'))
    records=[{'path':p.as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sources]
    (WORK/'expected_inputs.json').write_text(json.dumps({'top':'fpga_v8_capture_arm_loop_top','allowed_stages':['compile','synthesize'],'sources':records},indent=2))
    blocks='\n'.join(f'(_file "{p.as_posix()}" (_format verilog) (_timespec "2026-10-06T00:00:00"))' for p in sources)
    pds=f'''(_flow fab_demo "2022.2-SP6.4"
(_version "1.1.0") (_status "initial")
(_project (_option prj_work_dir (_string ".")) (_option prj_impl_dir (_string ".")))
(_task tsk_setup
 (_widget wgt_select_arch (_input (_part (_family Logos2) (_device PG2L100H) (_speedgrade -6) (_package FBG484))))
 (_widget wgt_my_design_src (_input {blocks}))
 (_widget wgt_my_ips_src)
 (_widget wgt_import_logic_con_file (_input (_file "component.fdc" (_format fdc))))
)
(_task tsk_compile (_command cmd_compile (_gci_state (_integer 0))))
(_task tsk_synthesis (_command cmd_synthesize (_gci_state (_integer 0)) (_option selected_syn_tool_opt (_integer 2))))
(_task tsk_devmap (_command cmd_devmap (_gci_state (_integer 0))))
(_task tsk_pnr (_command cmd_pnr (_gci_state (_integer 0))))
(_task tsk_gen_bitstream (_command cmd_gen_bitstream (_gci_state (_integer 0))))
)
'''
    template=(MIG/'component_synthesis/cooperative_core_01/project.pds').read_text()
    begin=template.index('        (_widget wgt_my_design_src')
    end=template.index('        (_widget wgt_my_ips_src',begin)
    template=template[:begin]+'        (_widget wgt_my_design_src (_input '+blocks+'))\n'+template[end:]
    template=template.replace('fpga_v8_cooperative_core','fpga_v8_capture_arm_loop_top')
    template=template.replace('(_gci_state (_integer 2))','(_gci_state (_integer 0))')
    (WORK/'project.pds').write_text(template)
    (WORK/'component.fdc').write_text('create_clock -name {component_clk} [get_ports {clk}] -period {7.619048} -waveform {0 3.809524}\ndefine_attribute {p:*} {PAP_IS_VIRTUAL_IO} {TRUE}\n')
    print('COMPONENT_READY',len(sources))
if __name__=='__main__':main()
