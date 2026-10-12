"""Isolated ModelSim execution and strict complete-stream independent comparison."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import argparse
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
RTL = PROJECT / 'source/npu'
MS = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
VENDOR = Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
spec = importlib.util.spec_from_file_location('hwc16_readonly', HERE.parent / 'hwc16_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


def command(args, cwd, tag):
    # System modelsim.ini maps work to a mutable relative library. Keep an
    # explicit local mapping so concurrent agent simulations cannot alter it.
    ini = cwd / 'modelsim.ini'
    if not ini.exists():
        ini.write_text('[Library]\nwork = '+(cwd/'work').as_posix()+'\nothers = '+(MS.parent/'modelsim.ini').as_posix()+'\n')
    args=list(args)
    if Path(args[0]).name.lower() in {'vlog.exe','vsim.exe'}:
        args[1:1]=['-modelsimini',ini.as_posix()]
    r = subprocess.run([str(a) for a in args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    s = r.stdout.decode('utf-8', errors='replace')
    (cwd / (tag + '.log')).write_text(s)
    if r.returncode or '** Error' in s or 'CONTRACT_TIMEOUT' in s:
        raise RuntimeError(tag + '\n' + s[-6000:])
    return s


def mem(path, words, width=32):
    path.write_text(''.join(f'{int(w):0{width}x}\n' for w in words))


def words(data):
    return [int.from_bytes(data[i:i+16], 'little') for i in range(0,len(data),16)]


def make_case(name, k, ci, co, use11=0, model_task=None):
    d = HERE / name
    d.mkdir(exist_ok=True)
    rng = np.random.default_rng(1000+k+ci+co)
    if model_task is None:
        w = rng.integers(-128,128,(co,ci,k,k),dtype=np.int16).astype(np.int8)
        w[0,0,0,0] = -128
        w[1,0,0,0] = 127
    else:
        with np.load(HERE.parent / f'numeric_layer/task_{model_task:03d}.npz') as f:
            w = f['weight'].copy()
        co,ci,k,_=w.shape
    ib=(ci+15)//16
    width=256
    zero=23
    data = rng.integers(0,256,(ib,3,width+2,16),dtype=np.uint8)
    data[:,:,0,:]=zero;data[:,:,-1,:]=zero
    # 256 consecutive interior pixels cover every u8 code on every lane.
    for b in range(ib):
        for y in range(3):
            for lane in range(16):
                data[b,y,1:-1,lane]=(np.arange(256,dtype=np.int32)+y*17+lane*13+b*29)%256
    if ib*16>ci:
        data[-1,:,:,ci%16:]=zero
    packed=layout.pack_weights(w)
    if model_task is not None:
        packed=(HERE.parent / f'legacy_hwc16/assets/task_{model_task:03d}_weight.bin').read_bytes()
    (d/'weights.bin').write_bytes(packed)
    mem(d/'weights.mem',words(packed))
    for y in range(3): mem(d/f'data{y}.mem',words(data[:,y].tobytes()))
    expected=[]
    shifted=[]
    switched_tail=[]
    for ob in range((co+15)//16*8):
        for b in range(ib):
            for x in range(width):
                lanes=[]
                shifted_lanes=[]
                tail_lanes=[]
                for lane in range(2):
                    oc=ob*2+lane
                    acc=0
                    shifted_acc=0
                    if oc<co:
                        for ic in range(b*16,min((b+1)*16,ci)):
                            for ky in range(k):
                                for kx in range(k):
                                    dy=ky if k==3 else 1
                                    dx=x+kx if k==3 else x+1
                                    acc += int(w[oc,ic,ky,kx])*int(data[b,dy,dx,ic%16])
                                    # Diagnostic only: official APM bypasses P_REG with USE_POSTADD=0.
                                    # The final tail contains the explicitly driven idle zero sample.
                                    shifted_acc += int(w[oc,ic,ky,kx])*(int(data[b,dy,dx+1,ic%16]) if dx+1<width+2 else 0)
                    lanes.append(acc & 0xffffff)
                    shifted_lanes.append(shifted_acc & 0xffffff)
                    tail_acc=shifted_acc
                    if x==width-1:
                        gid=ob*ib+b
                        next_gid=gid+1 if gid+1<(co+15)//16*8*ib else gid-1
                        next_oc=(next_gid//ib)*2+lane
                        next_ib=next_gid%ib
                        tail_acc=0
                        if next_oc<co:
                            for il in range(16):
                                next_ic=next_ib*16+il
                                if next_ic>=ci:continue
                                for ky in range(k):
                                    for kx in range(k):
                                        dy=ky if k==3 else 1
                                        dx=x+kx+1 if k==3 else x+2
                                        tail_acc+=int(w[next_oc,next_ic,ky,kx])*(int(data[b,dy,dx,il]) if dx<width+2 else 0)
                    tail_lanes.append(tail_acc & 0xffffff)
                expected.append(lanes[0] | lanes[1]<<24)
                shifted.append(shifted_lanes[0] | shifted_lanes[1]<<24)
                switched_tail.append(tail_lanes[0] | tail_lanes[1]<<24)
    mem(d/'expected.mem',expected,12)
    mem(d/'diagnostic_one_pixel_ahead.mem',shifted,12)
    mem(d/'diagnostic_one_pixel_ahead_switched_tail.mem',switched_tail,12)
    return d, dict(name=name,k=k,ci=ci,co=co,ib=ib,width=width,use11=use11,model_task=model_task), expected


def run_case(d,c,expected,candidate_latency=False):
    command([MS/'vlib.exe','work'],d,'vlib')
    multipliers=[RTL/'conv/conv_mul_E2.v',RTL/'conv11_16/conv11_mul_E2.v']
    if candidate_latency:
        copies=[]
        for source in multipliers:
            raw=source.read_bytes()
            old=b'localparam DELAY = MUL_DELAY - 3;'
            if raw.count(old)!=1:raise RuntimeError('unexpected source latency declaration')
            dest=d/source.name
            dest.write_bytes(raw.replace(old,b'localparam DELAY = MUL_DELAY - 2;'))
            copies.append(dest)
        multipliers=copies
    sources=[VENDOR/'GTP_GRS.v',VENDOR/'GTP_APM_E2.v',multipliers[0],RTL/'conv/conv_conv.v',
             multipliers[1],RTL/'conv11_16/conv11_conv.v',HERE/'tb_contract_mac.v']
    command([MS/'vlog.exe','-quiet','-work','work',*sources],d,'compile')
    s=command([MS/'vsim.exe','-c','-quiet','-wlf','contract.wlf','-l','transcript.log',
               '-gK='+str(c['k']),'-gCI='+str(c['ci']),'-gCO='+str(c['co']),'-gIB='+str(c['ib']),
               '-gUSE11='+str(c['use11']),'-gW='+str(c['width']),
               'work.tb_contract_mac','-do','run -all; quit -f'],d,'simulate')
    if 'CONTRACT_MAC_DONE' not in s: raise RuntimeError('missing complete marker')
    events=[line.split() for line in (d/'mac_observed.txt').read_text().splitlines()]
    actual=[];last_indices=[];invalid_last=[];unknown=[]
    for cy,v,l,value in events:
        if v not in {'0','1'} or l not in {'0','1'}:
            unknown.append([cy,v,l,value]);continue
        if l=='1':
            if v!='1':invalid_last.append(int(cy))
            last_indices.append(len(actual))
        if v=='1':
            if any(x in value.lower() for x in 'xz'):
                unknown.append([cy,v,l,value]);actual.append(None)
            else:actual.append(int(value,16))
    mismatch=[dict(index=i,got=None if a is None else f'{a:012x}',expected=f'{e:012x}')
              for i,(a,e) in enumerate(zip(actual,expected)) if a!=e]
    desired_last=[(g+1)*c['width']-1 for g in range(8*((c['co']+15)//16)*c['ib'])]
    shifted=[int(s,16) for s in (d/'diagnostic_one_pixel_ahead.mem').read_text().splitlines()]
    switched_tail=[int(s,16) for s in (d/'diagnostic_one_pixel_ahead_switched_tail.mem').read_text().splitlines()]
    result=dict(**c,production_wrappers_unmodified=not candidate_latency,
                expected_valid_words=len(expected),actual_valid_words=len(actual),
                unknown_events=unknown[:10],unknown_count=len(unknown),mismatch_count=len(mismatch),
                first_mismatches=mismatch[:12],expected_last_indices=desired_last,
                actual_last_indices=last_indices,last_without_valid=invalid_last,
                pass_exact=len(actual)==len(expected) and not mismatch and not unknown and not invalid_last and last_indices==desired_last,
                diagnostic_all_words_match_one_pixel_ahead=actual==shifted,
                diagnostic_all_words_match_one_pixel_ahead_next_bank_tail=actual==switched_tail,
                first_actual=[None if a is None else f'{a:012x}' for a in actual[:8]])
    (d/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(c['name'], 'valid',len(actual),'/',len(expected),'mismatches',len(mismatch),'last',last_indices[:4], 'PASS',result['pass_exact'],flush=True)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate-latency',action='store_true',help='test local wrapper copies with one additional output register; production untouched')
    args=parser.parse_args()
    cases=[('mac3_ci3_co3',3,3,3,0,None),('mac1_ci3_co3',1,3,3,0,None),
           ('mac11_ci3_co3',1,3,3,1,None),('mac3_ci19_co3',3,19,3,0,None),
           ('mac_model_task000',3,3,16,0,0)]
    results=[]
    for case in cases:
        if args.candidate_latency:case=(case[0]+'_candidate',*case[1:])
        d,c,expected=make_case(*case)
        results.append(run_case(d,c,expected,args.candidate_latency))
    (HERE/('candidate_latency_results.json' if args.candidate_latency else 'simulation_results.json')).write_text(json.dumps(results,indent=2)+'\n')
    if not all(r['pass_exact'] for r in results):
        raise SystemExit(1)


if __name__=='__main__':main()
