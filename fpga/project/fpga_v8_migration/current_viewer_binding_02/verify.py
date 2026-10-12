import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
load=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
a,b=load('snapshot_02.json'),load('snapshot_03.json')
keys=['pid','start_ticks','exe','exe_sha256','cmdline','pango_fds','pango_maps','rknn_maps','runtime_files']
assert len(a['processes'])==len(b['processes'])==1
assert a['boot']==b['boot']
assert not a['scan_errors'] and not b['scan_errors']
assert all(a['processes'][0][k]==b['processes'][0][k] for k in keys)
assert a['rknpu_version']==b['rknpu_version']=='0.9.8\n'
m=load('retrieval_manifest.json')
for e in m:
 if e['stable_match']:
  assert hashlib.sha256((root/e['local']).read_bytes()).hexdigest()==e['sha256']==e['remote_after']['sha256']
lookup={e['path']:e for e in m}
exe=a['processes'][0]['exe_sha256']
assert lookup['/userdata/linaro/detview-driving-demo-src/detview']['sha256']==exe==lookup['/userdata/detview-driving-demo/detview-driving-demo']['sha256']
runtime=(root/'inputs/usr/lib/librknnrt.so').read_bytes()
api=b'2.3.0 (c949ad889d@2024-11-07T11:35:33)'
codepaths=load('compiled_codepaths.json')
for e in codepaths:
 if e['symbol'].startswith('_ZN15InferenceThread') or e['symbol']=='_ZL10scanModelsv':
  (root/(e['symbol'].split('Thread')[-1].split('ER')[0].replace('_ZL','')[:45]+'.disassembly.txt')).write_text(e['stdout'],encoding='utf-8')
result={'two_snapshots_stable':True,'interval_seconds':b['time']-a['time'],'all_device_owners_observed':len(b['processes']),'scan_errors':[],'retrieved_stable_files':sum(e['stable_match'] for e in m),'proc_exe_disk_retained_hash_equal':True,'sdk_header_sha256':lookup['/userdata/linaro/detview-driving-demo-src/rknn_api.h']['sha256'],'runtime_sha256':lookup['/usr/lib/librknnrt.so']['sha256'],'rknpu_sysfs_version':b['rknpu_version'].strip(),'pinned_api_literal_in_disk_runtime':api in runtime,'api_query_performed':False,'remote_device_open_performed':False,'remote_build_performed':False,'independent_rebuild_proven':False}
(root/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
