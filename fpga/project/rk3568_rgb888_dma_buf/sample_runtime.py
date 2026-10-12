"""Sample process CPU and runtime evidence for a bounded observation window."""
from pathlib import Path
import argparse,json,shlex,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('pid',type=int);parser.add_argument('label');parser.add_argument('log')
parser.add_argument('--seconds',type=int,default=30)
args=parser.parse_args()
if not 1 <= args.seconds <= 1800:parser.error('--seconds must be 1..1800')
assert args.label.replace('_','').isalnum()
code=r'''
import pathlib,time,os,json
pid=PID
def measure():
    text=pathlib.Path('/proc',str(pid),'stat').read_text().split(') ',1)[1].split()
    status=pathlib.Path('/proc',str(pid),'status').read_text().splitlines()
    memory={line.split(':',1)[0]:int(line.split()[1]) for line in status if line.startswith(('VmRSS:','VmHWM:'))}
    return {'wall':time.monotonic(),'ticks':int(text[11])+int(text[12]),'start':text[19],**memory}
start=measure()
observed_rss=[start.get('VmRSS',0)]
for i in range(SAMPLE_SECONDS):
    time.sleep(1)
    point=measure();assert point['start']==start['start']
    observed_rss.append(point.get('VmRSS',0))
end=measure();assert start['start']==end['start']
print(json.dumps({'pid':pid,'seconds':end['wall']-start['wall'],'cpu_seconds':(end['ticks']-start['ticks'])/os.sysconf('SC_CLK_TCK'),'cpu_percent':100*(end['ticks']-start['ticks'])/os.sysconf('SC_CLK_TCK')/(end['wall']-start['wall']),'rss_start_kib':start.get('VmRSS'),'rss_end_kib':end.get('VmRSS'),'rss_observed_peak_kib':max(observed_rss),'process_lifetime_rss_hwm_kib':end.get('VmHWM'),'rss_sample_period_seconds':1}))
'''
client=board_ssh.connect()
try:
    with client.open_sftp() as sftp:
        log_start=sftp.stat(args.log).st_size
    rc,out,err=board_ssh.run(client,'python3 -c '+shlex.quote('PID='+str(args.pid)+'\nSAMPLE_SECONDS='+str(args.seconds)+'\n'+code),timeout=args.seconds+15,sudo=True)
    (root/(args.label+'_cpu.json')).write_text(out,encoding='utf-8')
    if rc:raise RuntimeError(err)
    with client.open_sftp() as sftp:sftp.get(args.log,str(root/(args.label+'_runtime.log')))
    full=(root/(args.label+'_runtime.log')).read_bytes()
    if len(full)<log_start:raise RuntimeError('Runtime log shrank during sample')
    window=full[log_start:]
    (root/(args.label+'_sample_window.log')).write_bytes(window)
    (root/(args.label+'_window_receipt.json')).write_text(json.dumps({'remote_log':args.log,'start_offset':log_start,'end_offset':len(full),'cpu_sample':json.loads(out),'note':'Log interval includes SSH/SFTP overhead around CPU interval; report aggregate windows separately.'},indent=2),encoding='utf-8')
    print(out)
finally:client.close()
