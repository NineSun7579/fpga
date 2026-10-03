"""Isolated actual TX capture and byte/K mutation replay; no physical PCS model."""
from pathlib import Path
import hashlib, json, subprocess, re
ROOT=Path(__file__).resolve().parent
WS=ROOT.parents[2]
BIN=Path('C:/modeltech64_10.6e/win64')
TX=WS/'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
RX=WS/'project/source/sfp'
ALIGN=WS/'project/sim/sfp_align'

def run(args,name):
    p=subprocess.run([str(x) for x in args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    text=p.stdout.decode(errors='replace'); (ROOT/name).write_text(text)
    if p.returncode: raise RuntimeError(name)
    return text

def main():
    a=(WS/'log/six_50k_pins_fixed_board_20261003/cam5.rgb565').read_bytes()
    assert len(a)==640*480*2
    golden=[]
    for y in range(480):
        golden.extend(int.from_bytes(a[2*(y*640+x):2*(y*640+x)+2],'little') for x in range(640))
        # Alternating dark rows and adversarial BC/50 + BC/28 + all values.
        golden.extend((0 if y%3==0 else 0x50bc if y%3==1 else ((x+y*640)&65535)) for x in range(640))
    (ROOT/'input.hex').write_text(''.join(f'{p:04x}\n' for p in golden))
    source=TX/'sfp_video_tx.v'
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,RX/'sfp_rx_link.v',RX/'sfp_video_rx.v']}
    for lib in ['txwork','rxwork']: run([BIN/'vlib.exe',lib],lib+'_vlib.log')
    run([BIN/'vlog.exe','-sv','-work','txwork',TX/'video_async_fifo.v',source,'capture.sv'],'capture_compile.log')
    run([BIN/'vsim.exe','-c','txwork.capture','-do','onbreak {quit -code 1 -force}; run -all; quit -code 0 -force'],'capture.log')
    run([BIN/'vlog.exe','-sv','-work','rxwork',ALIGN/'hsst_sfp_stub.v',RX/'sfp_rx_link.v',RX/'sfp_video_rx.v',ALIGN/'tb_sfp_align.v'],'replay_compile.log')
    words=[tuple(int(t,16) for t in l.split()) for l in (ROOT/'actual.vec').read_text().splitlines()]
    syms=[((d>>(8*j))&255,(k>>j)&1) for d,k in words for j in range(4)]
    pairs={}
    for val in [0x28,0x50]:
        pos=[i for i in range(len(syms)-1) if syms[i:i+2]==[(0xbc,1),(val,0)]]
        pairs[f'BC{val:02X}']=dict(total=len(pos),cross_word=sum(i%4==3 for i in pos))
    payload=0; targets=[]; last_ctrl=None
    for i,(d,k) in enumerate(words):
        if k==9: last_ctrl=i
        if k==0:
            # Last control before one two-pixel word in B, every fourth row.
            if payload%1280==640 and payload//1280%4==0:
                assert last_ctrl is not None and last_ctrl==i-1
                targets.append(last_ctrl*4)
            payload+=2
    assert payload==614400
    results=[]
    cases={'baseline':[], 'delete_BC28_before_B':targets,
           'delete_BC50_matches': [i for i in range(len(syms)-1) if syms[i:i+2]==[(0xbc,1),(0x50,0)]]}
    # Also mutate an earlier control to distinguish deletion position.
    cases['delete_BC28_earlier_B']=[i-4 for i in targets if words[i//4-1][1]==9]
    for name,positions in cases.items():
        deleted=set(j for i in positions for j in [i,i+1])
        vector=ROOT/(name+'.vec')
        with vector.open('w') as f:
            chunk=[]
            for i,s in enumerate(syms):
                if i in deleted: continue
                chunk.append(s)
                if len(chunk)==4:
                    f.write(f'{sum(b<<(8*j) for j,(b,k) in enumerate(chunk)):08x} {sum(k<<j for j,(b,k) in enumerate(chunk)):x}\n');chunk=[]
            if chunk:
                chunk += [(0xc5,0)]*(4-len(chunk))
                f.write(f'{sum(b<<(8*j) for j,(b,k) in enumerate(chunk)):08x} {sum(k<<j for j,(b,k) in enumerate(chunk)):x}\n')
        text=run([BIN/'vsim.exe','-c','-voptargs=+acc','rxwork.tb_sfp_align',f'+VECTOR={name}.vec',f'+PIXELS={name}.pixels',f'+TRACE={name}.trace','-do','run -all; quit -code 0 -force'],name+'.log')
        m=re.search(r'RESULT pixels=(\d+) frame_pixels=(\d+) sof=(\d+) controls=(\d+) relocks=(\d+) overflow=(\d+)',text)
        row=dict(zip(['pixels','frame_pixels','sof','controls','relocks','overflow'],map(int,m.groups())))
        observed=[int(l,16) for l in (ROOT/(name+'.pixels')).read_text().splitlines()]
        row.update(case=name,deleted_pairs=len(positions),exact=observed==golden,first_mismatch=next((i for i,(a,b) in enumerate(zip(observed,golden)) if a!=b),None))
        results.append(row); print(json.dumps(row),flush=True)
        if name=='baseline': assert row['exact'] and row['sof']==1 and row['overflow']==0
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (ROOT/'summary.json').write_text(json.dumps(dict(hashes=hashes,pairs=pairs,results=results),indent=2))

if __name__=='__main__': main()
