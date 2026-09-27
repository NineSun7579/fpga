from pathlib import Path
import re,hashlib,json,difflib,subprocess,collections
p=Path(__file__).resolve().parent;root=p.parents[1]
report=[]
def say(s):report.append(s);print(s)
files=list((root/'source').rglob('*.burst_credit.bak'));assert len(files)==6
diff=[]
for backup in files:
 current=backup.with_name(backup.name.removesuffix('.burst_credit.bak'))
 old=backup.read_bytes();new=current.read_bytes()
 for predicate in [lambda l:any(c>=128 for c in l),lambda l:b'SENSOR_PLL_MULT' in l]:
  assert list(filter(predicate,old.splitlines()))==list(filter(predicate,new.splitlines())),current
 say('PASS preserved non-ASCII/PLL bytes '+str(current.relative_to(root)))
 diff.extend(difflib.unified_diff(old.decode('gbk','replace').splitlines(True),new.decode('gbk','replace').splitlines(True),fromfile=str(backup.relative_to(root)),tofile=str(current.relative_to(root))))
(p/'burst_credit_source.diff').write_bytes(''.join(diff).encode('utf-8'))
protected=json.loads((p/'throughput_protected_hashes.json').read_bytes())
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in protected.items())
say(f'PASS all {len(protected)} vendor/IP files byte-identical')
top=(root/'source/top.v').read_bytes()
assert top.count(b'.WAIT_FOR_DATA(1)')==3
for cam in [b'cam',b'cam2',b'cam3']:
 for port in [b'cam_s_data_available',b'data_in_available']:
  assert len(re.findall(rb'\.'+port+rb'\('+cam+rb'_s_data_available\)',top))==1
say('PASS three camera credit nets connected through top and camera-only WAIT_FOR_DATA enabled')
for path in [root/'source/top.v',root/'source/axi_dma/axi_dma.v']:
 b=path.read_bytes()
 assert len(re.findall(rb'\.data_in_available\(16\'d0\)',b))==1
say('PASS non-camera DMA inputs explicitly tied off')
# A pre-existing ModelSim top.v declaration-order issue is compared by signature.
exe='C:/modeltech64_10.6e/win64/vlog.exe';results=[]
for name,path in [('before',root/'source/top.v.burst_credit.bak'),('after',root/'source/top.v')]:
 r=subprocess.run([exe,'-work','work_credit_vendor',str(path)],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (p/('credit_top_'+name+'.log')).write_bytes(r.stdout)
 errors=re.findall(rb'\*\* Error[^\n]*',r.stdout)
 results.append(collections.Counter(re.sub(rb'^.*?\(vlog-',b'(vlog-',e) for e in errors))
 say(f'Top ModelSim {name}: exit={r.returncode}, errors={len(errors)}')
assert results[0]==results[1],(results[1]-results[0],results[0]-results[1])
say('PASS whole-top error signatures unchanged (not a clean whole-top compile)')
r=subprocess.run([exe,'-work','work_credit_vendor',str(root/'source/ov5640/ov5640_top.v'),str(root/'source/axi_dma/axi_dma.v')],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(p/'credit_wrappers.log').write_bytes(r.stdout);assert r.returncode==0,r.stdout
say('PASS camera and generic DMA wrappers compile')
(p/'audit_burst_credit.log').write_bytes(('\n'.join(report)+'\n').encode())
