# -*- coding: utf-8 -*-
"""flash_bg.py -- 后台烧录 + 轮询日志 + 主动关弹窗窗口
用法: python flash_bg.py <tcl文件>
策略: 杀净 cdt 进程 -> 起 cdt_js -> 后台跑 cdt_cfg(输出到临时文件)
     -> 轮询直到出现 Program] execute successfully 或超时 -> 关闭全部 cdt 窗口进程
"""
import subprocess, time, sys, os

tcl = sys.argv[1]
logf = os.path.join(os.environ['TEMP'], 'flash_bg_out.log')
errf = os.path.join(os.environ['TEMP'], 'flash_bg_err.log')

def kill_cdt():
    for exe in ('cdt_cfg.exe', 'cdt_js.exe'):
        subprocess.run(['taskkill', '-F', '/IM', exe], capture_output=True)

kill_cdt()
time.sleep(2)
subprocess.Popen(['powershell', '-NoProfile', '-Command',
 "Start-Process -FilePath 'C:/pango/PDS_2022.2-SP6.4/bin/cdt_js.exe' -ArgumentList '-port','65470' -WindowStyle Hidden"])
time.sleep(6)

with open(logf, 'w') as fo, open(errf, 'w') as fe:
    p = subprocess.Popen([r'C:\pango\PDS_2022.2-SP6.4\bin\cdt_cfg.exe',
                          '-ip', '127.0.0.1', '-port', '65470', '-file', tcl],
                         stdout=fo, stderr=fe)
    ok = False
    t0 = time.time()
    while time.time() - t0 < 180:
        time.sleep(3)
        try:
            txt = open(logf, encoding='gbk', errors='replace').read()
        except Exception:
            txt = ''
        if 'Program] execute successfully' in txt:
            ok = True
            break
        if p.poll() is not None and 'execute successfully' not in txt:
            break
    kill_cdt()          # 主动关闭弹窗窗口
    time.sleep(1)
    txt = open(logf, encoding='gbk', errors='replace').read()
    for ln in txt.splitlines():
        if any(k in ln for k in ('PGL', 'PG2L', 'done bit', 'E:', 'uccess')):
            print(ln.strip())
    print('FLASH_RESULT:', 'SUCCESS' if ok else 'FAILED')
    sys.exit(0 if ok else 1)
