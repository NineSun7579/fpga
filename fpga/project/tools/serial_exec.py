"""serial_exec.py -- run commands on the board's serial debug console (COM5 @ 1.5M).

Usage: python serial_exec.py "cmd1" "cmd2" ...
"""
import re
import sys
import time

import serial

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROMPT = b'root@linaro-alip:/#'
ANSI = re.compile(rb'\x1b\[[0-9;?]*[a-zA-Z]')


def open_port():
    ser = serial.Serial('COM5', 1500000, timeout=0.3)
    ser.reset_input_buffer()
    ser.write(b'\r')
    ser.flush()
    deadline = time.time() + 5
    while time.time() < deadline:
        if PROMPT in ser.read(4096):
            break
    return ser


def clean(b):
    b = ANSI.sub(b'', b)
    return b.decode('utf-8', 'replace')


def run(ser, cmd, timeout=25):
    ser.reset_input_buffer()
    ser.write((cmd + '\r').encode())
    ser.flush()
    buf = b''
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = ser.read(4096)
        if d:
            buf += d
            if PROMPT in buf.split(b'\r\n')[-1] or buf.rstrip().endswith(PROMPT):
                # prompt seen at end -> command finished
                break
        else:
            if buf and buf.rstrip().endswith(PROMPT):
                break
    text = clean(buf)
    # strip the echoed command + trailing prompt
    lines = text.splitlines()
    if lines and lines[0].strip() == cmd:
        lines = lines[1:]
    if lines and 'root@linaro-alip' in lines[-1]:
        lines = lines[:-1]
    return '\n'.join(lines)


def main():
    ser = open_port()
    try:
        for cmd in sys.argv[1:]:
            print('$ ' + cmd)
            print(run(ser, cmd))
            print('-' * 60)
    finally:
        ser.close()


if __name__ == '__main__':
    main()
