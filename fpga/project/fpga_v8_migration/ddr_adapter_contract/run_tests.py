"""Read-only production/IP inspection and isolated actual-FIFO simulations."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
MIGRATION=ROOT.parent
PROJECT=MIGRATION.parent
SIM=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
TOP=PROJECT/'source/top.v'
TOP_HASH='dca00ca2ecbc0b1418a32fc9abb09c673e522960a0150ef568f1e528a1681347'
FIFO_SOURCES=[]
for side in ['w','r']:
    directory=PROJECT/f'ipcore/ddr_fifo16_{side}'
    FIFO_SOURCES += [directory/f'ddr_fifo16_{side}.v'] + sorted((directory/'rtl').glob('*.v'))
RTL=FIFO_SOURCES + [MIGRATION/'raw_preprocess/fpga_v8_raw_letterbox.v',MIGRATION/'raw_preprocess/fpga_v8_rgb888_pack128.v',
    MIGRATION/'cooperative_axi/fpga_v8_raw_frame_axi.v',MIGRATION/'cooperative_control/fpga_v8_coop_control_axil.v',
    MIGRATION/'cooperative_arbiter/fpga_v8_ddr_write_arbiter.v',MIGRATION/'cooperative_core/fpga_v8_cooperative_core.v',
    ROOT/'fpga_v8_ddr_adapter.v',ROOT/'fpga_v8_top_read_route_snapshot.v',ROOT/'fpga_v8_top_bid_snapshot.v']
TB=[MIGRATION/'cooperative_core/tb_fpga_v8_cooperative_core.sv',ROOT/'fpga_v8_vendor_ddr_stub.sv',ROOT/'tb_core_ddr_adapter.sv',ROOT/'tb_ddr_adapter_contract.sv']
CASES={
    'directed_actual_fifo':dict(top='tb_ddr_adapter_contract'),
    'original_bid_failure':dict(top='tb_core_ddr_adapter',width=4,height=3,out=5,toprows=1,mode=4,bursts=24,legacy=1),
    'core_leases_actual_fifo':dict(top='tb_core_ddr_adapter',width=4,height=3,out=5,toprows=1,mode=0,bursts=24,legacy=0),
    'core_reset_actual_fifo':dict(top='tb_core_ddr_adapter',width=5,height=3,out=6,toprows=1,mode=2,bursts=24,legacy=0),
    'core_full_actual_fifo':dict(top='tb_core_ddr_adapter',width=640,height=480,out=640,toprows=80,mode=4,bursts=512,legacy=0),
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def vectors(c,seq):
    raw=bytearray();body=bytearray()
    for y in range(c['height']):
        for x in range(c['width']):
            p=y*c['width']+x;r=(p*7+seq*3+y)%32;g=(p*11+seq*5+x)%64;b=(p*13+seq*9+y*3)%32
            raw.extend((r*2048+g*32+b).to_bytes(2,'little'))
            body.extend((r*8+r//4,g*4+g//16,b*8+b//4))
    raw.extend(bytes([0xd7])*((-len(raw))%16))
    expected=bytes([114])*(c['toprows']*c['width']*3)+body+bytes([114])*((c['out']-c['toprows']-c['height'])*c['width']*3)
    return bytes(raw),bytes(expected)
def camera_expected(bursts):
    return bytes((o*37+t*19+b*11+l*7)%256 if b<(16,3,5,1)[t%4] else 0xa5
                 for o in range(6) for t in range(bursts) for b in range(16) for l in range(16))
def run(argv,directory,log):
    p=subprocess.run(argv,cwd=directory,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
    (directory/log).write_bytes(p.stdout)
    if p.returncode:raise RuntimeError(f'{argv}:\n{p.stdout.decode(errors="replace")[-6000:]}')
def compare(path,expected):
    actual=path.read_bytes()
    if actual!=expected:raise AssertionError(f'{path.name} complete bytes differ, lengths {len(actual)}/{len(expected)}')
    return dict(bytes=len(actual),sha256=sha(path))
def vendor_trace(path,c):
    active=None;words=0;camera_words=0;output_words=0;aws=0
    for line in path.read_text().splitlines():
        fields=line.split()
        if fields[0]=='RESET':active=None
        elif fields[0]=='AW':
            if active is not None:raise AssertionError('overlapping vendor AW')
            active=dict(address=int(fields[1],16),ident=int(fields[2]),beats=int(fields[3]),count=0);aws+=1
            if not 1<=active['beats']<=16:raise AssertionError('vendor length truncation')
        elif fields[0]=='W':
            address,ident,word,strobe,last=int(fields[1],16),int(fields[2]),int(fields[3],16),int(fields[4],16),int(fields[5])
            if active is None or address!=active['address']+active['count']*16 or ident!=active['ident'] or last!=(active['count']+1==active['beats']):raise AssertionError(f'vendor W order/ID/last {line}')
            data=word.to_bytes(16,'little')
            if 'width' in c:
                if 0x01000000<=address<0x01600000:
                    owner=(address-0x01000000)//0x00100000;tx=(address-(0x01000000+owner*0x00100000))//256;beat=(address%256)//16
                    expected=bytes((owner*37+tx*19+beat*11+lane*7)%256 for lane in range(16))
                    if data!=expected or strobe!=0xffff or ident!=owner+8:raise AssertionError(f'vendor camera complete W mismatch {line}')
                    camera_words+=1
                else:
                    if ident!=1:raise AssertionError('output ID not preserved')
                    output_words+=1
            else:
                tx=5 if active['address']==0x0ffffff0 else (active['address']-0x00200000)//256
                expected=bytes((tx*31+active['count']*7+lane*5)%256 for lane in range(16))
                if data!=expected or strobe!=(0x07ff if last else 0xffff):raise AssertionError(f'directed vendor complete W mismatch {line}')
            active['count']+=1;words+=1
            if last:active=None
        elif fields[0]=='AR':
            if not 1<=int(fields[3])<=16:raise AssertionError('vendor AR length truncation')
        else:raise AssertionError(f'unknown vendor trace {line}')
    if active is not None:raise AssertionError('final vendor write not retired')
    return dict(vendor_aw_count=aws,vendor_w_words=words,camera_w_words=camera_words,output_w_words=output_words)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',action='append',choices=CASES);args=parser.parse_args()
    names=args.case or list(CASES);artifact=ROOT/'artifacts';artifact.mkdir(exist_ok=True)
    assert sha(TOP)==TOP_HASH,'production top hash changed'
    # Read GBK production text as bytes; preserve exact original source evidence.
    top_bytes=TOP.read_bytes();lines=top_bytes.splitlines(keepends=True)
    selected=[(238,268),(508,576),(578,655)]
    (artifact/'production_glue_excerpt.bin').write_bytes(b''.join(b''.join(lines[a-1:b]) for a,b in selected))
    inspected=dict(top_sha256=TOP_HASH,excerpt_ranges=selected,top_bid_assignment=lines[523].decode('gbk').strip(),
        write_fifo_wr_en=lines[241].decode('gbk').strip(),read_route_assignment=lines[267].decode('gbk').strip())
    sources=RTL+TB+[Path(__file__).resolve(),TOP,PROJECT/'ipcore/ddr3/ddr3.v']
    hashes={str(p.relative_to(PROJECT)).replace('\\','/'):sha(p) for p in sources}
    report=dict(python=sys.executable,modelsim=str(SIM),fifo_status='actual unmodified generated FIFO RTL compiled and simulated',vendor_ddr_status='behavioral scheduling stub; physical DDR3 IP not simulated',production_inspection=inspected,source_sha256=hashes,cases=[])
    for name in names:
        c=CASES[name];d=artifact/name;d.mkdir(exist_ok=True)
        if 'width' in c:
            for seq in range(1,6):
                raw,golden=vectors(c,seq)
                for prefix,data in [('source',raw),('golden',golden)]:
                    (d/f'{prefix}_{seq}.hex').write_text(''.join(f'{b:02x}\n' for b in data),encoding='ascii')
        run([str(SIM/'vlib.exe'),'work'],d,'vlib.log')
        compile_rtl=[str(SIM/'vlog.exe'),'-work','work']+[str(p) for p in RTL]
        compile_tb=[str(SIM/'vlog.exe'),'-work','work','-sv']+[str(p) for p in TB]
        run(compile_rtl,d,'compile_rtl.log');run(compile_tb,d,'compile_tb.log')
        (d/'run.do').write_text('onerror {quit -code 1}\nonbreak {quit -code 0}\nrun -all\nquit -code 0\n',encoding='ascii')
        generics=[]
        if 'width' in c:
            generics=[f'-gWIDTH={c["width"]}',f'-gHEIGHT={c["height"]}',f'-gOUT_HEIGHT={c["out"]}',f'-gTOP_ROWS={c["toprows"]}',f'-gMODE={c["mode"]}',f'-gCAMERA_BURSTS={c["bursts"]}',f'-gLEGACY_BID={c["legacy"]}']
        sim=[str(SIM/'vsim.exe'),'-c','-onfinish','stop','-voptargs=+acc','-l','transcript.log']+generics+[f'work.{c["top"]}','-do','run.do']
        run(sim,d,'console.log');text=(d/'console.log').read_text(errors='replace')
        if re.search(r'\*\* (Error|Fatal):|CORE_FAIL',text):raise AssertionError(f'{name}:\n{text[-6000:]}')
        if name=='original_bid_failure':
            required=['ORIGINAL_BID_FAILURE_CONFIRMED'];outputs=[]
        elif name=='directed_actual_fifo':
            required=['ADAPTER_DIRECTED_PASS','ORIGINAL_WREN_FULL_SAFE','ORIGINAL_READ_ROUTE_SAFE','VENDOR_ID_FAULT_PASS'];outputs=[]
            records=(d/'read_trace.txt').read_text().splitlines()
            if len(records)!=39:raise AssertionError('complete directed R trace length')
            for line in records:
                _,rid,address,data,last=line.split();address=int(address,16)
                expected=bytes(((address>>4)*13+lane*17+31)%256 for lane in range(16))
                if int(data,16).to_bytes(16,'little')!=expected or int(rid,16)>>4 not in (0,2,5):raise AssertionError('all directed R bytes/SIDs')
        else:
            required=['ADAPTER_CORE_PASS','CORE_PASS'];outputs=[]
            seqs=[1,2,3] if c['mode']==0 else [5] if c['mode']==2 else [1]
            for seq in seqs:outputs.append(dict(seq=seq,**compare(d/f'output_{seq}.bin',vectors(c,seq)[1])))
            vendor_output=compare(d/'vendor_output.bin',vectors(c,seqs[-1])[1])
            if c['mode']==0:compare(d/'vendor_output1.bin',vectors(c,2)[1])
            compare(d/'vendor_camera.bin',camera_expected(c['bursts']))
            compare(d/'camera_output.bin',camera_expected(c['bursts']))
        for marker in required:
            if marker not in text:raise AssertionError(f'missing {marker}: {name}\n{text[-5000:]}')
        markers=[line.removeprefix('# ') for line in text.splitlines() if any(marker in line for marker in required)]
        audit=vendor_trace(d/'vendor_trace.txt',c)
        report['cases'].append(dict(name=name,parameters=c,pass_markers=markers,outputs=outputs,vendor_trace=audit,compile_rtl=compile_rtl,compile_tb=compile_tb,simulation=sim))
        (artifact/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='ascii')
        print(f'PASS {name}: '+', '.join(markers),flush=True)
    assert {str(p.relative_to(PROJECT)).replace('\\','/'):sha(p) for p in sources}==hashes,'read-only dependency changed during regression'
    assert sha(TOP)==TOP_HASH
    report['production_and_dependency_hashes_unchanged']=True
    report['total_host_output_compared_bytes']=sum(o['bytes'] for c in report['cases'] for o in c['outputs'])
    (artifact/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='ascii')
if __name__=='__main__':main()
