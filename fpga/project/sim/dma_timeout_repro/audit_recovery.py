from pathlib import Path
import re, subprocess, collections, hashlib
root=Path(__file__).resolve().parents[2]
here=Path(__file__).resolve().parent
vlog=Path('C:/modeltech64_10.6e/win64/vlog.exe')
report=[]
def say(s):report.append(s);print(s)
mods={}
for p in (root/'source').rglob('*.v'):
 for m in re.finditer(rb'\bmodule\s+(\w+)',p.read_bytes()):
  mods.setdefault(m[1],[]).append(p)
for name in [b'axi_dma_write',b'ov5640_ddr',b'ov5640_ddr_w',b'ov5640_ddr_w_ctrl',b'ov5640_top']:
 assert len(mods[name])==1,(name,mods[name])
say('PASS changed RTL module names unique in source/')
# Byte-level instance extraction, balanced parentheses, skipping comments.
def clean(s):return re.sub(rb'//[^\n]*|/\*.*?\*/',b'',s,flags=re.S)
def close(s,start):
 depth=0
 for i in range(start,len(s)):
  if s[i]==40:depth+=1
  if s[i]==41:
   depth-=1
   if depth==0:return i
 raise ValueError('unclosed')
instances=[]
for p in (root/'source').rglob('*.v'):
 s=clean(p.read_bytes())
 for m in re.finditer(rb'\baxi_dma_write\s*#\s*\(',s):
  if re.search(rb'module\s*$',s[max(0,m.start()-20):m.start()]):continue
  end=close(s,m.end()-1)
  inst=re.match(rb'\s*(\w+)\s*\(',s[end+1:]);assert inst
  start=end+1+inst.end()-1;stop=close(s,start)
  ports=dict(re.findall(rb'\.(\w+)\s*\(\s*([^()]*)\s*\)',s[start:stop+1]))
  assert b'abort_req' in ports and b'data_in_abort' in ports,(p,inst[1])
  instances.append((p,inst[1],ports))
  say(f'PASS DMA instance {p.relative_to(root)}:{inst[1].decode()} abort_req={ports[b"abort_req"].decode()} abort_out={ports[b"data_in_abort"].decode()}')
assert len(instances)==5,len(instances)
for cam in [b'cam',b'cam2',b'cam3']:
 s=(root/'source/top.v').read_bytes()
 for port,net in [(b'cam_dma_abort',cam+b'_dma_abort'),(b'cam_dma_abort_req',cam+b'_dma_abort_req')]:
  assert re.search(rb'\.'+port+rb'\s*\(\s*'+net+rb'\s*\)',s)
say('PASS all three camera wrapper fault paths connected at top')
for p in (root/'source').rglob('*.frame_recovery.bak'):
 new=p.with_name(p.name.removesuffix('.frame_recovery.bak'))
 oldlines=p.read_bytes().splitlines();newlines=new.read_bytes().splitlines()
 assert [l for l in oldlines if any(c>=128 for c in l)] == [l for l in newlines if any(c>=128 for c in l)],new
 assert [l for l in oldlines if b'SENSOR_PLL_MULT' in l] == [l for l in newlines if b'SENSOR_PLL_MULT' in l],new
 say(f'PASS GBK non-ASCII lines and SENSOR_PLL_MULT preserved: {new.relative_to(root)} SHA256={hashlib.sha256(new.read_bytes()).hexdigest()}')
results=[]
for label,path in [('baseline',root/'source/top.v.frame_recovery.bak'),('current',root/'source/top.v')]:
 cmd=[str(vlog),'-work','work_recovery',str(path)]
 r=subprocess.run(cmd,cwd=here,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (here/f'top_{label}_compile.log').write_bytes(r.stdout)
 errors=re.findall(rb'\*\* Error[^\n]*',r.stdout)
 # Compare error content, omitting file and line number.
 signatures=collections.Counter(re.sub(rb'^.*?\(vlog-',b'(vlog-',e) for e in errors)
 results.append(signatures)
 say(f'Top ModelSim compile {label}: return={r.returncode}, errors={len(errors)}')
assert results[0]==results[1],(results[1]-results[0],results[0]-results[1])
say('PASS top compile error signatures identical to pre-edit baseline; top cannot be claimed ModelSim-clean')
r=subprocess.run([str(vlog),'-work','work_recovery',str(root/'source/ov5640/ov5640_top.v'),str(root/'source/axi_dma/axi_dma.v')],cwd=here,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(here/'wrapper_compile.log').write_bytes(r.stdout)
assert r.returncode==0,r.stdout
say('PASS ov5640_top and generic axi_dma wrappers compile')
(here/'audit_recovery.log').write_text('\n'.join(report)+'\n',encoding='utf-8')
