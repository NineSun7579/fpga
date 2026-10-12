"""Focused original DDR hold comparison using documented -from/-to options."""
import datetime
import re
import subprocess
from run_route import HERE, PDS, processes, guards, inputs, save
from summarize_route import sha

def main():
    dump = (HERE / 'final_export/routed_dump.txt').read_bytes()
    targets = []
    connections = []
    for m in re.finditer(rb'(?m)^            \(CONNECT\b.*?^            \)', dump, re.S):
        b = m[0]
        if b'mcdq_dcp_out/o_rid[' in b or b'mcdq_dcp_out/o_rlast/' in b:
            refs = re.findall(rb'\(PORTREF (DI\w*) \(INSTREF \\([^\s)]+mcdq_prefetch_fifo/rd_data_ff1[^\s)]+)\s*\)\)', b)
            for pin, inst in refs:
                targets.append((inst + b'/' + pin).decode('ascii'))
                connections.append(b.decode('ascii'))
    assert len(set(targets)) == 5, targets
    save('inherited_hold_target_binding.json', {'routed_targets': sorted(set(targets)), 'exact_connect_blocks': connections,
        'help_evidence': 'timing_help.log', 'basis': 'Original o_rid[0:3] and o_rlast mapped packed-memory DI pins; five data pins, both timing edges audited'})
    before = guards()
    frozen = inputs()
    arch = 'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
    synth_from = ['ddr3/u_ips_ddrc_top/mcdq_dcp_top/mcdq_dcp_out/o_rid[' + str(i) + ']/CLK' for i in range(4)]
    synth_from += ['ddr3/u_ips_ddrc_top/mcdq_dcp_top/mcdq_dcp_out/o_rlast/CLK']
    for stage, db, points, option in [
        ('focused_route_hold', HERE/'place_route/fpga_v8_cooperative_top_v2_pnr.adf', sorted(set(targets)), '-to'),
        ('focused_synthesis_hold', HERE/'synthesize/fpga_v8_cooperative_top_v2_syn.adf', synth_from, '-from')]:
        work = HERE / stage
        assert not work.exists(), 'Never overwrite focused report'
        processes('before_' + stage)
        work.mkdir()
        script = HERE / (stage + '.tcl')
        script.write_text(arch + 'report_timing -input_db_file {' + db.as_posix() + '}'
                          + ' -force_to_run -delay_type min -nworst 10 -max_path 1000 -input_pins TRUE '
                          + option + ' {' + ' '.join('{' + s + '}' for s in points) + '}\n', encoding='ascii')
        command = [str(PDS), '-file', str(script), '-work_dir', str(work), '-project_name', stage]
        dbhash = sha(db)
        with (HERE/(stage+'.log')).open('xb') as log:
            proc = subprocess.Popen(command, cwd=work, stdout=log, stderr=subprocess.STDOUT)
            print('Focused evidence export', stage, 'PID', proc.pid, flush=True)
            code = proc.wait()
        save(stage + '_result.json', {'exit_code': code, 'command': command, 'input_db_sha256': dbhash,
                                     'input_db_unchanged': dbhash == sha(db), 'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        assert code == 0 and dbhash == sha(db)
    assert before == guards() and frozen == inputs()
    print('Both focused reports complete; all source/protected hashes unchanged.', flush=True)

if __name__ == '__main__':
    main()
