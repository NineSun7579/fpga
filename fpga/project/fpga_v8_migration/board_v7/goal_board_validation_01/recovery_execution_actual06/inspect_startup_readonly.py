"""Run through SSH stdin only: proc/sys PCIe/startup metadata; never open a device."""
import os
import stat
import json
import re
import subprocess
from pathlib import Path

def text(p):
    return Path(p).read_text(errors='replace')

def safe(s):
    return re.sub(r'(?i)((?:password|passwd|token|secret|credential)\s*[=: ]\s*)\S+', r'\1<redacted>', s)

def call(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    import hashlib
    a,b=safe(p.stdout),safe(p.stderr)
    return dict(argv=argv, returncode=p.returncode, stdout=a, stderr=b, stdout_sha256=hashlib.sha256(a.encode()).hexdigest(), stderr_sha256=hashlib.sha256(b.encode()).hexdigest())

out = dict(boot_id=text('/proc/sys/kernel/random/boot_id').strip(), processes=[], holders=[], startup=[], commands=[], scan_errors=[], device_opened=False)
out['hostname']=text('/proc/sys/kernel/hostname').strip()
out['pci_raw']=[]
import hashlib
for devpath in Path('/sys/bus/pci/devices').iterdir():
    if text(devpath/'vendor').strip()!='0x0755' or text(devpath/'device').strip()!='0x0755': continue
    for path in (devpath, devpath.resolve().parent):
        with (path/'config').open('rb') as f: raw=f.read(64)
        assert len(raw)==64 and raw[:4]!=b'\xff'*4
        row=dict(bdf=path.name,config64_hex=raw.hex(),config64_sha256=hashlib.sha256(raw).hexdigest(),class_code=text(path/'class').strip())
        if path==devpath:
            row['reset_method']=text(path/'reset_method').strip()
            row['resource_metadata']=text(path/'resource')
        else:
            row['downstream_sysfs_devices']=[p.name for p in path.rglob('*') if (p/'vendor').is_file()]
        out['pci_raw'].append(row)
dev = Path('/dev/pango_pci_driver')
target = dev.stat().st_rdev if dev.exists() else None
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():
        continue
    try:
        raw = (proc/'cmdline').read_bytes()
        argv = [s.decode(errors='replace') for s in raw.split(b'\0') if s]
        comm = text(proc/'comm').strip()
        fds = []
        for fd in (proc/'fd').iterdir():
            try:
                st = fd.stat()
                if target is not None and stat.S_ISCHR(st.st_mode) and st.st_rdev == target:
                    fds.append(dict(fd=fd.name, target=os.readlink(fd)))
            except FileNotFoundError:
                pass
        maps = text(proc/'maps')
        mapped = [s for s in maps.splitlines() if '/dev/pango' in s or '/dev/xdma' in s]
        related = any(x in ' '.join(argv).lower() for x in ('driving-demo', 'detview', 'camview', 'pango'))
        # Exclude this interpreter's command/script and shells containing heredoc text.
        related = related and not any('\n' in a for a in argv) and comm!='python3'
        if fds or mapped or related:
            row = dict(pid=int(proc.name), comm=comm, argv=[safe(x) for x in argv], exe=os.readlink(proc/'exe'), stat=text(proc/'stat').strip(), cgroup=text(proc/'cgroup'), fds=fds, mappings=mapped)
            import hashlib
            try:
                row['exe_sha256'] = hashlib.sha256((proc/'exe').read_bytes()).hexdigest()
            except OSError:
                row['exe_sha256'] = None
            out['processes'].append(row)
            if fds or mapped:
                out['holders'].append(row)
    except FileNotFoundError:
        pass
    except (OSError, PermissionError) as e:
        out['scan_errors'].append(dict(path=str(proc), error=type(e).__name__))

roots = ['/etc/systemd/system', '/usr/lib/systemd/system', '/lib/systemd/system', '/etc/xdg', '/etc/lightdm', '/home/linaro/.config/autostart', '/root/.config/autostart', '/home/linaro/.config/systemd/user', '/root/.config/systemd/user', '/etc/cron.d', '/var/spool/cron/crontabs']
import pwd
homes = {entry.pw_dir for entry in pwd.getpwall() if entry.pw_uid in (0,1000)} | {'/userdata/linaro'}
out['home_paths'] = sorted(homes)
for home in homes:
    roots.extend([home+'/.config/autostart', home+'/.config/systemd/user', home+'/.config/xfce4', home+'/.cache/sessions'])
files = [Path('/etc/rc.local'), Path('/home/linaro/.xsession'), Path('/home/linaro/.xinitrc'), Path('/home/linaro/.profile'), Path('/etc/crontab')]
for home in homes:
    files.extend(Path(home)/x for x in ('.xsession','.xinitrc','.profile','.bash_profile'))
for base in ('/userdata','/usr/local/bin','/opt'):
    # Bounded launcher search: never consume model/media trees or arbitrary credential files.
    for root, dirs, names in os.walk(base):
        depth=len(Path(root).relative_to(base).parts)
        dirs[:] = [d for d in dirs if depth < 3 and d not in ('models','media','node_modules','.git','build')]
        for name in names:
            if name.endswith(('.sh','.desktop','.service')):
                files.append(Path(root)/name)
for root in roots:
    p = Path(root)
    if p.exists():
        files.extend(x for x in p.rglob('*') if x.is_file())
for p in files:
    try:
        if not p.is_file() or p.stat().st_size > 1024*1024:
            continue
        lines = text(p).splitlines()
        hits = [(i+1, safe(s)) for i,s in enumerate(lines) if any(k in s.lower() for k in ('driving-demo', 'detview', 'pango_pci', 'camview')) or (p.suffix=='.desktop' and s.startswith(('Exec=','Hidden=','X-GNOME-Autostart-enabled=')))]
        if hits:
            out['startup'].append(dict(path=str(p), realpath=str(p.resolve()), matches=hits))
    except OSError as e:
        out['scan_errors'].append(dict(path=str(p), error=type(e).__name__))
out['commands'].append(call(['systemctl', 'list-units', '--all', '--no-pager', '--plain']))
units = set()
for row in out['startup']:
    if row['path'].endswith('.service'):
        units.add(Path(row['path']).name)
for row in out['processes']:
    units.update(re.findall(r'([\w@.\-]+\.service)', row['cgroup']))
for unit in sorted(units):
    out['commands'].append(call(['systemctl', 'show', unit, '--no-pager', '--property=Id,FragmentPath,DropInPaths,ExecStart,Restart,ActiveState,UnitFileState']))
out['commands'].append(call(['ps', '-eo', 'pid,ppid,comm']))
out['commands'].append(call(['cat','/userdata/detview-driving-demo/run_driving_demo.sh']))
out['commands'].append(call(['sha256sum','/userdata/detview-driving-demo/detview-driving-demo','/userdata/detview-driving-demo/run_driving_demo.sh']))
out['commands'].append(call(['ls','-la','/run/driving_demo','/tmp/driving_demo']))
for state in ('/run/driving_demo','/tmp/driving_demo'):
    p=Path(state)
    if p.is_dir():
        for name in ('app.pid','supervisor.pid','app.path','launch.args','stop'):
            f=p/name
            if f.is_file():
                out.setdefault('launcher_state',[]).append(dict(path=str(f),content=safe(f.read_bytes().replace(b'\0',b'\n').decode(errors='replace'))))
out['commands'].append(call(['cat','/etc/rc.local']))
out['commands'].append(call(['systemctl','list-unit-files','--no-pager','--plain']))
print(json.dumps(out, indent=2))
