"""Candidate-only actual camera -> core -> generated-FIFO DDR regression."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import time

HERE=Path(__file__).resolve().parent
MIG=HERE.parent
PROJECT=MIG.parent
SIM=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
VENDOR=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
ART=HERE/'artifacts'
CASES={'small_leases':dict(width=16,height=16,out=24,top=4,mode=0,bursts=8),
       'small_reset':dict(width=32,height=16,out=24,top=4,mode=1,bursts=8),
       'full_640x480':dict(width=640,height=480,out=640,top=80,mode=0,bursts=32)}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def source_pixels(c,seed):
    # Immutable fixture contract shared with the sensor driver, never PNG.
    raw=bytearray()
    for y in range(c['height']):
        for x in range(c['width']):
            p=y*c['width']+x
            r=(p*7+seed*3+y)%32
            g=(p*11+seed*5+x)%64
            b=(p*13+seed*9+y*3)%32
            raw.extend((r*2048+g*32+b).to_bytes(2,'little'))
    return bytes(raw)

def software_prepare(raw,c):
    body=bytearray()
    for i in range(0,len(raw),2):
        word=int.from_bytes(raw[i:i+2],'little')
        r=(word>>11)&31; g=(word>>5)&63; b=word&31
        body.extend(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
    return bytes([114])*(c['width']*c['top']*3)+bytes(body)+bytes([114])*(
        c['width']*(c['out']-c['height']-c['top'])*3)

def inputs():
    fifo=[]
    for name in ['ov5640_ddr_fifo','ov5640_ddr_fifo_DRM','ddr_fifo16_w','ddr_fifo16_r']:
        root=PROJECT/'ipcore'/name
        fifo += [root/(name+'.v')]+sorted((root/'rtl').glob('ipm*.v'))
    primitives=[VENDOR/(n+'.v') for n in ['GTP_GRS','GTP_DRM18K_E1','GTP_DRM9K_E1',
                                          'GTP_DRM18K','GTP_DRM9K','GTP_DRM36K_E1']]
    rtl=[PROJECT/'source/ov5640/ov5640_ddr'/ (n+'.v') for n in
         ['ov5640_ddr_w','ov5640_ddr_w_ctrl','ov5640_ddr_w_en']]
    rtl += [PROJECT/'source/axi_dma/axi_dma_write.v',PROJECT/'source/axi_dma/stream_pipe.v']
    rtl += [PROJECT/'source/axi_crossbar'/(n+'.v') for n in
            ['axi_crossbar_rd','axi_crossbar_addr','axi_register_rd','arbiter','priority_encoder']]
    rtl += [MIG/p for p in ['capture_lease/fpga_v8_capture_lease.v',
                           'capture_lease/fpga_v8_capture_ov5640_ddr.v',
                           'raw_preprocess/fpga_v8_raw_letterbox.v',
                           'raw_preprocess/fpga_v8_rgb888_pack128.v',
                           'cooperative_axi/fpga_v8_raw_frame_axi.v',
                           'cooperative_control/fpga_v8_coop_control_axil.v',
                           'cooperative_arbiter/fpga_v8_ddr_write_arbiter.v',
                           'cooperative_core/fpga_v8_cooperative_core.v',
                           'ddr_adapter_contract/fpga_v8_ddr_adapter.v',
                           'ddr_adapter_contract/fpga_v8_top_read_route_snapshot.v']]
    return primitives+fifo+rtl

def pinned():
    # Preserve the finalized capture_lease WHOLE tree, including evidence.
    p=json.loads((MIG/'capture_lease/artifacts/production_scope_hashes_after.json').read_text())
    for name,value in p.items():
        if sha(Path(name))!=value: raise RuntimeError('Production 42-file pin changed: '+name)
    for f in (MIG/'capture_lease').rglob('*'):
        if f.is_file(): p[str(f)]=sha(f)
    for f in inputs()+[MIG/'ddr_adapter_contract/fpga_v8_vendor_ddr_stub.sv']:
        p[str(f)]=sha(f)
    return dict(sorted(p.items()))

def module_scan():
    wanted={b'fpga_v8_capture_contract_memory',b'tb_capture_core_contract'}
    found={name.decode():[] for name in wanted}
    for root in [PROJECT/'source',MIG]:
        for suffix in ['*.v','*.sv']:
            for path in root.rglob(suffix):
                if any(part in path.parts for part in ['artifacts','.venv','_attic']):continue
                raw=re.sub(rb'//[^\r\n]*|/\*.*?\*/',b'',path.read_bytes(),flags=re.S)
                for name in re.findall(rb'\bmodule\s+([A-Za-z_][A-Za-z_0-9$]*)',raw):
                    if name in wanted:found[name.decode()].append(str(path))
    if any(len(paths)!=1 for paths in found.values()):raise RuntimeError('Module collision: '+repr(found))
    return found

def run(args,d,name,commands,timeout=1200):
    start=time.monotonic()
    r=subprocess.run([str(x) for x in args],cwd=d,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    (d/(name+'.log')).write_bytes(r.stdout)
    text=r.stdout.decode(errors='replace')
    commands.append(dict(args=[str(x) for x in args],cwd=str(d),returncode=r.returncode,seconds=round(time.monotonic()-start,3)))
    if r.returncode or re.search(r'\*\* (?:Error|Fatal):',text):
        raise RuntimeError(name+': '+text[-9000:])
    return text

def main():
    from verify_contract import verify
    parser=argparse.ArgumentParser();parser.add_argument('--case',action='append',choices=CASES)
    opts=parser.parse_args();names=opts.case or list(CASES)
    ART.mkdir(exist_ok=True)
    before=pinned()
    manifest=ART/'immutable_hashes_before.json'
    if manifest.exists() and json.loads(manifest.read_text())!=before:
        raise RuntimeError('Immutable dependency tree differs from first run')
    if not manifest.exists(): manifest.write_text(json.dumps(before,indent=2)+'\n')
    scanned=module_scan()
    commands=[]
    build=ART/'build';build.mkdir(exist_ok=True)
    run([SIM/'vlib.exe','work'],build,'vlib',commands)
    run([SIM/'vlog.exe','-quiet','-work',build/'work',*inputs()],build,'compile_v2001',commands)
    run([SIM/'vlog.exe','-quiet','-sv','-work',build/'work',
         MIG/'ddr_adapter_contract/fpga_v8_vendor_ddr_stub.sv',
         HERE/'fpga_v8_capture_contract_memory.sv',HERE/'tb_capture_core_contract.sv'],build,'compile_tb',commands)
    result={}
    for name in names:
        c=CASES[name];d=ART/name;d.mkdir(exist_ok=True)
        text=run([SIM/'vsim.exe','-c','-quiet','-wlf','contract.wlf','-lib',build/'work',
                  'tb_capture_core_contract',f'-gWIDTH={c["width"]}',f'-gHEIGHT={c["height"]}',
                  f'-gOUT_HEIGHT={c["out"]}',f'-gTOP_ROWS={c["top"]}',f'-gMODE={c["mode"]}',
                  f'-gCAMERA_BURSTS={c["bursts"]}','-do','run -all; quit -f'],d,'simulate',commands)
        if 'CAPTURE_CORE_CONTRACT_PASS' not in text: raise RuntimeError('No positive completion: '+text[-5000:])
        result[name]=verify(d,c)
        print('PASS',name,json.dumps(result[name]['counts']),flush=True)
    after=pinned()
    (ART/'immutable_hashes_after.json').write_text(json.dumps(after,indent=2)+'\n')
    if after!=before: raise RuntimeError('Immutable source/capture_lease evidence changed')
    report=dict(scope='actual camera capture/core/adapter generated FIFO transaction-backed memory contract',
                physical_ddr_ip_simulated=False,production_42_hashes_unchanged=True,
                finalized_capture_lease_tree_unchanged=True,immutable_hash_count=len(after),
                unique_module_scan=scanned,
                source_sha256={str(p):sha(p) for p in inputs()},
                contract_sha256={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.sv']},
                cases=result,commands=commands)
    (ART/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CAPTURE_CORE_ALL_PASS cases='+str(len(result)),flush=True)

if __name__=='__main__': main()
