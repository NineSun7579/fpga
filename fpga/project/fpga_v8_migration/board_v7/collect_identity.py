"""Collect non-DMA runtime identity; never opens the FPGA driver."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import board_ssh

command = '''sha256sum /userdata/linaro/projects/fpga/RK3568/pango_pci_driver.ko /userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko
od -An -tx1 /sys/module/pango_pci_driver/notes/.note.gnu.build-id
cat /proc/2583/maps
ls -l /proc/2583/fd
cat /proc/interrupts | grep -E 'MSI|pango|PCI'
lspci -vv -s 0002:21:00.0
'''
c = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(c, command, sudo=True, timeout=20)
    target = Path(__file__).resolve().parent / 'run_20261006_134504_c9abdebb/runtime/loaded_identity.txt'
    target.write_text(out + '\n' + err, encoding='utf-8')
    print(out[:2400])
    print(err[:300])
finally:
    c.close()
