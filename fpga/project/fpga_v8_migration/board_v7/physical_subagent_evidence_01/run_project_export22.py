"""Test documented CLI project loading on a disposable mapped project copy."""
import json
import re
import shutil
import subprocess
from native_query08 import BASE, PDS, idle, digest

if __name__ == '__main__':
    idle()
    source = BASE / 'fixed_06/stage_map13'
    out = BASE / 'fixed_06/project_export22'
    shutil.copytree(source, out)
    original = source / 'device_map/v7_sdt_top_map.adf'
    before = digest(original)
    project = out / 'stage_map13.pds'
    raw = project.read_bytes()
    def absolute(match):
        path = (out / match.group(1).decode('ascii')).resolve()
        return b'(_file "' + path.as_posix().encode('ascii') + b'"'
    project.write_bytes(re.sub(rb'\(_file "([^"\r\n]+)"', absolute, raw))
    target = out / 'actual_export22.fdc'
    script = out / 'export22.tcl'
    script.write_text('export_fdc -file {' + target.as_posix() + '} -no_log FALSE\n', encoding='ascii')
    command = [PDS, '-project', str(project), '-file', str(script), '-work_dir', str(out)]
    (out / 'export22_launch.json').write_text(json.dumps({'command': command, 'source_db_sha256': before}, indent=2))
    idle()
    with (out / 'export22_shell.log').open('xb') as stream:
        result = subprocess.run(command, cwd=out, stdout=stream, stderr=subprocess.STDOUT)
    raw = (out / 'export22_shell.log').read_bytes()
    text = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8', errors='replace')
    (out / 'export22_shell.txt').write_text(text, encoding='utf8')
    receipt = {
        'exit_code': result.returncode,
        'errors': [line for line in text.splitlines() if line.startswith('E:')],
        'source_db_unchanged': digest(original) == before,
        'export_exists': target.exists(),
        'export_bytes': target.stat().st_size if target.exists() else 0,
        'budget_loading_proven': False,
        'bit_permitted': False,
    }
    (out / 'export22_result.json').write_text(json.dumps(receipt, indent=2))
    print(text, flush=True)
    print(json.dumps(receipt, indent=2), flush=True)
    assert receipt['source_db_unchanged']
