"""Restore the preserved display-fix binary with its historical EGL launch environment."""
import json,time,uuid
from pathlib import Path
import deploy_candidate as d

source=d.ROOT/'deploy_1791608274721868300/receipt.json'
receipt=json.loads(source.read_text())
assert receipt['phase']=='restored'
folder=d.ROOT/('restore_display30_launch_'+str(time.time_ns()));folder.mkdir()
session=d.Session(folder,receipt)
try:
    assert session.rpc('boot')['boot_id']==receipt['baseline']['boot_id']
    assert session.rpc('hash',path=session.helper)['sha256']==receipt['artifacts']['helper_sha256']
    exe='/userdata/detview-hdmifull/detview-hdmifull'
    assert session.rpc('hash',path=exe)['sha256']==d.ACTIVE
    assert session.rpc('hash',path='/userdata/linaro/detview-display-fix-20261008/detview')['sha256']==d.ACTIVE
    old=receipt['active'];baseline=receipt['baseline']
    session.save('display30_preflight',previous_active=old,source_receipt=str(source))
    session.rpc('stop',identity=old['identity'],env=old['env'],status=old['status'])
    session.save('display30_previous_retired')
    env=dict(old['env'])
    env.update(QT_QPA_PLATFORM='xcb',QT_XCB_GL_INTEGRATION='xcb_egl')
    for key in tuple(env):
        if key.startswith(('DETVIEW_FPGA_INFER','DETVIEW_CAMERA_DIAG','DETVIEW_INFER_AGE')):env.pop(key)
    run='display30-'+uuid.uuid4().hex
    paths={key:session.remote+'/'+run+suffix for key,suffix in
           {'config':'.launch.json','log':'.viewer.log','supervisor_log':'.supervisor.log',
            'identity_file':'.identity.json','status':'.exit.json'}.items()}
    identity=session.rpc('launch',exe=exe,sha256=d.ACTIVE,argv=baseline['argv'],env=env,
                         cwd=baseline['cwd'],uid=baseline['uid'],gid=baseline['gid'],
                         groups=baseline['groups'],candidate=False,**paths)
    session.save('display30_running',active={'identity':identity,'env':env,**paths})
    print(str(folder));print(json.dumps(identity))
finally:session.client.close()
