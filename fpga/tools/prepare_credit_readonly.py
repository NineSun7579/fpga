from pathlib import Path
root = Path(__file__).resolve().parents[1]
data = (root/'tools/diagnose_recovery_readonly.py').read_bytes()
data = data.replace(b'recovery_readonly_diag', b'credit_readonly_repeat')
data = data.replace(b'range(21)', b'range(61)').replace(b'time.sleep(0.25)', b'time.sleep(0.5)')
data = data.replace(b'd=PciDriver()', b"from pathlib import Path\nassert Path('/sys/bus/pci/devices/0002:21:00.0/driver').is_symlink()\nd=PciDriver()")
(root/'tools/credit_readonly_repeat.py').write_bytes(data)
