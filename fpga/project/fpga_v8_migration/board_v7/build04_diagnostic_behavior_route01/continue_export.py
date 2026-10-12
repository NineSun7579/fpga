"""Continue export after the original controller's overly strict *.adf count.
Place & Route retains both PLC and final PNR ADF; neither is removed or rewritten.
No PNR or predecessor command is repeated by this continuation.
"""
import run_diagnostic as r
import ctypes,subprocess,sys,json
def main():
 r.GUARD=r.load(r.E/'protection_before.json')
 receipt=r.load(r.E/'pnr_receipt.json')
 if receipt['exit_code'] or receipt['implicit_predecessor_detected']:raise RuntimeError('Actual PNR failed; cannot continue')
 raw=(r.E/'pnr.log').read_bytes()
 if b'Process "Place & Route" done.' not in raw:raise RuntimeError('Official PNR done absent')
 route=r.W/'place_route/v7_sdt_top_pnr.adf';prr=r.W/'place_route/prr.db'
 if not all(p.is_file() and p.stat().st_size for p in [route,prr]):raise RuntimeError('Final PNR or native prr absent')
 r.save('actual_final_route_binding.json',{'final_route':str(route),'sha256':r.sha(route),'prr':str(prr),'prr_sha256':r.sha(prr),'PLC_also_retained':True,'continuation_reason':'Initial controller counted both *_plc.adf and *_pnr.adf; final artifact is exact *_pnr.adf. Original controller failure and artifacts remain intact. No tool rerun.'})
 r.idle('continuation_before_mutex')
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p;k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');exists=ctypes.get_last_error()==183
 if not h or exists:
  if h:k.CloseHandle(h)
  raise RuntimeError('Mutex busy')
 try:
  r.guard('before_continuation');r.idle('continuation_mutex_acquired')
  export=r.E/'functional';export.mkdir()
  code,raw=r.tool('functional',r.ARCH+'gen_netlist -force_to_run -input_db_file {'+route.as_posix()+'} -func_sim_only -sdf_annotate FALSE\n',export)
  graphs=r.E/'routed';(graphs/'synthesis_export').mkdir(parents=True);(graphs/'analysis').mkdir()
  code2,raw2=r.tool('graph',r.ARCH+'.switch_db -input {'+route.as_posix()+'} -output {'+(graphs/'synthesis_export/synthesis_dump.txt').as_posix()+'}\n',graphs)
  parser=r.B/'runtime/analysis_tools/parse_objects.py';r.shutil.copy2(parser,graphs/'analysis/parse_objects.py')
  res=subprocess.run([sys.executable,'-B',str(graphs/'analysis/parse_objects.py')],cwd=graphs/'analysis',capture_output=True);(graphs/'analysis/parser.log').write_bytes(res.stdout+res.stderr)
  r.save('export_result.json',{'functional_exit':code,'graph_exit':code2,'parser_exit':res.returncode,'routed_adf':str(route),'routed_sha256':r.sha(route),'functional_files':r.tree(export),'graph_files':r.tree(graphs),'parser_source_sha256':r.sha(parser),'diagnostic_only':True,'final_timing_acceptance':False,'bit':False,'remote':False,'flash':False})
 finally:
  r.guard('continuation_final');k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':main()
