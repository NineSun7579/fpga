"""Retire optional desktop processes; retain display/network/camera services."""
from pathlib import Path
import shlex,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
code=r'''
import pathlib,os,signal,json,subprocess,time
allowed={'blueman-applet','blueman-tray','Thunar','tracker-miner-f','light-locker'}
before=subprocess.check_output(['free','-m'],text=True)
targets=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        name=(p/'comm').read_text().strip()
        if name not in allowed:continue
        args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        status=(p/'status').read_text()
        rss=next((s for s in status.splitlines() if s.startswith('VmRSS:')),'')
        targets.append({'pid':int(p.name),'name':name,'args':args,'rss':rss})
        os.kill(int(p.name),signal.SIGTERM)
    except FileNotFoundError:pass
time.sleep(3)
result={'before':before,'targets':targets,'still_present':[t['pid'] for t in targets if pathlib.Path('/proc',str(t['pid'])).exists()],
        'after':subprocess.check_output(['free','-m'],text=True),'scope':'SIGTERM optional apps only; no service disabling or files removed'}
print(json.dumps(result,ensure_ascii=False,indent=2))
'''
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'python3 -c '+shlex.quote(code),timeout=25,sudo=True)
    (Path(__file__).resolve().parent/'background_trim_receipt.json').write_text(out,encoding='utf-8')
    print(out+err)
    if rc:raise RuntimeError('Process cleanup failed')
finally:client.close()
