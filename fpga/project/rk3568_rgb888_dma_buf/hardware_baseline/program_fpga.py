"""Program candidate into SRAM after coordinated PCIe removal, leave SPI intact."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
background='--background' in sys.argv
original='--restore-display30' in sys.argv
project=root/('integrated_six_background/project' if background else 'integrated_six_batch/project' if '--batch' in sys.argv else 'integrated_six/project' if '--six-camera' in sys.argv else 'integrated/project')
image=project/'generate_bitstream/top.sbit'
if original:
    image=root.parent/'bitstream_cam5_fix_20261008/top.sbit'
    if hashlib.sha256(image.read_bytes()).hexdigest()!='fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122':
        raise RuntimeError('Original production archive identity mismatch')
if not original and (not image.is_file() or 'All Constraints Met' not in (project/'place_route/top_timing_summary_after_hold_fix.txt').read_text()):
    raise RuntimeError('Missing bitstream or passing timing')
prefix='six_background_' if background else 'six_batch_' if '--batch' in sys.argv else 'six_' if '--six-camera' in sys.argv else ''
if original: prefix='original_display30_'
if '--batch' in sys.argv or background:
    generated=json.loads((root/(prefix+'bitstream_manifest.json')).read_text())
    timing=project/'place_route/top_timing_summary_after_hold_fix.txt'
    if (generated.get('status')!='finished' or generated.get('return_code')!=0 or
        generated.get('sha256')!=hashlib.sha256(image.read_bytes()).hexdigest() or
        generated.get('timing_sha256')!=hashlib.sha256(timing.read_bytes()).hexdigest()):
        raise RuntimeError('Batch image/timing identity does not match generation receipt')
    build=json.loads((root/(prefix+'pds_manifest.json')).read_text())
    if build.get('status')!='finished' or build.get('return_code')!=0:
        raise RuntimeError('Batch build receipt is not successful')
    for relative,expected in build['inputs'].items():
        if Path(relative).name=='project.pds':
            continue  # PDS rewrites project output metadata during generation.
        if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Batch source changed after build: '+relative)
manifest={'image':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'scope':'SRAM only; SPI unchanged'}
(root/(prefix+'program_manifest.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
tcl=root/'program_candidate.tcl'
tcl.write_text('cfg_scan_chain\ncfg_assign_file -file '+image.as_posix()+' -device_index 0\ncfg_program -device_index 0\n',encoding='ascii')
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'fuser /dev/pango_pci_driver',sudo=True)
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('Device still owned; FPGA programming not started')
    command=('driver=$(basename "$(readlink /sys/bus/pci/devices/0002:21:00.0/driver)"); '
        'test "$driver" = pango_pci_driver -o "$driver" = pango_zc || exit 2; '
        'echo 0002:21:00.0 > /sys/bus/pci/drivers/$driver/unbind && '
        'echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove')
    if '--post-reboot' in sys.argv:
        command='test ! -e /sys/bus/pci/devices/0002:21:00.0'
    rc,out,err=board_ssh.run(client,command,sudo=True)
    (root/(prefix+'program_preflight.log')).write_text(out+err,encoding='utf-8')
    if rc:
        raise RuntimeError('PCIe removal failed')
    spec=importlib.util.spec_from_file_location('program_helper',root.parent/'flash_repo_latest.py')
    helper=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.TCL=str(tcl); helper.LOG=str(root/(prefix+'program.log')); helper.JSLOG=str(root/(prefix+'program_js.log'))
    if helper.main()!=0:
        raise RuntimeError('FPGA programming failed; endpoint left removed')
    recovery=('if [ ! -e /sys/bus/platform/devices/3c0800000.pcie/driver ]; then '
              'echo 3c0800000.pcie > /sys/bus/platform/drivers/rk-pcie/bind || exit 2; fi; '
              'echo 1 > /sys/bus/pci/rescan; '
              'for attempt in $(seq 1 50); do '
              'test -e /sys/bus/pci/devices/0002:21:00.0 && break; sleep 0.1; done; '
              'test -e /sys/bus/pci/devices/0002:21:00.0 || exit 4; '
              'if [ ! -d /sys/bus/pci/drivers/pango_zc ]; then '
              'insmod /userdata/linaro/fpga-zero-copy-driver-stage/pango_zc.ko vendor_id=0x0755 device_id=0x0755 || exit 3; fi; '
              'for attempt in $(seq 1 50); do '
              'test -L /sys/bus/pci/devices/0002:21:00.0/driver && break; sleep 0.1; done; '
              'test -L /sys/bus/pci/devices/0002:21:00.0/driver || '
              'echo 0002:21:00.0 > /sys/bus/pci/drivers/pango_zc/bind; '
              'readlink /sys/bus/pci/devices/0002:21:00.0/driver && lspci -s 0002:21:00.0')
    rc,out,err=board_ssh.run(client,recovery,sudo=True)
    (root/(prefix+'program_rescan.log')).write_text(out+err,encoding='utf-8')
    if rc:
        raise RuntimeError('PCIe rescan failed')
    print(out+err)
finally:
    client.close()
