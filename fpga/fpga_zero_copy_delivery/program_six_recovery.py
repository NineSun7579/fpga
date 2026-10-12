from pathlib import Path
import hashlib
import importlib.util
import json
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent))
import board_ssh

receipt = json.loads((root / 'six_bitstream_manifest.json').read_text())
image = Path(receipt['image'])
if receipt.get('return_code') != 0 or hashlib.sha256(image.read_bytes()).hexdigest() != receipt['sha256']:
    raise RuntimeError('Six-camera image identity failed')
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client,
        'test -z "$(ls /sys/bus/pci/devices)" && '
        '! pgrep -f "[d]etview" && '
        '! fuser /dev/pango_pci_driver 2>/dev/null', sudo=True, timeout=15)
    (root / 'six_program_preflight.log').write_text(out + err)
    if rc:
        raise RuntimeError('Recovery programming requires no PCI devices or viewer owners')
finally:
    client.close()
tcl = root / 'program_six_candidate.tcl'
tcl.write_text('cfg_scan_chain\ncfg_assign_file -file ' + image.as_posix() +
    ' -device_index 0\ncfg_program -device_index 0\n', encoding='ascii')
spec = importlib.util.spec_from_file_location('program_helper', root.parent / 'flash_repo_latest.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.TCL = str(tcl)
helper.LOG = str(root / 'six_program.log')
helper.JSLOG = str(root / 'six_program_js.log')
result = helper.main()
(root / 'six_program_manifest.json').write_text(json.dumps({
    'image': str(image), 'sha256': receipt['sha256'], 'return_code': result,
    'scope': 'SRAM only; SPI unchanged; absent PCI host preflight'}, indent=2))
raise SystemExit(result)
