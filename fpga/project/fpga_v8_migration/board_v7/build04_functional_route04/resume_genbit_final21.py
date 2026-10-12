"""Verify the genbit-final routed database, then bind the produced bitstream.

gen_bit_stream re-routed internally and finished with an IO report byte-identical
to the qualified baseline. This entry runs the complete controller acceptance
(native export, CDB, global10/crossings/signature reports, IO retention, routed
sites) on that final database, writes functional_route07/RESULT.json, and only on
PASS binds the actual .sbit in BIT_MANIFEST.json.
"""
import json
import shutil
import sys
import traceback
from pathlib import Path

import controller as f
import re

sys.dont_write_bytecode = True


def main():
    k, h = f.r.lock()
    try:
        f.idle('resume_genbit_final21')
        assert not (f.E/'BIT_MANIFEST.json').exists(), 'Qualified delivery already exists'
        assert not (f.E/'functional_route07').exists(), 'Never repeat this attempt'
        genbit_receipt = json.loads((f.E/'functional_genbit_receipt.json').read_bytes())
        assert genbit_receipt['rc'] == 0 and not genbit_receipt['errors'], 'genbit stage failed'
        assert genbit_receipt['log_sha256'] == f.r.sha(f.E/'functional_genbit.log')
        w = f.E/'functional_candidate01'
        final = w/'place_route'
        routed = final/'v7_sdt_top_pnr.adf'
        bits = list((w/'generate_bitstream').rglob('*.sbit'))
        assert routed.is_file() and len(bits) == 1 and bits[0].stat().st_size > 0
        f.r.W = w
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        graph = f.E/'functional_map_view13_native/analysis/graph.json'
        mg = json.loads(graph.read_bytes())
        label = 'functional_route07'
        attempt = f.E/label
        work = attempt/'work'
        work.mkdir(parents=True)
        copied = []
        for folder in ['compile', 'synthesize', 'device_map']:
            shutil.copytree(w/folder, work/folder)
            for p in (w/folder).rglob('*'):
                if p.is_file():
                    dest = work/folder/p.relative_to(w/folder)
                    assert f.r.sha(p) == f.r.sha(dest)
                    copied.append(dict(source=str(p), copy=str(dest), sha256=f.r.sha(p)))
        shutil.copytree(final, work/'place_route')
        for p in final.rglob('*'):
            if p.is_file():
                dest = work/'place_route'/p.relative_to(final)
                assert f.r.sha(p) == f.r.sha(dest)
                copied.append(dict(source=str(p), copy=str(dest), sha256=f.r.sha(p)))
        f.save(label+'/stage_copyhash.json', copied)
        f.save(label+'/genbit_final_binding.json', dict(
            genbit_receipt_sha256=f.r.sha(f.E/'functional_genbit_receipt.json'),
            genbit_log_sha256=f.r.sha(f.E/'functional_genbit.log'),
            place_route_source=str(final), routed_adf_sha256=f.r.sha(routed),
            sbit=str(bits[0]), sbit_sha256=f.r.sha(bits[0]),
            verify20_failure_sha256=f.r.sha(f.E/'RESUME_IO_VERIFY20_FAIL.json'),
            note='gen_bit_stream internally re-routed; its final database is re-verified here'))
        c = f.c
        c.E = attempt
        c.R = attempt
        c.P = work
        c.W = w
        routed = work/'place_route/v7_sdt_top_pnr.adf'
        plan = f.site_plan(mg, w, label+'/native60_site_binding.json')
        g = f.r.export(label+'/native', routed)
        dump = attempt/'native/synthesis_export/synthesis_dump.txt'
        rawcdb = c.raw_cdb(dump)
        pp = f.actual_pairs(g)
        f.save(label+'/actual_pairs.json', dict(count=len(pp), rows=pp))
        placements = {}
        pattern = rb'\(INSTANNOTATE\s+\(INSTREF\s+([^\s)]+)\s*\)\s+\(PLACE\s+([^\s]+)\s+\(DEVINSTREF\s+([^\s]+)\s+\(SITEREF\s+(\d+)\s+(\d+)'
        for m in re.finditer(pattern, dump.read_bytes()):
            placements.setdefault(m[1].decode().lstrip('\\'), []).append(m[3].decode()+'_'+m[4].decode()+'_'+m[5].decode())
        site_rows = []
        for item in plan:
            matches = [p for p in g['primitives'] if (p == item['source'] or p.startswith(item['source']+'/')) and p+'/CLK' in g['pin_net'] and any(p+'/'+x in g['pin_net'] for x in ['Q', 'Q0', 'L6Q', 'L5Q'])]
            assert len(matches) == 1, (item, matches)
            sites = sorted(set(placements.get(matches[0], [])))
            assert sites == [item['site']], (item, sites)
            site_rows.append(dict(source=item['source'], cell=matches[0], site=sites[0], type=g['primitives'][matches[0]]['type']))
        f.save(label+'/routed60_sites.json', dict(rows=site_rows, passed=True))
        mappedcopy = attempt/'mapping_native/analysis'
        mappedcopy.mkdir(parents=True)
        (mappedcopy/'graph.json').write_text(json.dumps(mg), encoding='ascii')
        retained = c.io_retention(g, placements)

        def report(name, options):
            dest = attempt/name
            f.r.tool(label+'_'+name, f.r.ARCH+'report_timing -force_to_run -input_db_file {'+routed.as_posix()+'} '+options+'\n', dest)
            return dest/'report_timing/v7_sdt_top.rtr'

        globalfile = report('global10', '-delay_type min_max -report_exception TRUE -max_path 10 -nworst 1')
        allfile = report('crossings', '-delay_type max -report_exception TRUE -input_pins TRUE -max_path '+str(2*len(pp))+' -nworst 1 -from '+c.pinlist(p['launch_CLK'] for p in pp)+' -to '+c.pinlist(p['capture_D'] for p in pp))
        sig = [p for p in pp if '/host_bank[480]/' in p['capture_D']]
        if sig:
            report('signature4', '-delay_type max -report_exception TRUE -input_pins TRUE -max_path 8 -nworst 1 -from '+c.pinlist(p['launch_CLK'] for p in sig)+' -to '+c.pinlist(p['capture_D'] for p in sig))
        raw = globalfile.read_bytes()
        ss = c.summary(raw)
        minima = {k2: min((x['wns'] for x in rows), default=None) for k2, rows in ss.items()}
        records = c.paths(allfile.read_bytes())
        expected = {(p['launch_CLK'], p['capture_D'], corner) for p in pp for corner in ['slow', 'fast']}
        scored = [p for p in records if (p['start'], p['end'], p['corner']) in expected]
        coverage = {(p['start'], p['end'], p['corner']) for p in scored if p['MaxDelay_15_238']}
        ddr = bool(re.search(rb'^\s*ddrphy_sysclk\s+131\.2500\s+MHz', raw, re.M))
        old_async = bool(re.search(rb'^\s*cmos[1-4]_pclk\s+asynchronous', raw, re.M))
        timing = len(minima) == 10 and all(v is not None and v >= 0 for v in minima.values()) and all(p['slack'] >= 0 for p in scored)
        result = dict(status='PASS_FUNCTIONAL_ROUTE' if timing and retained and coverage == expected and ddr and not old_async else 'FAIL_REAL_TIMING_OR_COVERAGE',
                      timing_pass=timing, retention_pass=retained, minima_ns=minima,
                      critical_paths=c.paths(raw), crossing_records=scored,
                      expected_pair_corners=len(expected), covered_15238=len(coverage),
                      coverage_complete=coverage == expected, DDR131_25=ddr,
                      old_camera_async=old_async, route=str(routed),
                      route_sha256=f.r.sha(routed), map_sha256=f.r.sha(work/'device_map/v7_sdt_top_map.adf'),
                      CDB_sha256=f.r.sha(attempt/'native_CDB_raw.txt'), bit=False, program=False)
        f.save(label+'/RESULT.json', result)
        print('ACTUAL ROUTE RESULT '+label+' '+result['status']+' '+json.dumps(minima), flush=True)
        if result['status'] != 'PASS_FUNCTIONAL_ROUTE':
            f.save('GENBIT_FINAL21_FAIL.json', dict(result=result, bit=False, program=False,
                next='Review genbit-final native timing/IO paths'))
            return
        f.save('resume_genbit_final21_binding.json', dict(
            original_sha256=f.r.sha(f.E/'continue_functional.py'),
            resume_sha256=f.r.sha(__file__),
            route_result_sha256=f.r.sha(attempt/'RESULT.json'),
            genbit_binding_sha256=f.r.sha(attempt/'genbit_final_binding.json'),
            sbit_sha256=f.r.sha(bits[0]), sbit_bytes=bits[0].stat().st_size,
            timing_constraints_modified=False, program=False,
            rationale='gen_bit_stream produced the final routed database and the bitstream together; '
                      'the database passed complete native acceptance including the byte-identical IO table.'))
        previous_binding = f.E/'official_genbit_entry_binding.json'
        if previous_binding.exists():
            import time
            previous_binding.rename(previous_binding.with_name('official_genbit_entry_binding_archived_'+str(time.time_ns())+'.json'))
        f.save('official_genbit_entry_binding.json', dict(
            reference=str(f.E.parent.parent/'source_diagnostics_timing_build_03/runtime/prepare_local_delivery.py'),
            stage='gen_bit_stream', route_sha256=f.r.sha(routed),
            qualified_result_sha256=f.r.sha(attempt/'RESULT.json'),
            genbit_receipt_sha256=f.r.sha(f.E/'functional_genbit_receipt.json')))
        f.save('BIT_MANIFEST.json', dict(
            status='PASS_FUNCTIONAL_SBIT', source_binding=hashes, route=str(routed),
            route_sha256=f.r.sha(routed), controller_sha256=f.r.sha(f.E/'controller.py'),
            continuation_sha256=f.r.sha(f.E/'continue_functional.py'),
            bits=[dict(path=str(bits[0]), sha256=f.r.sha(bits[0]), size=bits[0].stat().st_size)],
            program=False))
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_GENBIT_FINAL21_FAIL.json', dict(error=repr(error),
            traceback=traceback.format_exc(), bit=False, program=False))
        raise
