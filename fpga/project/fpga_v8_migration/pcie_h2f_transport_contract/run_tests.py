"""Local ModelSim only; all outputs restricted to pcie_h2f_transport_contract."""
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
from build_candidates import build,sha,HERE,ART,FROZEN,MOTION,OLD,FIFO_REL,CTRL_REL,compatibility
from prepare_tb import prepare

SIM=Path(os.environ.get('MODELSIM_BIN',r'C:\modeltech64_10.6e\win64'))
PANGO=Path(os.environ.get('PANGO_SIM',r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation'))
DMA=FROZEN/'source/pcie_dma/pcie_dma_ctrl'

def immutable():
    out={}
    for p in OLD.rglob('*'):
        if p.is_file():out[str(p)]=sha(p)
    for root in (FROZEN,MOTION):
        for rel in (FIFO_REL,CTRL_REL):out[str(root/rel)]=sha(root/rel)
    for folder in ('pcie_rx_fifo','pcie_tx_fifo'):
        for p in (FROZEN/'ipcore'/folder).rglob('*.v'):out[str(p)]=sha(p)
    for p in list(DMA.rglob('*.v'))+[
        PANGO/'GTP_DRM36K_E1.v',PANGO/'GTP_DRM18K_E1.v',PANGO/'GTP_GRS.v',
        HERE.parent/'cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v',
        HERE.parent/'cooperative_control/fpga_v8_coop_control_axil.v']:
        out[str(p)]=sha(p)
    return out

def tool(command,cwd,label):
    r=subprocess.run(command,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    text=r.stdout+r.stderr;(cwd/(label+'.log')).write_text(text,encoding='utf-8')
    if r.returncode or '** Error' in text or '** Fatal' in text:raise RuntimeError(label+'\n'+text[-12000:])
    return text

def compile_design(kind):
    cwd=ART/kind;cwd.mkdir(exist_ok=True)
    tool([str(SIM/'vlib.exe'),'work'],cwd,'vlib')
    sources=[PANGO/'GTP_DRM36K_E1.v',PANGO/'GTP_DRM18K_E1.v',PANGO/'GTP_GRS.v']
    for name in ('pcie_rx_fifo','pcie_tx_fifo'):
        folder=FROZEN/'ipcore'/name;sources+=sorted((folder/'rtl').glob('ipm*.v'))+[folder/(name+'.v')]
    sources+=[DMA/'ipm_distributed_sdpram_v1_2.v',DMA/'ips2l_pcie_dma_wr_ctrl.v',
              DMA/'ips2l_pcie_dma_rx_cpld_wr_ctrl.v']
    sources+=[DMA/'ips2l_pcie_dma_ram/ips2l_pcie_dma_ram.v',
              DMA/'ips2l_pcie_dma_ram/rtl/ipm2l_sdpram_v1_1_ips2l_pcie_dma_ram.v']
    sources+=[ART/(kind+'_controller.v'),ART/(kind+'_fifo.v'),DMA/'ips2l_pcie_dma_mrd_tx_ctrl.v',
              HERE.parent/'cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v',
              HERE.parent/'cooperative_control/fpga_v8_coop_control_axil.v']
    tool([str(SIM/'vlog.exe'),'-work','work']+[str(p) for p in sources],cwd,'vlog_rtl')
    cmd=[str(SIM/'vlog.exe'),'-sv','-work','work']
    if kind=='baseline':cmd+=['+define+BASELINE','+define+FIFO_MODULE=fpga_v8_pcie_fifo_retired',
                             '+define+SHELL_MODULE=pango_pcie_top','+define+CONTROL_MODULE=ips2l_pcie_dma_controller']
    tool(cmd+[str(HERE/'tests/pcie_shell.sv'),str(ART/'tb_transport.sv')],cwd,'vlog_tb')
    return cwd

# row: id, kind, bytes, host64, destination, control-word, profile, MRRS, reset
def suites():
    baseline=[(1,1,16,0x1000000,0x40010100,0xcafebabe,1,0,1),
              (2,0,4100,0x1000004,0x08000000,0,0,0,1),
              (3,0,512,0x1000000,0x08000000,0,2,1,1)]
    cases=[]
    def add(kind,bytes,host,target=0x08000000,word=0,profile=3,mrrs=0,reset=1):
        cases.append((len(cases)+100,kind,bytes,host,target,word,profile,mrrs,reset))
    # Actual cooperative producer/CLAIM/ACK through endpoint and control.
    for offset,word in ((0x30,0),(0x40,0),(0x44,0x10203040),(0x48,0x11223344),(0x4c,1),(0x4c,1)):
        add(1,16,0x1000000,0x40010000+offset*4,word,1 if offset==0x30 else 4,0,int(not cases))
    # Every legal DWORD-aligned host offset, including the near-boundary 4B
    # first chunk and a non-zero page. Partial source RAM words cross chunks.
    for off in (0,4,8,12,4092,4100):
        for size in (4092,4100):add(0,size,0x1000000+off,mrrs=(off//4)%4)
    for size in (1,3,4,15,16,17,31,32,255,256,257,4111):
        add(0,size,0x1000004,profile=1 if size<32 else 3,mrrs=1)
    add(0,512,0x1000000,profile=2,mrrs=1)
    add(0,8192,0x100000c,profile=4,mrrs=3)
    # 64-bit host address carry at the actual 4KB boundary.
    add(0,4100,0x00000001fffffffc,mrrs=0)
    add(0,8192,0x00000004fffff008,mrrs=2)
    for off in (0,4):add(0,1228800,0x1000000+off,profile=3,mrrs=0)
    # Persistent credit epoch and byte carry must reinitialize after commands
    # without a reset, with sizes/host offsets/destinations changing each time.
    add(0,17,0x100000c,target=0x08000010,profile=1,reset=0)
    add(0,4100,0x1000004,target=0x09000000,profile=3,reset=0)
    add(0,4092,0x1000ffc,target=0x0a000000,profile=4,reset=0)
    add(0,8188,0x1000004,profile=6,mrrs=1)
    # Faults produce no final credit/MSI; every next row performs common reset.
    add(2,16,0x1000000,profile=1);add(0,16,0x1000000,profile=1)
    add(3,16,0x1000000,profile=1);add(0,16,0x1000000,profile=1)
    add(4,512,0x1000004,profile=3);add(0,512,0x1000004,profile=3)
    add(5,16,0x1000000,profile=1);add(0,16,0x1000000,profile=1)
    add(6,512,0x1000004,profile=5);add(0,512,0x1000004,profile=3)
    return baseline,cases

def run_design(kind,cases):
    cwd=compile_design(kind)
    (cwd/'cases.txt').write_text(''.join(f'{i} {k} {n} {h:016x} {d:08x} {w:08x} {p} {m} {r}\n'
         for i,k,n,h,d,w,p,m,r in cases),encoding='ascii')
    text=tool([str(SIM/'vsim.exe'),'-c','-voptargs=+acc','-onfinish','stop',
               'work.tb_fpga_v8_h2f_transport','+STRICT='+str(int(kind=='candidate')),
               '-do','run -all; quit -f'],cwd,'simulation')
    assert 'H2F_TB_DONE' in text,text
    print(f'{kind}: {len(cases)} cases simulated',flush=True)
    return cwd/'events.trace'

def events(path):
    out=defaultdict(lambda:defaultdict(list))
    for line in path.read_text().splitlines():
        s=line.split();out[int(s[0])][s[2]].append((int(s[1]),s[3:]))
    return out

def audit_baseline(path):
    e=events(path)
    assert e[1]['END'][0][1][0]=='0' and not e[1]['W'] and not e[1]['MSI']
    illegal=[(t,w) for t,w in e[2]['FETCH'] if int(w[0],16)%4096+(int(w[1],16)*4 or 4096)>4096]
    assert illegal
    assert e[3]['END'][0][1][0]=='0'
    proof=dict(retirement_only_first_w_stall_timeout=True,illegal_host_offset4_chunks=illegal,
               retirement_only_wready_before_aw_timeout=True,
               original_failure_evidence_sha256=sha(OLD/'artifacts/results.json'))
    (ART/'negative_evidence.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

def audit_candidate(path,cases):
    all_events=events(path);reports=[]
    totals=defaultdict(int)
    for row in cases:
        ident,kind,byte_count,host,dest,word,profile,mrrs,reset=row
        e=all_events[ident];assert len(e['BEGIN'])==len(e['END'])==1,(ident,'missing case')
        success,aw,w,b,msi,pops,credits,ws,aws=map(int,e['END'][0][1])
        fault=kind in (2,3,4,6)
        expected_beats=(byte_count+15)//16
        expected_bursts=(expected_beats+15)//16
        if fault:
            assert success==0 and msi==credits==0,(ident,'fault falsely completed',e['END'])
            assert aw==1 and w==(0 if kind==6 else (16 if kind==4 else 1))
            assert pops==(2 if kind==6 else w)
            assert b==(0 if kind in (3,6) else 1)
            assert not e['MSI'] and not e['CREDIT']
        else:
            assert success==1 and aw==b==expected_bursts and w==pops==expected_beats
            assert msi==credits==1,(ident,'completion credit/MSI count',msi,credits)
            assert len(e['CREDIT'])==len(e['MSI'])==1
            assert e['MSI'][0][0]>e['B'][-1][0]
            assert e['CREDIT'][0][0]>e['B'][-1][0]
        # Stream oracle uses only host intent. Source bytes must be packed
        # contiguously even when a chunk contributes just 4/8/12 bytes.
        for index,(time,fields) in enumerate(e['W']):
            data,strb,last=int(fields[0],16),int(fields[1],16),int(fields[2])
            count=min(16,byte_count-index*16)
            expected=bytearray(((index*16+j)*37+11)&255 for j in range(count))
            if kind==1 and index==0:expected[:4]=word.to_bytes(4,'little')
            expected.extend(bytes(16-count))
            assert data==int.from_bytes(expected,'little'),(ident,index,'data',fields,expected.hex())
            assert strb==(1<<count)-1,(ident,index,'strobe',fields)
            assert last==int(index%16==15 or index==expected_beats-1)
        for index,(time,fields) in enumerate(e['AW']):
            address,length=int(fields[0],16),int(fields[1],16)
            assert address==dest+index*256,(ident,index,'AW address',hex(address))
            assert length==min(16,expected_beats-index*16)-1
            assert address%4096+(length+1)*16<=4096
        # Independently derive controller chunks from exact byte intent.
        chunks=[];remaining=byte_count;address=host
        while remaining:
            chunk=min(remaining,4096,4096-address%4096)
            chunks.append((address,chunk));address+=chunk;remaining-=chunk
        assert len(e['FETCH'])==len(chunks),(ident,'fetch count',len(e['FETCH']),chunks)
        tlp_expected=[]
        for (time,fields),(address,chunk) in zip(e['FETCH'],chunks):
            got_address,dword_encoding,got_chunk=int(fields[0],16),int(fields[1],16),int(fields[2])
            assert (got_address,got_chunk)==(address,chunk),(ident,'chunk metadata',fields,(address,chunk))
            dwords=(chunk+3)//4
            assert dword_encoding==dwords%1024
            assert address%4==0 and address%4096+dwords*4<=4096
            dw_left=dwords;segment_address=address
            while dw_left:
                n=min(dw_left,32<<mrrs)
                tlp_expected.append((segment_address,n))
                dw_left-=n;segment_address+=n*4
        actual_tlps=[(int(f[0],16),int(f[1])) for t,f in e['TLP']]
        assert actual_tlps==tlp_expected,(ident,'actual MRD segmentation',actual_tlps[:4],tlp_expected[:4])
        sram_expected=[]
        for address,chunk in chunks:
            left=(chunk+3)//4;seg_address=address
            while left:
                dw=min(left,32<<mrrs)
                for offset in range(0,dw*4,16):
                    valid=min(16,dw*4-offset)
                    sram_expected.append(((seg_address-address+offset)//16,(1<<valid)-1,
                                          seg_address-host+offset,valid))
                left-=dw;seg_address+=dw*4
        assert len(e['SRAM_W'])==len(sram_expected),(ident,'actual SRAM write count')
        for (time,fields),(address,mask,offset,count) in zip(e['SRAM_W'],sram_expected):
            assert (int(fields[0]),int(fields[1],16))==(address,mask),(ident,'actual SRAM address/strobe',fields,address,mask)
            # Only enabled SRAM lanes are meaningful; unchanged upper lanes
            # in the last partial word can contain previous-chunk data.
            expected=bytearray(((offset+j)*37+11)&255 for j in range(count))
            if kind==1 and offset==0:expected[:4]=word.to_bytes(4,'little')
            assert (int(fields[2],16)&((1<<(count*8))-1))==int.from_bytes(expected,'little'),(ident,'SRAM enabled-byte data')
        # Final B errors retire but intermediate burst errors cannot finish.
        expected_responses=([2] if kind==5 else ([2] if kind==1 and ident==105 else [0]*b))
        if not fault:assert [int(f[1],16) for t,f in e['B']]==expected_responses
        if profile==1:assert ws>=23,(ident,'first W stall not exercised',ws)
        if profile==5:assert ws>200,(ident,'pending queue reset not exercised',ws)
        if profile==6:assert ws>=2998,(ident,'long multi-chunk W stall not exercised',ws)
        if profile in (3,4) and expected_beats>1:assert ws>0,(ident,'multi-beat W stalls not exercised')
        if profile in (2,4):assert aws>0,(ident,'AW delay not exercised')
        if kind==1:
            assert len(e['CAW'])==len(e['CW'])==1
            assert int(e['CAW'][0][1][0],16)==(dest-0x40010000)//4
            assert int(e['CW'][0][1][0],16)==word
            if ident==100:assert any(f==['3'] for t,f in e['BANK'])
            if ident==104:assert any(f==['0'] for t,f in e['BANK'])
        for channel in ('AW','W','B','MSI','POP','CREDIT','FETCH','TLP','SRAM_W'):
            totals[channel]+=len(e[channel])
        reports.append(dict(id=ident,kind=kind,bytes=byte_count,host_address=f'0x{host:016x}',
            result='PENDING_FAULT_NO_MSI' if fault else 'PASS',aw=aw,w=w,b=b,msi=msi,
            fifo_pops=pops,final_b_credits=credits,chunks=len(chunks),actual_mrd_tlps=len(tlp_expected),
            actual_sram_writes=len(sram_expected),
            w_stall_cycles=ws,aw_stall_cycles=aws,
            msi_after_final_b_ps=None if fault else e['MSI'][0][0]-e['B'][-1][0]))
    result=dict(status='H2F_CORRECTIONS_PASS_PENDING_INTEGRATION',cases=len(cases),
        fault_cases=sum(r['result']!='PASS' for r in reports),event_counts=dict(totals),case_results=reports,
        scope='actual controller, MRD segmenter, completion writer and official SRAM/FIFO/DRM; simulated external PCIe completer shell',
        independent_resets_supported=False,f2h_retirement_validated=False,linux_completion_validated=False)
    (ART/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def check_f2h_parity():
    cwd=ART/'candidate'
    tool([str(SIM/'vlog.exe'),'-work','work',str(ART/'baseline_controller.v')],cwd,'vlog_f2h_original')
    tool([str(SIM/'vlog.exe'),'-sv','-work','work',str(HERE/'tests/tb_f2h_controller_parity.sv')],cwd,'vlog_f2h_parity')
    text=tool([str(SIM/'vsim.exe'),'-c','-onfinish','stop','work.tb_fpga_v8_h2f_f2h_parity',
               '-do','run -all; quit -f'],cwd,'f2h_parity')
    match=re.search(r'F2H_CONTROLLER_PARITY_PASS transfers=(\d+) chunks=(\d+)',text)
    assert match and int(match[1])==4 and int(match[2])==305,text
    report=dict(status='PASS',transfers=int(match[1]),controller_chunks=int(match[2]),
                scope='F2H controller output parity only; FIFO TX/read suffix byte-identical; no posted-write retirement proof')
    (ART/'f2h_parity.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    args=argparse.ArgumentParser();args.add_argument('--baseline-only',action='store_true');opt=args.parse_args()
    ART.mkdir(exist_ok=True);before=immutable();(ART/'immutable_before.json').write_text(json.dumps(before,indent=2)+'\n')
    build();prepare();baseline,candidate=suites()
    audit_baseline(run_design('baseline',baseline))
    if not opt.baseline_only:
        result=audit_candidate(run_design('candidate',candidate),candidate)
        check_f2h_parity()
        print(result['status'],flush=True)
    after=immutable();assert before==after
    (ART/'immutable_after.json').write_text(json.dumps(after,indent=2)+'\n')
    print('Dependencies and previous completed contract unchanged.',flush=True)

if __name__=='__main__':main()
