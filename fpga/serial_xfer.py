#!/usr/bin/env python3
"""serial_xfer.py v2: 串口逐块确认传输 (可靠) + md5 校验
用法: python serial_xfer.py <本地文件> <板上路径>
"""
import serial, sys, time, base64, hashlib, math

PORT = 'COM9'
BAUD = 1500000
CHUNK = 1400
NL = b'\n'

def open_port():
    s = serial.Serial(PORT, BAUD, timeout=0.05)
    s.reset_input_buffer()
    s.write(NL); time.sleep(0.3); s.reset_input_buffer()
    return s

def run(s, cmd, timeout=30):
    s.reset_input_buffer()
    s.write(cmd.encode() + NL); s.flush()
    t0 = time.time(); buf = b''
    while time.time() - t0 < timeout:
        c = s.read(8192)
        if c:
            buf += c
            if b'__RDY__' in buf.split(cmd.encode())[-1]:
                break
    s.reset_input_buffer()
    text = buf.decode('utf-8', errors='replace')
    return '\n'.join(l for l in text.splitlines() if '__RDY__' not in l)

def send_chunk(s, chunk, path, seq):
    line = "printf '%s' '" + chunk + "' >> " + path + ".b64; echo ACK" + str(seq) + "$?"
    for attempt in range(4):
        s.reset_input_buffer()
        s.write(line.encode() + NL); s.flush()
        t0 = time.time(); buf = b''
        want = ('ACK' + str(seq)).encode()
        while time.time() - t0 < 5:
            c = s.read(4096)
            if c:
                buf += c
                if want in buf:
                    return True
        s.write(("truncate -s -" + str(len(chunk)) + " " + path + ".b64 2>/dev/null" + chr(10)).encode())
    return False

def main(src, dst):
    data = open(src, 'rb').read()
    md5 = hashlib.md5(data).hexdigest()
    b64 = base64.b64encode(data).decode()
    nch = math.ceil(len(b64) / CHUNK)
    print(f"transfer {len(data)} B -> {dst} ({nch} chunks)")
    s = open_port()
    print(run(s, "mkdir -p $(dirname " + dst + "); rm -f " + dst + ".b64 " + dst + "; stty -echo; echo READY"))
    t0 = time.time()
    for i in range(nch):
        chunk = b64[i*CHUNK:(i+1)*CHUNK]
        if not send_chunk(s, chunk, dst, i):
            print(f"CHUNK {i} FAILED"); s.close(); return 1
        if i % 40 == 0:
            print(f"  {i}/{nch} {time.time()-t0:.0f}s")
    dt = time.time() - t0
    out = run(s, "base64 -d " + dst + ".b64 > " + dst + " && md5sum " + dst, timeout=120)
    run(s, "rm -f " + dst + ".b64")
    print(f"transfer {dt:.0f}s")
    if md5 in out:
        print(f"VERIFY OK {dst} md5={md5}")
        s.close(); return 0
    print(f"VERIFY FAILED expect={md5}")
    print(out[-300:])
    s.close(); return 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
