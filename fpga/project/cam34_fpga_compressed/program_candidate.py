# Verified SRAM-only programming, with exact owner retirement and rollback.
from pathlib import Path
import argparse,importlib.util,json,shlex,hashlib,subprocess,socket,time,os
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--rollback',action='store_true');a=p.parse_args()
spec=importlib.util.spec_from_file_location('board',root.parent/'board_ssh.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
if a.rollback:
 image=root.parent/'rk3568_rgb888_dma_buf/hardware_baseline/rollback/top.sbit'
 assert hashlib.sha256(image.read_bytes()).hexdigest()=='fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122'
else:
 receipt=json.loads((root/'bitstream_receipt.json').read_bytes());assert receipt['status']=='finished'and receipt['return_code']==0
 image=Path(receipt['image']);assert image.resolve().is_relative_to(root.resolve())
 assert hashlib.sha256(image.read_bytes()).hexdigest()==receipt['sha256']
 inputs=json.loads((root/'build_inputs.json').read_bytes())['changed']
 for relative,digest in inputs.items():
  if Path(relative).name!='project.pds':assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==digest,'RTL changed after verified build'
 timing=root/'project/place_route/top_timing_summary_after_hold_fix.txt';assert 'All Constraints Met' in timing.read_text(errors='replace')
 assert hashlib.sha256(timing.read_bytes()).hexdigest()==receipt['timing_sha256']
 assert 'Design Summary : All Constraints Met.' in (root/'project/report_timing/top.rtr').read_text(errors='replace')
check=subprocess.run(['powershell','-NoProfile','-Command','@(Get-Process pds,pds_shell,cdt_cfg,cdt_js -ErrorAction SilentlyContinue).Count'],capture_output=True,text=True)
assert check.stdout.strip()=='0','PDS/JTAG busy; do not change hardware'
port=65425;probe=socket.socket();probe.bind(('127.0.0.1',port));probe.close()
evidence=root/('rollback_program' if a.rollback else 'program');evidence.mkdir(exist_ok=True)
c=b.connect()
def run(code,timeout=45):
 rc,o,e=b.run(c,'python3 -c '+shlex.quote(code),timeout=timeout,sudo=True)
 if rc:raise RuntimeError(o+e[-1800:])
 return o
try:
 expected=json.loads((root/'baseline/private_launch.json').read_bytes())
 helper='/userdata/linaro/ov56401-cam34-wire-lifecycle.py'
 prefix='import importlib.util,json,os,subprocess,time\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location("life",'+repr(helper)+');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n'
 code=prefix+'''owners=m.owners()
if owners:
 ids=[m.identity(pid) for pid in owners];assert len(ids)==1
 exp=EXPECTED['identity']
 if ids[0]!=exp:raise RuntimeError('Viewer ownership changed; preserve unknown current viewer')
 print(json.dumps(m.stop({'identity':exp,'env':EXPECTED['env'],'timeout':30})))
m.retired()
if m.PCI.exists():print(json.dumps(m.remove({})))
else:print('ENDPOINT_ALREADY_REMOVED')
'''
 if a.rollback:
  candidate=json.loads((root/'viewer_build/manifest.json').read_bytes())
  code=prefix+'''owners=m.owners()
if owners:
 assert len(owners)==1;ident=m.identity(owners[0])
 assert ident['exe']==CANDIDATE['executable']and ident['sha256']==CANDIDATE['executable_sha256']
 print(json.dumps(m.stop({'identity':ident,'env':EXPECTED['env'],'timeout':30})))
m.retired()
if m.PCI.exists():print(json.dumps(m.remove({})))
'''
  code='CANDIDATE='+repr(candidate)+'\n'+code
 result=run('EXPECTED='+repr(expected)+'\n'+code);(evidence/'retirement.log').write_text(result,encoding='utf-8');print(result,flush=True)
 tcl=evidence/'program_sram.tcl';tcl.write_text('cfg_scan_chain\ncfg_assign_file -file '+image.as_posix()+' -device_index 0\ncfg_program -device_index 0\n',encoding='ascii')
 bin=Path(r'C:/pango/PDS_2022.2-SP6.4/bin');flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
 jslog=(evidence/'jtag_server.log').open('wb');cfglog=(evidence/'jtag_config.log').open('wb')
 js=subprocess.Popen([str(bin/'cdt_js.exe'),'-port',str(port)],stdout=jslog,stderr=subprocess.STDOUT,creationflags=flags);cfg=None
 try:
  time.sleep(5)
  cfg=subprocess.Popen([str(bin/'cdt_cfg.exe'),'-ip','127.0.0.1','-port',str(port),'-file',str(tcl)],stdout=cfglog,stderr=subprocess.STDOUT,creationflags=flags)
  start=time.monotonic();done=False
  while time.monotonic()-start<240:
   text=(evidence/'jtag_config.log').read_text(errors='replace')
   if 'The done bit is 1' in text and 'COMMAND[Program] execute successfully' in text:done=True;break
   if cfg.poll()is not None:break
   time.sleep(2)
  assert done,'JTAG SRAM programming failed; endpoint stays removed'
  print('SRAM_PROGRAM_CONFIRMED',flush=True)
 finally:
  for process in [cfg,js]:
   if process is not None and process.poll()is None:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  cfglog.close();jslog.close()
 code=prefix+'''assert m.MODULE.exists()
host=Path('/sys/bus/platform/devices/3c0800000.pcie')
if not(host/'driver').exists():Path('/sys/bus/platform/drivers/rk-pcie/bind').write_text(host.name)
Path('/sys/bus/pci/rescan').write_text('1')
for _ in range(100):
 if m.PCI.exists()and(m.PCI/'driver').exists():break
 time.sleep(.1)
assert m.PCI.exists()
if not(m.PCI/'driver').exists():Path('/sys/bus/pci/drivers/pango_zc/bind').write_text(m.BDF)
assert(m.PCI/'driver').resolve().name=='pango_zc'
fd=os.open(m.DEVICE,os.O_RDWR|os.O_SYNC);os.close(fd)
print(json.dumps({'pci':m.BDF,'driver':'pango_zc','device_open':'OK','boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}))
'''
 result=run(code);(evidence/'rescan.log').write_text(result,encoding='utf-8');print(result,flush=True)
 (evidence/'receipt.json').write_text(json.dumps({'image':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'scope':'SRAM only; original SPI Flash unchanged','status':'programmed_and_pci_restored','baseline_executable_preserved':expected['identity']['exe']},indent=2),encoding='utf-8')
 if a.rollback:
  code='EXPECTED='+repr(expected)+'\n'+prefix+'''m.retired()
ex=EXPECTED['identity']['exe'];assert m.digest(ex)==EXPECTED['identity']['sha256']
env=EXPECTED['env'];env.update(DISPLAY=':0',XAUTHORITY='/var/run/lightdm/root/:0',QT_QPA_PLATFORM='xcb',QT_XCB_GL_INTEGRATION='xcb_egl',TMPDIR='/userdata/linaro/ov56401-cam34-wire-trial/tmp')
log=open('/userdata/linaro/ov56401-cam34-wire-trial/restored_original.log','wb')
p=subprocess.Popen(EXPECTED['argv'],cwd=EXPECTED['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'restored_pid':p.pid,'exe':ex}))
'''
  print(run(code),flush=True)
finally:c.close()
