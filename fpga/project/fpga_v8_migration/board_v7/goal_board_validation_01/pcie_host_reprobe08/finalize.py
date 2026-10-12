from pathlib import Path
import json,hashlib,re
p=Path(__file__).parent
d=json.loads((p/'final.stdout.txt').read_text())
for c in d['commands']:
 name='dmesg_after' if c['argv'][0]=='dmesg' else 'lspci_'+('tree' if '-t' in c['argv'] else 'nnvv')
 for stream in ['stdout','stderr']:
  (p/(name+'.'+stream+'.txt')).write_bytes(c[stream].encode())
before=(p/'bind_once.stdout.txt').read_text().splitlines()
for line in before:
 if line.startswith('{"argv": ["dmesg"]'):
  c=json.loads(line)
  (p/'dmesg_before.stdout.txt').write_bytes(c['stdout'].encode())
  (p/'dmesg_before.stderr.txt').write_bytes(c['stderr'].encode())
  break
ep=next(x for x in d['pci'] if x['bdf']=='0002:21:00.0')
receipts={q.stem.replace('.receipt',''):json.loads(q.read_text()) for q in p.glob('*.receipt.json')}
assert all(x['rc']==0 for x in receipts.values())
assert ep['attributes']['vendor']=='0x0755' and ep['attributes']['device']=='0x0755'
assert ep['driver']=='/sys/bus/pci/drivers/pango_pci_driver'
assert len(ep['msi_irqs'])==4 and d['owners']==[] and d['owner_scan_errors']==[]
assert d['admission_mode']=='0o644'
result=dict(status='HOST_REPROBE_AND_ENDPOINT_ENUMERATION_RECOVERED',functional_pass=False,dma_validated=False,viewer_validated=False,
 boot_id=d['boot_id'],platform_device='3c0800000.pcie',of_node='/pcie@fe280000',host_driver='rk-pcie',
 bind_attempts=1,unbind_attempts=0,rescan_attempts=0,reboots=0,fpga_programmer_invoked=False,pds_invoked=False,
 endpoint=ep,admission_mode=d['admission_mode'],owners=d['owners'],owner_scan_errors=d['owner_scan_errors'],
 module_sha256='0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861',module_build_id='1102cfd04acaeeea21ca4d03fe27ddbb32b7340a',
 command_receipts=receipts,next_step='Continue separately authorized bounded functional DMA/frame validation with admission still held; do not perform further host bind/reset while endpoint is present.')
(p/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
manifest={q.name:dict(size=q.stat().st_size,sha256=hashlib.sha256(q.read_bytes()).hexdigest()) for q in sorted(p.iterdir()) if q.is_file() and q.name!='manifest.json'}
(p/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['status','functional_pass','boot_id','bind_attempts','admission_mode','owners']},indent=2))
