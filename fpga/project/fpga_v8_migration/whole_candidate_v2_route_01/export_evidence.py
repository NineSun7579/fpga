"""Documented read-only routed DB exports in a new report project, no implementation rerun."""
from pathlib import Path
import datetime
import json
import subprocess
import sys
from run_route import HERE, PDS, processes, guards, inputs, save
from summarize_route import sha

def main():
    assert not (HERE / 'final_export').exists(), 'Do not overwrite export project'
    processes('before_final_export')
    route = HERE / 'place_route/fpga_v8_cooperative_top_v2_pnr.adf'
    route_sha = sha(route)
    before = guards()
    frozen = inputs()
    work = HERE / 'final_export'
    work.mkdir()
    script = HERE / 'final_export.tcl'
    script.write_text(
        'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        + '.switch_db -input {' + route.as_posix() + '} -output {' + (work/'routed_dump.txt').as_posix() + '}\n'
        + 'report_timing -input_db_file {' + route.as_posix() + '}'
        + ' -force_to_run -delay_type min_max -nworst 1 -max_path 15000'
        + ' -slack_less_than 0 -input_pins TRUE -report_exception TRUE\n', encoding='ascii')
    save('export_command_provenance.json', {
        'physical_export_reference': 'project/motion_100h/run_20261003_212303/routed_phy.tcl',
        'sta_reference': 'project/motion_100h/run_20261003_212303/full_sta.tcl',
        'slack_filter_documentation': 'C:/pango/PDS_2022.2-SP6.4/bin/Templates/Tcl/Tools/Project Navigator/Process/Report timing.tmp lines 18-21',
        'scope': 'Final routed DB timing and physical evidence only; no PnR rerun, no constraints changed',
        'path_limit': 15000, 'paths_per_endpoint': 1, 'filter': 'slack < 0',
        'route_sha256_before': route_sha})
    command = [str(PDS), '-file', str(script), '-work_dir', str(work), '-project_name', 'final_route_evidence']
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (HERE / 'final_export_shell.log').open('xb') as log:
        child = subprocess.Popen(command, cwd=work, stdout=log, stderr=subprocess.STDOUT)
        save('final_export_started.json', {'command': command, 'pid': child.pid, 'started_utc': started})
        print('Started final routed evidence export PID', child.pid, flush=True)
        code = child.wait()
    save('final_export_result.json', {
        'exit_code': code, 'command': command, 'started_utc': started,
        'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'route_sha256_before': route_sha, 'route_sha256_after': sha(route),
        'route_db_unchanged': route_sha == sha(route),
        'protected_unchanged': before == guards(), 'local_sources_unchanged': frozen == inputs()})
    print('Final evidence export exit', code, 'route DB unchanged', route_sha == sha(route), flush=True)
    sys.exit(code)

if __name__ == '__main__':
    main()
