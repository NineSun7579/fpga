from pathlib import Path
import subprocess,hashlib,json,re
R=Path(__file__).resolve().parent;W=R.parents[2];B=Path('C:/modeltech64_10.6e/win64')
T=W/'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl';A=R.parent/'sfp_align';P=R.parent/'sfp_payload_probe'
def run(args,name):
 p=subprocess.run([str(x) for x in args],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 t=p.stdout.decode(errors='replace');(R/name).write_text(t)
 if p.returncode:raise RuntimeError(name)
 return t
def writevector(name,syms):
 with (R/(name+'.vec')).open('w') as f:
  # End with the beginning of the next control rather than invented D payload.
  syms=syms+[(0xbc,1),(0x28,0),(0,0),(0xbc,1)][:(-len(syms))%4]
  for i in range(0,len(syms),4):
   c=syms[i:i+4];f.write(f'{sum(b<<(j*8) for j,(b,k) in enumerate(c)):08x} {sum(k<<j for j,(b,k) in enumerate(c)):x}\n')
def main():
 (R/'input.hex').write_bytes((P/'input.hex').read_bytes())
 (R/'capture.sv').write_bytes((P/'capture.sv').read_bytes())
 for lib in ['txwork','oldwork','currentwork']:run([B/'vlib.exe',lib],lib+'_vlib.log')
 run([B/'vlog.exe','-sv','-work','txwork',T/'video_async_fifo.v','candidate_sfp_video_tx.v','capture.sv'],'capture_compile.log')
 run([B/'vsim.exe','-c','txwork.capture','-do','onbreak {quit -code 1 -force};run -all;quit -code 0 -force'],'capture.log')
 for lib,link in [('oldwork',A/'results_before_fix/sfp_rx_link_before_fix.v'),('currentwork',W/'project/source/sfp/sfp_rx_link.v')]:
  run([B/'vlog.exe','-sv','-work',lib,A/'hsst_sfp_stub.v',link,W/'project/source/sfp/sfp_video_rx.v',A/'tb_sfp_align.v'],lib+'_compile.log')
 words=[tuple(int(t,16) for t in l.split()) for l in (R/'actual.vec').read_text().splitlines()]
 syms=[((d>>(j*8))&255,(k>>j)&1) for d,k in words for j in range(4)]
 pairs=[i for i in range(len(syms)-1) if syms[i:i+2]==[(0xbc,1),(0x50,0)]]
 assert pairs and all(i%4 in [0,2] and words[i//4]==(0x50bc50bc,5) for i in pairs)
 guards=sum((d,k)==(0xffbcffbc,5) for d,k in words);data=sum(k==0 for d,k in words)
 assert guards==data==307200,(guards,data)
 gold=[int(l,16) for l in (R/'input.hex').read_text().splitlines()]
 # Events at both halves of a dedicated skip word, before payload and blank SOF.
 skipwords=pairs[::2];stride=max(1,len(skipwords)//128)
 selected=[base+2*(j%2) for j,base in enumerate(skipwords[::stride][:128])]
 assert all(b-a>2 for a,b in zip(selected,selected[1:])), 'must model isolated two-byte phase changes'
 results=[]
 for kind in ['baseline','delete','insert']:
  targets=set(selected);mut=[]
  for i,s in enumerate(syms):
   if kind=='delete' and (i in targets or i-1 in targets):continue
   if kind=='insert' and i in targets:mut.extend([(0xbc,1),(0x50,0)])
   mut.append(s)
  for offset in range(4):
   name=f'{kind}_{offset}';writevector(name,[(0xc5,0)]*offset+mut)
   for lib in ['oldwork','currentwork']:
    text=run([B/'vsim.exe','-c','-voptargs=+acc',lib+'.tb_sfp_align',f'+VECTOR={name}.vec',f'+PIXELS={lib}_{name}.pixels',f'+TRACE={lib}_{name}.trace','-do','onbreak {quit -code 1 -force};run -all;quit -code 0 -force'],f'{lib}_{name}.log')
    m=re.search(r'RESULT pixels=(\d+) frame_pixels=(\d+) sof=(\d+) controls=(\d+) relocks=(\d+) overflow=(\d+)',text)
    row=dict(zip(['pixels','frame_pixels','sof','controls','relocks','overflow'],map(int,m.groups())))
    observed=[int(l,16) for l in (R/f'{lib}_{name}.pixels').read_text().splitlines()]
    row.update(kind=kind,offset=offset,receiver=lib,exact=observed==gold,events=0 if kind=='baseline' else len(targets))
    results.append(row);print(json.dumps(row),flush=True)
    if kind!='baseline':assert row['relocks']>=len(targets), 'missing two-byte phase-change coverage'
 (R/'summary.json').write_text(json.dumps(dict(guards=guards,data_words=data,skip_pairs=len(pairs),skip_matches_only_dedicated=True,results=results),indent=2))
 for p,h in json.loads((R/'manifest.json').read_text()).items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
 assert all(r['exact'] and r['sof']==1 and r['overflow']==0 for r in results), 'see summary.json for failed guard transport case'
if __name__=='__main__':main()
