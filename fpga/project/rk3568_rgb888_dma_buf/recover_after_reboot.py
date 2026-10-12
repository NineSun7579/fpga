"""Restore recorded original module/viewer after reboot and SRAM programming."""
from pathlib import Path
import json
import argparse
import shlex
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--evidence',default='reboot_original_recovery')
parser.add_argument('--display30',action='store_true',help='Restore historical display-fix EGL environment')
args=parser.parse_args()
evidence=(root/args.evidence).resolve()
evidence.relative_to(root)
receipt=json.loads((root/'deploy_1791567760719372300/receipt.json').read_text())
if args.display30:
    receipt['baseline']['env'].update(QT_QPA_PLATFORM='xcb',QT_XCB_GL_INTEGRATION='xcb_egl')
program_log=(evidence/'restore.jtag.log').read_text(errors='replace')
assert 'The done bit is 1' in program_log and 'COMMAND[Program] execute successfully' in program_log
code=r'''
import os,subprocess,hashlib,json,time
from pathlib import Path
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot!=RECEIPT['baseline']['boot_id'],'Reboot not verified'
owner=subprocess.run(['fuser','/dev/pango_pci_driver'],capture_output=True)
assert not owner.stdout.strip(),'Existing owner; preserve runtime'
module=RECEIPT['original_module']['module']
assert hashlib.sha256(Path(module).read_bytes()).hexdigest()==RECEIPT['original_module']['sha256']
if Path('/sys/module/pango_zc').exists():
    assert Path('/sys/module/pango_zc/refcnt').read_text().strip()=='0'
    subprocess.run(['rmmod','pango_zc'],check=True)
subprocess.run(['insmod',module,'vendor_id=0x0755','device_id=0x0755'],check=True)
host=Path('/sys/bus/platform/devices/3c0800000.pcie')
if not (host/'driver').exists():Path('/sys/bus/platform/drivers/rk-pcie/bind').write_text(host.name)
Path('/sys/bus/pci/rescan').write_text('1')
time.sleep(2)
assert Path('/dev/pango_pci_driver').exists(),'PCI device unavailable'
baseline=RECEIPT['baseline']; exe=baseline['identity']['exe']
assert hashlib.sha256(Path(exe).read_bytes()).hexdigest()==RECEIPT['artifacts']['active_sha256']
remote='/userdata/linaro/ov56401-reboot-original-'+str(time.time_ns())
os.makedirs(remote+'/tmp')
env=baseline['env']; env['TMPDIR']=remote+'/tmp'
env['DISPLAY']=':0'
env['XAUTHORITY']='/var/run/lightdm/root/:0'
for name in ('DETVIEW_FPGA_INFER_RGB','DETVIEW_FPGA_INFER_VERIFY'):env.pop(name,None)
log=open(remote+'/original.log','wb')
p=subprocess.Popen(baseline['argv'],cwd=baseline['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'boot_id':boot,'pid':p.pid,'remote':remote,'module_sha256':RECEIPT['original_module']['sha256']}))
'''
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'python3 -c '+shlex.quote('RECEIPT='+repr(receipt)+'\n'+code),timeout=45,sudo=True)
    (evidence/'runtime_receipt.json').write_text(out if rc==0 else json.dumps({'error':out+err}),encoding='utf-8')
    print(out+err)
    if rc:raise RuntimeError('Recovery gate failed')
finally:client.close()
