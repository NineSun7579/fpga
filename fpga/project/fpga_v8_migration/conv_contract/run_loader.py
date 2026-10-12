from run_sim import HERE, RTL, MS, command, words, mem, layout
import json
import numpy as np


def run(name,k,use11):
    d=HERE/name
    d.mkdir(exist_ok=True)
    rng=np.random.default_rng(651+k)
    w=rng.integers(-128,128,(3,3,k,k),dtype=np.int16).astype(np.int8)
    bp=layout.pack_biases([0x00098000,-0x00234567,0x01020304],16)
    wp=layout.pack_weights(w)
    mem(d/'parameter_image.mem',words(bp+wp))
    command([MS/'vlib.exe','work'],d,'vlib')
    sources=[RTL/'common/spram_D.v',RTL/'common/sync_fifo.v',RTL/'common/fifo_ram.v',
             RTL/'conv/conv_weight.v',RTL/'conv11_16/conv11_weight.v',HERE/'tb_contract_loader.v']
    command([MS/'vlog.exe','-quiet','-work','work',*sources],d,'compile')
    text=command([MS/'vsim.exe','-c','-quiet','-wlf','contract.wlf','-l','transcript.log',
                  '-gK='+str(k),'-gUSE11='+str(use11),'work.tb_contract_loader',
                  '-do','run -all; quit -f'],d,'simulate')
    if 'CONTRACT_LOADER_DONE' not in text:raise RuntimeError('loader did not finish')
    rows=[l.split() for l in (d/'loader_observed.txt').read_text().splitlines()]
    wr=[r for r in rows if r[0]=='W'];br=[r for r in rows if r[0]=='B']
    actual=[];last=[];unknown=[];invalid_last=[]
    for r in wr:
        _,cy,v,l,*taps=r
        if v not in {'0','1'} or l not in {'0','1'}:unknown.append(r);continue
        if l=='1':
            last.append(len(actual))
            if v!='1':invalid_last.append(r)
        if v=='1':
            used=taps if k==3 else [taps[4]]
            if any(x in ''.join(used).lower() for x in 'xz'):unknown.append(r);actual.append(None)
            else:actual.append([int(x,16) for x in used])
    packed_words=words(wp)
    expected=[]
    for g in range(8):
        for lane in range(2):expected.append([packed_words[g*k*k*2+t*2+lane] for t in range(k*k)])
    mismatch=[dict(index=i,got=None if a is None else [f'{v:032x}' for v in a],expected=[f'{v:032x}' for v in e])
              for i,(a,e) in enumerate(zip(actual,expected)) if a!=e]
    bexpected=[]
    for i in range(8):
        pair=bp[i*16:i*16+16]
        bexpected.append(int.from_bytes(pair[:4],'little')|int.from_bytes(pair[8:12],'little')<<32)
    bactual=[]
    for r in br:
        if r[2]!='1' or r[3]!='1' or any(c in r[4].lower() for c in 'xz'):unknown.append(r)
        else:bactual.append(int(r[4],16))
    result=dict(name=name,k=k,use11=use11,expected_weight_beats=16,actual_weight_beats=len(actual),
                mismatch_count=len(mismatch),first_mismatches=mismatch[:4],
                actual_last_indices=last,expected_last_indices=list(range(1,16,2)),
                last_without_valid=invalid_last,unknown_events=unknown,
                expected_bias_beats=8,actual_bias_beats=len(bactual),bias_matches=bactual==bexpected,
                commands=[r for r in rows if r[0]=='C'],
                pass_exact=actual==expected and last==list(range(1,16,2)) and not invalid_last and not unknown and bactual==bexpected)
    (d/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(name,'weight',len(actual),'/16 mismatches',len(mismatch),'bias',len(bactual),'/8 pass',result['pass_exact'],flush=True)
    return result


if __name__=='__main__':
    results=[run('loader3',3,0),run('loader1',1,0),run('loader11',1,1)]
    (HERE/'loader_results.json').write_text(json.dumps(results,indent=2)+'\n')
    if not all(r['pass_exact'] for r in results):raise SystemExit(1)
