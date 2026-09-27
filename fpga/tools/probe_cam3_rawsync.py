from pathlib import Path
exec(Path('/tmp/probe_cam3_readonly.py').read_bytes().split(b'for sample in range(3):')[0])
for sample in range(2):
    print('RAW_VSYNC',sample,[(hex(base),read(base+0xe0)) for base in (0x20000000,0x20000200,0x20000400)],flush=True)
    if sample==0: time.sleep(2)
rx.close()
os.close(fd)
