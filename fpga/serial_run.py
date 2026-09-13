#!/usr/bin/env python3
"""serial_run.py : 在 RK3568 串口控制台执行命令 (COM9 @1500000)
用法: python serial_run.py "command1" "command2" ...
每条命令等待提示符后输出。长命令可用 -t 秒数 调整超时。
"""
import serial, sys, time

PORT = 'COM9'
BAUD = 1500000

def open_port():
    s = serial.Serial(PORT, BAUD, timeout=0.3)
    s.reset_input_buffer()
    return s

def run(s, cmd, timeout=30):
    s.reset_input_buffer()
    s.write((cmd + '\n').encode())
    s.flush()
    t0 = time.time()
    buf = b''
    marker = b'__EOC__'
    s.write(b'echo __EOC__\n')  # 会在上一条执行完后排队
    while time.time() - t0 < timeout:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            if marker in buf.split(cmd.encode()+b'\n')[-1]:
                break
        else:
            # 再敲一次标记防止丢失
            s.write(b'echo __EOC__\n')
    s.reset_input_buffer()
    # 去掉回显与标记行
    text = buf.decode('utf-8', errors='replace')
    lines = [l for l in text.splitlines() if '__EOC__' not in l]
    return '\n'.join(lines)

if __name__ == '__main__':
    args = sys.argv[1:]
    timeout = 30
    if args and args[0] == '-t':
        timeout = int(args[1]); args = args[2:]
    s = open_port()
    for cmd in args:
        print(f'### {cmd}')
        print(run(s, cmd, timeout))
    s.close()
