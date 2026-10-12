"""Capture actual executable help before selecting a project-loading invocation."""
import json
import subprocess
from native_query08 import BASE, PDS, idle

if __name__ == '__main__':
    idle()
    out = BASE / 'fixed_06/shell_cli21'
    out.mkdir(exist_ok=False)
    command = [PDS, '-help']
    (out / 'launch.json').write_text(json.dumps({'command': command}, indent=2))
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / 'shell.log').write_bytes(result.stdout)
    text = result.stdout.decode('utf-16' if result.stdout.startswith(b'\xff\xfe') else 'utf8', errors='replace')
    (out / 'shell.txt').write_text(text, encoding='utf8')
    (out / 'result.json').write_text(json.dumps({'exit_code': result.returncode, 'help_only': True}))
    print(text, flush=True)
