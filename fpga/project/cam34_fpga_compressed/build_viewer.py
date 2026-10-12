from pathlib import Path
import hashlib,json,importlib.util,shlex,time
root=Path(__file__).resolve().parent;source=root/'viewer'
spec=importlib.util.spec_from_file_location('board',root.parent/'board_ssh.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
remote='/userdata/linaro/ov56401-cam34-wire-viewer-build-'+str(time.time_ns())
m={'source':str(source),'remote':remote,'sources':{},'executable':remote+'/detview_cam34_fpga_compressed'}
evidence=root/'viewer_build';evidence.mkdir(exist_ok=True)
c=b.connect()
try:
 rc,o,e=b.run(c,'mkdir -p '+remote+'/tmp',timeout=20);assert rc==0
 with c.open_sftp() as sf:
  dirs={remote,remote+'/tmp'}
  for p in sorted(source.rglob('*')):
   if not p.is_file():continue
   rel=p.relative_to(source).as_posix();dest=remote+'/'+rel
   for d in reversed(Path(rel).parent.parents):
    path=remote+'/'+d.as_posix()
    if path not in dirs:
     try:sf.mkdir(path)
     except OSError:sf.stat(path)
     dirs.add(path)
   parent=remote+'/'+Path(rel).parent.as_posix()
   if parent not in dirs:
    try:sf.mkdir(parent)
    except OSError:sf.stat(parent)
    dirs.add(parent)
   sf.put(str(p),dest);m['sources'][rel]=hashlib.sha256(p.read_bytes()).hexdigest()
 print('REMOTE_VIEWER_BUILD',remote,flush=True)
 # Only changed units compile. Reuse prior objects whose sources/headers match,
 # then let make track modified headers in its generated dependencies.
 previous='/userdata/linaro/ov56401-cam34-six-320x240-build-1791630965350164900'
 rc,o,e=b.run(c,'cp '+previous+'/*.o '+remote+'/; cp '+previous+'/main.moc '+remote+'/; cp '+previous+'/moc_*.cpp '+remote+'/; cd '+remote+' && env TMPDIR='+remote+'/tmp qmake detview.pro && touch main.cpp hdmi_view.h hdmi_view_selftest.cpp inference_geometry_selftest.cpp && env TMPDIR='+remote+'/tmp make -j2',timeout=600)
 (evidence/'build.log').write_text(o+e,encoding='utf-8');m['build_return_code']=rc
 if rc:print((o+e)[-5000:],flush=True)
 else:
  rc2,o2,e2=b.run(c,'sha256sum '+m['executable']);assert rc2==0;m['executable_sha256']=o2.split()[0]
 (evidence/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print('HOST_BUILD_RC',rc,flush=True);assert rc==0
finally:c.close()
