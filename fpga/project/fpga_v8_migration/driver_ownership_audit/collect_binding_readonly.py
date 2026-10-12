import base64
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REMOTE=r'''python3 - <<'PY'
import base64, datetime, hashlib, json, os
from pathlib import Path
paths=['/sys/module/pango_pci_driver/srcversion','/sys/module/pango_pci_driver/version','/sys/module/pango_pci_driver/initstate','/sys/module/pango_pci_driver/refcnt','/sys/module/pango_pci_driver/notes/.note.gnu.build-id','/usr/src/linux-headers-6.1-rockchip/Makefile','/usr/src/linux-headers-6.1-rockchip/include/generated/utsrelease.h','/usr/src/linux-headers-6.1-rockchip/include/generated/autoconf.h','/usr/src/linux-headers-6.1-rockchip/Module.symvers','/tmp/pango-driver-fix-20260926/pango_pci_driver.c','/tmp/pango-driver-fix-20260926/pango_pci_driver.h','/tmp/pango-driver-fix-20260926/.pango_pci_driver.o.cmd','/tmp/pango-driver-fix-20260926/.pango_pci_driver.ko.cmd','/tmp/pango-driver-fix-20260926/id_config.h','/userdata/AI_car_pro/driver/pango_pci_driver.c','/userdata/linaro/projects/fpga/RK3568/driver/id_config.h']
rows=[]
for name in paths:
    try:
        data=Path(name).read_bytes(); row={'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        if name.endswith('.note.gnu.build-id'): row['hex']=data.hex()
        elif len(data)<150000: row['base64']=base64.b64encode(data).decode()
        rows.append(row)
    except OSError as e: rows.append({'path':name,'error':str(e)})
print(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':rows}))
PY'''
def main():
    destination=ROOT/'binding_evidence.json'
    if destination.exists(): raise FileExistsError(destination)
    spec=importlib.util.spec_from_file_location('board_connection',ROOT.parents[1]/'board_ssh.py')
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    cli=helper.connect()
    try:
        rc,out,err=helper.run(cli,REMOTE,timeout=60,sudo=True)
        if rc: raise RuntimeError(err)
        evidence=json.loads(out)
        for i,row in enumerate(evidence['files']):
            encoded=row.pop('base64',None)
            if encoded:
                path=ROOT/'binding_files'/('%03d_'%i+Path(row['path']).name)
                path.parent.mkdir(exist_ok=True); path.write_bytes(base64.b64decode(encoded))
                row['local_evidence']=str(path.relative_to(ROOT))
        destination.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(evidence,indent=2))
    finally: cli.close()
if __name__=='__main__': main()
