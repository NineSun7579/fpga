echo __C2_START__
pkill -f run_camview.sh 2>/dev/null
pkill -x camview 2>/dev/null
sleep 2
python3 /tmp/cap3.py 2>&1 | tail -30
echo ---ppm-stats---
python3 -c "
import os
for n in ('c1a','c1b','c2a','c2b'):
    p='/tmp/%s.ppm'%n
    if not os.path.exists(p):
        print(n,'MISSING'); continue
    d=open(p,'rb').read()
    # parse P6 header
    parts=d.split(b'\n',3)
    print(n,'header',parts[0],parts[1],parts[2],'bytes',len(d))
    body=d[len(parts[0])+len(parts[1])+len(parts[2])+3:]
    vals=list(body[:614400])
    uniq=len(set(vals))
    mn,mx=min(vals),max(vals)
    mean=sum(vals)/len(vals)
    var=sum((v-mean)**2 for v in vals)/len(vals)
    print('   unique=%d min=%d max=%d mean=%.1f std=%.1f'%(uniq,mn,mx,mean,var**0.5))
"
echo ---jpeg---
cd /tmp
for n in c1a c1b c2a c2b; do
  if [ -f /tmp/$n.ppm ]; then ffmpeg -y -loglevel error -i /tmp/$n.ppm -q:v 3 /tmp/$n.jpg; ls -l /tmp/$n.jpg; fi
done
echo ---restart-camview---
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null &
sleep 14
echo -n 'camview procs: '
ps aux | grep -a './camview' | grep -v grep | wc -l
echo __C2_DONE__
