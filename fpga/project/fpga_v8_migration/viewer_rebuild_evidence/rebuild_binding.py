"""Isolated source/build binding audit. Uses board_ssh.connect without logging secrets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import posixpath
import tarfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT))
import board_ssh


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(cli, command, timeout=120):
    stdin, stdout, stderr = cli.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if rc:
        raise RuntimeError(f"Remote command rc={rc}: {err[-2000:]}")
    return out


def remote_python(cli, source, *args, timeout=120):
    command = "python3 - " + " ".join(shlex.quote(str(arg)) for arg in args)
    stdin, stdout, stderr = cli.exec_command(command, timeout=timeout)
    stdin.write(source)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if rc:
        raise RuntimeError(f"Remote Python rc={rc}: {err[-2000:]}")
    return out


def process_guard(cli):
    # The live viewer is owned by root. Elevate only this read-only /proc audit;
    # board_ssh keeps its credential handling private. Build remains unprivileged.
    rc, out, err = board_ssh.run(cli, "python3 -c " + shlex.quote(GUARD), sudo=True)
    if rc:
        raise RuntimeError(f"Read-only process guard rc={rc}")
    return json.loads(out)


VERIFY_REMOTE = r'''
import hashlib, json, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
def info(p):
    data = p.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
files = {str(p.relative_to(root)): info(p) for p in sorted(root.rglob('*')) if p.is_file()}
print(json.dumps(files))
'''

GUARD = r'''
import hashlib, json, os, pathlib
def info(p):
    try:
        d = pathlib.Path(p).read_bytes()
        return {"sha256": hashlib.sha256(d).hexdigest(), "bytes": len(d)}
    except OSError as e: return {"error": str(e)}
result = {"boot_id": pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
          "installed": info('/userdata/detview-hdmifull/detview-hdmifull'), "processes": []}
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try:
        exe = os.readlink(p / 'exe')
        if 'detview' not in exe: continue
        stat = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        result['processes'].append({"pid": int(p.name), "start_ticks": int(stat[19]),
                                    "exe": exe, "image": info(p / 'exe'),
                                    "cmdline": (p/'cmdline').read_bytes().decode('utf8','replace').replace('\0',' '),
                                    "maps": (p/'maps').read_text(),
                                    "fds": {f.name: os.readlink(f) for f in (p/'fd').iterdir()}})
    except OSError: pass
print(json.dumps(result))
'''


def prepare(cli):
    recovered = HERE.parent / "viewer_build_recovered"
    manifest = json.loads((recovered / "manifest.json").read_text(encoding="utf-8"))
    expected = {f["path"]: {"bytes": f["bytes"], "sha256": f["sha256"]} for f in manifest["files"]}
    local = {name: {"bytes": (recovered / "inputs" / name).stat().st_size,
                    "sha256": digest(recovered / "inputs" / name)} for name in expected}
    save("frozen_local_recheck.json", local)
    if local != expected:
        raise RuntimeError("Frozen local inputs differ from recovered manifest")
    remote = json.loads(remote_python(cli, VERIFY_REMOTE, manifest["remote_root"]))
    save("original_remote_before.json", remote)
    differences = {name: {"expected": value, "actual": remote.get(name)}
                   for name, value in expected.items() if remote.get(name) != value}
    extras = sorted(set(remote) - set(expected))
    save("input_verification.json", {"manifest_sha256": digest(recovered / "manifest.json"),
                                    "files_checked": len(expected), "differences": differences,
                                    "extra_remote_files": extras})
    if differences or extras:
        raise RuntimeError("Original retained board directory changed; review input_verification.json")
    save("process_guard_before.json", process_guard(cli))
    remote_base = "/userdata/linaro/fpga_v8_viewer_binding_20261005"
    remote_root = run(cli, "base=" + shlex.quote(remote_base) +
                      '; dest="$base"; i=0; while [ -e "$dest" ]; do i=$((i+1)); dest="${base}_$i"; done; '
                      'mkdir "$dest" && printf "%s" "$dest"').strip()
    state = {"remote_root": remote_root, "original_root": manifest["remote_root"],
             "expected_executable_sha256": manifest["installed_binary_sha256"],
             "build_return_code": None}
    save("state.json", state)
    sftp = cli.open_sftp()
    uploaded = []
    # Only original authored source/header/project files; regenerate every moc,
    # qmake stash, Makefile and object. No recovered object or executable uploaded.
    for name in expected:
        if Path(name).suffix not in {".cpp", ".h", ".pro"}: continue
        if Path(name).name.startswith("moc_"): continue
        dest = remote_root + "/" + name
        parent = str(Path(name).parent).replace("\\", "/")
        if parent != ".":
            try: sftp.mkdir(remote_root + "/" + parent)
            except OSError: pass
        sftp.put(str(recovered / "inputs" / name), dest)
        uploaded.append({"path": name, **expected[name]})
    sftp.put(str(HERE / "remote_audit.py"), remote_root + "/remote_audit.py")
    sftp.put(str(HERE / "build_isolated.sh"), remote_root + "/build_isolated.sh")
    sftp.close()
    save("uploaded_sources.json", uploaded)
    out = run(cli, "cd " + shlex.quote(remote_root) +
              " && python3 remote_audit.py preflight > preflight_status.json")
    print(json.dumps({"phase": "prepared", "remote_root": remote_root, "verified_files": len(expected),
                      "uploaded_source_files": len(uploaded), "reused_objects": 0}))


def build(cli):
    state = json.loads((HERE / "state.json").read_text())
    root = state["remote_root"]
    # The local tool is run with background=true. Remote output is redirected,
    # so a three-minute compilation does not flood tool output or hit 120s IO limits.
    result = run(cli, "cd " + shlex.quote(root) + " && bash build_isolated.sh", timeout=900)
    print(result.strip())


def collect(cli):
    state = json.loads((HERE / "state.json").read_text())
    root = state["remote_root"]
    result = json.loads(run(cli, "cd " + shlex.quote(root) + " && python3 remote_audit.py collect", timeout=900))
    save("remote_result.json", result)
    sftp = cli.open_sftp()
    products = HERE / "rebuilt"
    products.mkdir(exist_ok=True)
    for name in result["download_files"]:
        dest = HERE / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        sftp.get(root + "/" + name, str(dest))
    sftp.close()
    recovered = HERE.parent / "viewer_build_recovered"
    manifest = json.loads((recovered / "manifest.json").read_text())
    reference = {f["path"]: f for f in manifest["files"]}
    comparison = []
    for name in ["detview"] + sorted(n for n in result["products"] if n.endswith(".o")):
        actual = result["products"][name]
        old = reference.get(name)
        comparison.append({"path": name, "new_sha256": actual["sha256"],
                           "old_sha256": old["sha256"] if old else None,
                           "equal": bool(old and old["sha256"] == actual["sha256"]),
                           "new_bytes": actual["bytes"], "old_bytes": old["bytes"] if old else None})
    save("binary_comparison.json", comparison)
    after = json.loads(remote_python(cli, VERIFY_REMOTE, state["original_root"]))
    save("original_remote_after.json", after)
    guard = process_guard(cli)
    save("process_guard_after.json", guard)
    before = json.loads((HERE / "original_remote_before.json").read_text())
    guard_before = json.loads((HERE / "process_guard_before.json").read_text())
    exe_equal = comparison[0]["equal"]
    state.update({"build_return_code": result["build_return_code"],
                  "source_build_binding": "exact_executable_reproduction" if exe_equal else "requires_delta_analysis",
                  "objects_equal": sum(x["equal"] for x in comparison[1:]),
                  "objects_total": len(comparison) - 1,
                  "original_directory_unchanged": after == before,
                  "installed_executable_unchanged": guard_before["installed"] == guard["installed"],
                  "boot_unchanged": guard_before["boot_id"] == guard["boot_id"],
                  "live_process_identity_unchanged":
                      [(p["pid"], p["start_ticks"], p["image"]) for p in guard_before["processes"]] ==
                      [(p["pid"], p["start_ticks"], p["image"]) for p in guard["processes"]]})
    save("state.json", state)
    print(json.dumps(state))


SUPPLEMENT = r'''
import hashlib, json, os, pathlib, time
def info(p):
    d = pathlib.Path(p).read_bytes()
    return {"path": str(p), "realpath": str(pathlib.Path(p).resolve()), "bytes": len(d),
            "sha256": hashlib.sha256(d).hexdigest()}
result = {"utc_epoch": time.time(), "boot_id": pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
          "processes": [], "live_mapped_libraries": {}}
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try:
        exe = os.readlink(p/'exe')
        if 'detview' not in exe: continue
        stat = (p/'stat').read_text().rsplit(')',1)[1].split()
        maps = (p/'maps').read_text()
        result['processes'].append({"pid": int(p.name), "start_ticks": int(stat[19]), "exe": exe,
          "image": info(p/'exe'), "maps": maps,
          "fds": {f.name: os.readlink(f) for f in (p/'fd').iterdir()}})
        for line in maps.splitlines():
            fields = line.split(None,5)
            if len(fields) < 6 or not fields[5].startswith('/'): continue
            lib = fields[5]
            if '.so' in lib and pathlib.Path(lib).is_file(): result['live_mapped_libraries'][lib] = info(lib)
    except OSError: pass
print(json.dumps(result))
'''


def supplement(cli):
    state = json.loads((HERE/'state.json').read_text())
    root = state['remote_root']
    rc, out, err = board_ssh.run(cli, "python3 -c " + shlex.quote(SUPPLEMENT), sudo=True)
    if rc: raise RuntimeError(f"Read-only live runtime library audit rc={rc}")
    mapped = json.loads(out)
    save('live_runtime_library_audit.json', mapped)
    # qmake inputs and pkg-config metadata are build dependencies too.
    script = r'''
import json, pathlib, re, sys, tarfile
import remote_audit as audit
root = pathlib.Path.cwd()
text = (root/'Makefile.fresh').read_text().replace('\\\n', ' ')
paths = {pathlib.Path(p) for p in re.findall(r'/[^\s\\]+\.(?:prf|conf|pri)', text)}
paths |= {pathlib.Path('/usr/lib/aarch64-linux-gnu/pkgconfig/opencv4.pc'),
          pathlib.Path('/usr/bin/qtchooser'), pathlib.Path('/usr/lib/qt5/bin/moc'),
          pathlib.Path('/usr/lib/aarch64-linux-gnu/qt5/mkspecs/features/data/dummy.cpp')}
for p in list(paths):
    if p.suffix in {'.pri','.prf','.conf'} and p.is_file():
        paths |= {pathlib.Path(q) for q in re.findall(r'/[^\s)]+\.(?:prf|conf|pri)',p.read_text(errors='replace'))}
qmake = audit.copy_snapshot(paths, 'qmake_config_snapshot')
mapped = json.loads((root/'live_runtime_library_audit.json').read_text())
runtime = audit.copy_snapshot(mapped['live_mapped_libraries'].keys(), 'live_runtime_library_snapshot')
with tarfile.open(root/'supplement_snapshots.tar.gz','w:gz') as tar:
    for name in ['qmake_config_snapshot','live_runtime_library_snapshot']: tar.add(root/name,arcname=name)
audit.dump('supplement_archive_identity.json',audit.info(root/'supplement_snapshots.tar.gz'))
print(json.dumps({'qmake_config_files':len(qmake),'live_runtime_libraries':len(runtime)}))
'''
    sftp = cli.open_sftp()
    sftp.put(str(HERE/'live_runtime_library_audit.json'),root+'/live_runtime_library_audit.json')
    sftp.close()
    result = json.loads(run(cli,"cd "+shlex.quote(root)+" && python3 -c "+shlex.quote(script),timeout=900))
    save('supplement_result.json',result)
    sftp = cli.open_sftp()
    for name in ['qmake_config_snapshot_manifest.json','live_runtime_library_snapshot_manifest.json',
                 'supplement_snapshots.tar.gz','supplement_archive_identity.json']:
        sftp.get(root+'/'+name,str(HERE/name))
    sftp.close()
    save('process_guard_final.json', process_guard(cli))
    print(json.dumps(result))


def verify_local():
    recovered = HERE.parent/'viewer_build_recovered'
    ref = json.loads((recovered/'manifest.json').read_text())
    rechecked = []
    for f in ref['files']:
        p = recovered/'inputs'/f['path']
        if digest(p) != f['sha256'] or p.stat().st_size != f['bytes']:
            raise RuntimeError('Frozen source changed: '+f['path'])
        rechecked.append(f['path'])
    byte_comparisons = []
    for p in sorted((HERE/'rebuilt').iterdir()):
        byte_comparisons.append({'path':p.name,'byte_for_byte_equal':p.read_bytes() == (recovered/'inputs'/p.name).read_bytes()})
    generated = []
    for name in ['main.moc','moc_predefs.h','moc_calibration_capture.cpp','moc_vision_pipeline.cpp','.qmake.stash']:
        generated.append({'path':name,'byte_for_byte_equal':(HERE/name).read_bytes() == (recovered/'inputs'/name).read_bytes(),
                          'sha256':digest(HERE/name)})
    flags = {}
    for key in ['CC','CXX','DEFINES','CFLAGS','CXXFLAGS','INCPATH','LINK','LFLAGS','LIBS','QMAKE']:
        def setting(path):
            for line in path.read_text().splitlines():
                if line.split('=',1)[0].strip() == key: return line.split('=',1)[1].strip()
        old = setting(recovered/'inputs'/'Makefile')
        new = setting(HERE/'Makefile.fresh')
        flags[key] = {'equal':old == new,'old':old,'new':new}
    archives = []
    for archive, identity, manifests in [
        ('dependency_snapshots.tar.gz','snapshot_archive_identity.json',
         ['toolchain_snapshot','compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot']),
        ('supplement_snapshots.tar.gz','supplement_archive_identity.json',
         ['qmake_config_snapshot','live_runtime_library_snapshot']),
    ]:
        record = json.loads((HERE/identity).read_text())
        if digest(HERE/archive) != record['sha256']: raise RuntimeError('Downloaded archive SHA mismatch')
        count = 0
        with tarfile.open(HERE/archive,'r:gz') as tar:
            members = {m.name:m for m in tar.getmembers() if m.isfile()}
            for prefix in manifests:
                for f in json.loads((HERE/(prefix+'_manifest.json')).read_text()):
                    name = posixpath.normpath(prefix+'/'+f['path'].lstrip('/'))
                    member = members[name]
                    h = hashlib.sha256()
                    stream = tar.extractfile(member)
                    for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
                    if h.hexdigest() != f['sha256'] or member.size != f['bytes']:
                        raise RuntimeError('Snapshot member mismatch '+name)
                    count += 1
        archives.append({'path':archive,'sha256':record['sha256'],'verified_manifest_entries':count})
    verify = {'frozen_files_unchanged':len(rechecked),'products':byte_comparisons,'generated':generated,
              'qmake_flags':flags,'archives':archives}
    save('local_verification.json',verify)
    print(json.dumps({'products_equal':all(x['byte_for_byte_equal'] for x in byte_comparisons),
                      'generated_equal':all(x['byte_for_byte_equal'] for x in generated),
                      'qmake_flags_equal':all(x['equal'] for x in flags.values()),
                      'frozen_files_unchanged':len(rechecked),'archives':archives}))


def finalize(cli):
    state = json.loads((HERE/'state.json').read_text())
    final_files = json.loads(remote_python(cli,VERIFY_REMOTE,state['original_root']))
    save('original_remote_final.json',final_files)
    guard = process_guard(cli)
    save('process_guard_final.json',guard)
    before = json.loads((HERE/'process_guard_before.json').read_text())
    state['original_directory_unchanged_final'] = final_files == json.loads((HERE/'original_remote_before.json').read_text())
    state['installed_executable_unchanged_final'] = before['installed'] == guard['installed']
    state['boot_unchanged_final'] = before['boot_id'] == guard['boot_id']
    state['live_process_identity_unchanged_final'] = [(p['pid'],p['start_ticks'],p['image']) for p in before['processes']] == [(p['pid'],p['start_ticks'],p['image']) for p in guard['processes']]
    state['viewer_or_selftest_executions'] = 0
    state['driver_opens_by_audit'] = 0
    state['device_runtime_exclusivity'] = 'not_established'
    state['note'] = 'Accessible root-owned process guard began while isolated build was underway; parent-reported prior PID had already changed.'
    save('state.json',state)
    verification = json.loads((HERE/'local_verification.json').read_text())
    uploaded = json.loads((HERE/'uploaded_sources.json').read_text())
    dependencies = {f['path']:f for f in json.loads((HERE/'compiler_dependency_snapshot_manifest.json').read_text())}
    used = []
    for f in uploaded:
        actual = dependencies.get(state['remote_root']+'/'+f['path'])
        if actual:
            used.append({'path':f['path'],'sha256':actual['sha256'],'matches_frozen':actual['sha256'] == f['sha256']})
    save('compiled_authored_input_verification.json',used)
    if not all(x['matches_frozen'] for x in used): raise RuntimeError('Compiler source inputs differed')
    if not all(x['byte_for_byte_equal'] for x in verification['products']): raise RuntimeError('Products differ')
    inventory = []
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name == 'artifact_manifest.json': continue
        inventory.append({'path':p.relative_to(HERE).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)})
    save('artifact_manifest.json',{'excludes':['artifact_manifest.json','__pycache__'],'files':inventory})
    # Reports are copied only to the isolated evidence root. Installed executable
    # and original source directory are never destinations of a write operation.
    sftp = cli.open_sftp()
    for name in ['README.md','SOURCE_RUNTIME_NOTES.md','artifact_manifest.json','state.json',
                 'local_verification.json','binary_comparison.json','compiled_authored_input_verification.json']:
        sftp.put(str(HERE/name),state['remote_root']+'/'+name)
    sftp.close()
    print(json.dumps({'source_build_binding':state['source_build_binding'],
                      'objects_equal':state['objects_equal'],'objects_total':state['objects_total'],
                      'artifact_files':len(inventory), 'compiled_authored_inputs_verified':len(used),
                      'preservation':{k:v for k,v in state.items() if k.endswith('_final')}}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "build", "collect", "supplement", "verify-local", "finalize"])
    args = parser.parse_args()
    if args.phase == 'verify-local':
        verify_local()
        return
    cli = board_ssh.connect()
    try:
        {"prepare": prepare, "build": build, "collect": collect, "supplement": supplement, "finalize": finalize}[args.phase](cli)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
