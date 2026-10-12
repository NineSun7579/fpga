"""Independent ModelSim differential regression, no PDS or whole-system runner."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time
import sys

HERE = Path(__file__).resolve().parents[1]
PROJECT = HERE.parents[1]
REF = PROJECT / 'fpga_v8_migration/whole_candidate_v5_route_01/rtl/fpga_v8_capture_lease.v'
RTL = HERE / 'rtl/fpga_v8_capture_lease_tc04.v'
ART = HERE / 'receipts/lease'
MS = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def protected():
    roots = [PROJECT/'source', PROJECT/'fpga_v8_migration/whole_candidate_v5_route_01/rtl',
             PROJECT/'fpga_v8_migration/timing_correction_03/rtl',
             PROJECT/'fpga_v8_migration/capture_lease',
             PROJECT/'fpga_v8_migration/capture_arm_contract/lease']
    paths = {p for root in roots for p in root.rglob('*') if p.is_file() and
             not any(x in p.parts for x in ['artifacts','__pycache__'])}
    paths.add(PROJECT/'project/project.pds')
    return {str(p.relative_to(PROJECT)):sha(p) for p in sorted(paths)}


def bench():
    header=REF.read_bytes().decode('ascii').split(')(\n',1)[1].split('\n);',1)[0]
    ports=[]
    for decl in header.split(','):
        m=re.fullmatch(r'\s*(input|output)\s+(?:reg\s+)?(\[[^]]+\]\s*)?(\w+)\s*',decl)
        if not m: raise ValueError(decl)
        ports.append((m[1],m[2] or '',m[3]))
    outputs=[name for direction,width,name in ports if direction=='output']
    lines=['`timescale 1ns/1ps','module tb_lease_tc04;',
           'parameter HOST_REQUIRED=1, BAD_CFG=0;',
           'localparam VALID_CFG=(BAD_CFG==0);',
           'reg clk=0; always #5 clk=~clk;']
    for direction,width,name in ports:
        if name=='clk': continue
        if direction=='input': lines.append(f'reg {width}{name}=0;')
        else: lines.append(f'wire {width}ref_{name}, dut_{name};')
    params="""#(.HOST_REQUIRED(HOST_REQUIRED),
        .BANK1_ADDR(BAD_CFG==1 ? 32'h01800010 : BAD_CFG==2 ? 32'h0ffff000 :
                    BAD_CFG==3 ? 32'h01a00001 : 32'h01a00000),
        .CAM_DATA_LEN(BAD_CFG==4 ? 38401 : 38400),
        .DATA_WIDTH(BAD_CFG==5 ? 24 : 16),
        .RAW_LENGTH(BAD_CFG==6 ? 614384 : 614400),
        .CAM_ID(BAD_CFG==7 ? 6 : 4))"""
    for module,instance,prefix in [('fpga_v8_capture_lease','reference','ref'),
                                  ('fpga_v8_capture_lease_tc04','dut','dut')]:
        conns=[f'.{name}({prefix+"_"+name if direction=="output" else name})'
               for direction,width,name in ports]
        lines.append(f'{module} {params} {instance} (\n'+',\n'.join(conns)+'\n);')
    lines+=['task compare_outputs; begin']
    for name in outputs:
        lines.append(f'if(ref_{name} !== dut_{name}) $fatal(1,"output {name} cycle=%0d ref=%h dut=%h",cycles,ref_{name},dut_{name});')
    lines+=['if(!rst && (dut.writing_eligible !== (dut.state[dut.writing_bank]==1) ||',
            'dut.next_nonzero !== (dut.next_sequence!=0) ||',
            'dut.next_last !== (dut.next_sequence==32\'hffffffff))) $fatal(1,"predicate invariant");',
            'end endtask']
    body=(HERE/'tests/lease_stimulus.svh').read_text().replace('OUTPUT_COUNT',str(len(outputs)))
    lines += [body,'endmodule']
    return '\n'.join(lines)+'\n',outputs


def run():
    ART.mkdir(parents=True,exist_ok=True)
    evidence=PROJECT/'fpga_v8_migration/whole_candidate_v5_route_01/evidence/all_reported_failing_paths.json'
    paths=[x for x in json.loads(evidence.read_bytes()) if 'u_v8_capture_lease/' in x['Endpoint']]
    (ART/'v5_lease_failing_paths_full.json').write_text(json.dumps(paths,indent=2)+'\n')
    before=protected()
    (ART/'protected_before.json').write_text(json.dumps(before,indent=2)+'\n')
    # Byte-level collision scan, including GBK production sources.
    collisions=[]
    for root in [PROJECT/'source',PROJECT/'fpga_v8_migration']:
        for p in root.rglob('*.v'):
            if any(x in p.parts for x in ['receipts','artifacts','.venv','source_ascii']): continue
            if b'fpga_v8_capture_lease_tc04' in re.findall(rb'\bmodule\s+(\w+)',p.read_bytes()):
                collisions.append(str(p.resolve()))
    if collisions != [str(RTL.resolve())]: raise RuntimeError(collisions)
    build=ART/'build'; build.mkdir(exist_ok=True)
    tb,outputs=bench(); (build/'tb_lease_tc04.sv').write_text(tb,encoding='ascii')
    commands=[]
    def command(args,name):
        start=time.time()
        r=subprocess.run([str(x) for x in args],cwd=build,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        out=r.stdout.decode('utf-8',errors='replace')
        (ART/(name+'.log')).write_text(out,encoding='utf-8')
        commands.append(dict(args=[str(x) for x in args],cwd=str(build),returncode=r.returncode,seconds=round(time.time()-start,3)))
        if r.returncode or '** Error:' in out or '** Fatal:' in out: raise RuntimeError(out[-8000:])
        return out
    command([MS/'vlib.exe','work'],'vlib')
    command([MS/'vlog.exe','-quiet','-work','work',REF,RTL],'compile_verilog_2001')
    command([MS/'vlog.exe','-quiet','-sv','-work','work',build/'tb_lease_tc04.sv'],'compile_tb')
    results={}
    for host,bad in [(1,0),(0,0)]+[(1,k) for k in range(1,8)]:
        name=f'host{host}_bad{bad}'
        out=command([MS/'vsim.exe','-c','-quiet','-voptargs=+acc','-wlf',name+'.wlf',
                     'tb_lease_tc04',f'-gHOST_REQUIRED={host}',f'-gBAD_CFG={bad}',
                     '-do','run -all; quit -f'],name)
        marker=re.search(r'LEASE_TC04_DIFF_PASS[^\r\n]*',out)
        if not marker: raise RuntimeError(out[-8000:])
        results[name]=marker[0]; print(name,marker[0],flush=True)
    after=protected()
    (ART/'protected_after.json').write_text(json.dumps(after,indent=2)+'\n')
    if after!=before: raise RuntimeError('Protected bytes changed')
    report=dict(pass_all=True,candidate_sha256=sha(RTL),reference_sha256=sha(REF),
                public_outputs=outputs,compare_before_and_after_edge=True,
                protected_unchanged=True,protected_files=len(before),module_scan=collisions,
                timing_evidence_sha256=sha(evidence),lease_failing_paths=len(paths),
                commands=commands,results=results,
                test_sha256={p.name:sha(p) for p in (HERE/'tests').glob('*') if p.is_file()},
                limitations=['RTL differential simulation, not formal equivalence',
                             'No PDS synthesis/place/route; timing improvement unmeasured',
                             'Sequence/count boundary deposits preserve redundant invariants',
                             'No camera/DMA/whole-system simulation performed'])
    (ART/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': run()
