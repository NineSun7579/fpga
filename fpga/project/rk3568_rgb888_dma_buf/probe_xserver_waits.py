"""Bounded read-only Xorg observation; tracing intervals are not FPS acceptance."""
import json,shlex,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
out=root/('xserver_waits_'+str(time.time_ns()));out.mkdir()
c=board_ssh.connect()
def run(cmd,name,timeout=20):
    rc,o,e=board_ssh.run(c,cmd,timeout=timeout,sudo=True)
    (out/name).write_text(o+e,encoding='utf-8')
    return rc,o,e
try:
    rc,o,e=run('cat /proc/sys/kernel/random/boot_id; pidof Xorg; fuser /dev/pango_pci_driver','identity.log')
    assert rc==0
    lines=o.splitlines();boot=lines[0];xp=int(lines[1]);vp=int(lines[2].strip())
    rc,o,e=run(f'sha256sum /proc/{vp}/exe; cat /proc/{xp}/stat; sha256sum /usr/lib/xorg/modules/drivers/modesetting_drv.so; dpkg-query -W xserver-xorg-core; readlink /proc/{vp}/fd/1','versions.log')
    assert '73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100' in o
    remote='/userdata/linaro/'+out.name+'.trace'
    cmd=f'timeout --signal=INT 5 strace -tt -T -yy -e trace=ioctl,poll,ppoll,select,pselect6,epoll_wait,recvmsg,sendmsg,futex -p {xp} -o '+shlex.quote(remote)
    rc,o,e=run(cmd,'trace_control.log',15)
    assert rc==124 and 'detached' in e
    with c.open_sftp() as s:s.get(remote,str(out/'xorg.trace'))
    cmds=['set pagination off','set debuginfod enabled off',f'attach {xp}','bt 24','detach']
    rc,o,e=run('gdb -q -nx -batch '+' '.join('-ex '+shlex.quote(x) for x in cmds),'xorg_stack.log',25)
    assert rc==0 and 'detached' in o+e
    rc,o,e=run(f'cat /proc/{xp}/status; cat /proc/{vp}/status; tail -40 /var/log/Xorg.0.log; tail -45 "$(readlink /proc/{vp}/fd/1)"','posttrace_health.log')
    (out/'receipt.json').write_text(json.dumps({'boot':boot,'xorg_pid':xp,'viewer_pid':vp,'trace_exit':124,'debugger_detached':True},indent=2))
    print(str(out));print((out/'xorg_stack.log').read_text()[-5500:])
finally:c.close()
