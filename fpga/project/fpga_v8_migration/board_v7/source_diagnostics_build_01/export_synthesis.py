"""Read-only actual PDS synthesis DB dump and command support discovery."""
from prepare import HERE, PDS, idle, sha, save
import subprocess, json

def main():
    result = json.loads((HERE / 'flow_result.json').read_bytes())
    assert result['stages'][-1] == {**result['stages'][-1], 'stage':'synthesize', 'exit_code':0}
    db = HERE / 'synthesize/v7_sdt_top_syn.adf'
    h = sha(db)
    attempt = 1
    while (HERE / ('synthesis_export' if attempt == 1 else 'synthesis_export_%02d' % attempt)).exists():
        attempt += 1
    suffix = '' if attempt == 1 else '_%02d' % attempt
    out = HERE / ('synthesis_export' + suffix)
    out.mkdir()
    script = HERE / ('export_synthesis' + suffix + '.tcl')
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
                      '.switch_db -input {' + db.as_posix() + '} -output {' + (out / 'synthesis_dump.txt').as_posix() + '}\n'
                      'report_timing -help\n', encoding='ascii')
    idle('before_synthesis_export')
    cmd = [str(PDS), '-file', str(script), '-work_dir', str(out), '-project_name', 'sdt_synthesis_evidence']
    with (HERE / ('synthesis_export_shell' + suffix + '.log')).open('xb') as log:
        p = subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT)
    save('synthesis_export_result' + suffix + '.json', {'command':cmd, 'exit_code':p.returncode,
                                        'db_sha256_before':h, 'db_sha256_after':sha(db)})
    assert p.returncode == 0 and h == sha(db)

if __name__ == '__main__':
    main()
