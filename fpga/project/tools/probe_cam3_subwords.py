from pathlib import Path
exec(Path('/tmp/probe_cam3_readonly.py').read_bytes().split(b'for sample in range(3):')[0])
for sample in range(2):
    for base in (0x20000000,0x20000200,0x20000400):
        print(sample,hex(base),[(hex(o),hex(read(base+o))) for o in (4,8,12)],flush=True)
    if sample==0: time.sleep(2)
rx.close(); os.close(fd)
