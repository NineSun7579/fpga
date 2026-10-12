"""Independent physical retry from unchanged mapped DB; preserve attempt01 evidence."""
import ctypes
import traceback
from pathlib import Path
from preflight import HERE, BOARD, sha, require, verify
import physical_flow as flow

def main():
    root=HERE/'route_attempt_02';require(not root.exists(),'Do not overwrite physical attempt02')
    flow.wait_idle();flow.protected();verify()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.ReleaseMutex.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance')
    require(handle and ctypes.get_last_error()!=183,'Another cooperating controller holds the PDS slot')
    try:
        root.mkdir();(root/'evidence').mkdir()
        source=HERE/'device_map/v7_sdt_top_map.adf'
        require(source.is_file(),'Actual mapped input missing')
        before=flow.snapshot();dbhash=sha(source)
        helpfile=BOARD.parent/'whole_candidate_v3_timing_route_01/pnr_help.log'
        helpbytes=helpfile.read_bytes()
        flags=['-input_db_file','-gplace_seed','-groute_seed','-optimize_multi_corner_timing',
               '-fix_hold_violation','-enable_route_constraint_iterate','-route_constraint_iterate_times',
               '-route_constraint_slack','-route_constraint_max_timing_path','-generate_bitstream']
        require(all(f.encode() in helpbytes for f in flags),'PNR flag missing installed version provenance')
        script=root/'route.tcl'
        cmd=('pnr -input_db_file {'+source.as_posix()+'} -force_to_run -gplace_seed 2 -groute_seed 2'
             ' -optimize_multi_corner_timing -fix_hold_violation -enable_route_constraint_iterate'
             ' -route_constraint_iterate_times 3 -route_constraint_slack 0 -route_constraint_max_timing_path 32'
             ' -generate_bitstream FALSE\n')
        script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'+cmd).encode('ascii'))
        flow.EVIDENCE=root/'evidence'
        flow.record('physical_settings.json',{'help_path':str(helpfile),'help_sha256':sha(helpfile),'command':cmd,
            'source_map':str(source),'source_map_sha256':dbhash,'source_graph_and_constraint_inputs_unchanged':True,
            'attempt01_negative_setup_ns':[-0.882,-0.692,-0.159],
            'rationale':'All three Slow violations are camera2 paths dominated by routing. New placement/route seeds plus vendor route-constraint iteration; identical RTL/FDC.',
            'generate_bitstream':False,'remote_or_program':False})
        marks=flow.run('pnr_attempt02',[str(flow.PDS),'-file',str(script),'-work_dir',str(root),'-project_name','v7_timing_route_attempt02'],root)
        require(any('Place' in m and 'done.' in m for m in marks),'Official Place-and-Route completion absent')
        require(sha(source)==dbhash and flow.snapshot()==before,'Physical attempt changed frozen inputs or map DB')
        routes=[p for p in (root/'place_route').glob('*_pnr.adf') if p.stat().st_size]
        require(len(routes)==1,'One actual new routed ADF required')
        flow.record('actual_result.json',{'phase':'NEW_ROUTE_COMPLETE_REQUIRES_FRESH_GRAPH_AND_FULL_SIGNOFF',
            'route':str(routes[0]),'route_sha256':sha(routes[0]),'source_map_sha256':dbhash,
            'full_signoff':False,'bit_allowed':False,'remote_or_program':False})
        flow.status('ROUTE_ATTEMPT02_COMPLETE_PENDING_FRESH_AUDIT')
    finally:
        kernel.ReleaseMutex(handle);kernel.CloseHandle(handle)

if __name__=='__main__':
    try:main()
    except BaseException:
        flow.EVIDENCE.mkdir(exist_ok=True)
        (flow.EVIDENCE/'route_attempt02_failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        raise
