from pathlib import Path
import json,re,sys,time
from runner import E,W,B,F,BOARD,ARCH,sha,save,guard
from native_audit import messages
def main():
 messages()
 p=E/'reports/report_timing/v7_sdt_top.rtr';raw=p.read_bytes()
 old_async=[i for i in range(1,5) if re.search(rb'^\s*cmos'+str(i).encode()+rb'_pclk\s+asynchronous',raw,re.M)]
 assert not old_async,'Native report retains old camera async'
 assert re.search(rb'^\s*ddrphy_sysclk\s+131\.2500\s+MHz',raw,re.M),'Native DDR requested frequency differs'
 pairs=json.loads((E/'mapping_native_pairs1280.json').read_bytes())['rows']
 expected={(r['launch_CLK'],r['capture_D']) for r in pairs};scored=[]
 for chunk in re.split(rb'(?=^\s*Startpoint\s*:)',raw,flags=re.M):
  a=re.search(rb'^\s*Startpoint\s*:\s*(\S+)',chunk,re.M);b=re.search(rb'^\s*Endpoint\s*:\s*(\S+)',chunk,re.M)
  if not a or not b:continue
  key=(a[1].decode('ascii'),b[1].decode('ascii'))
  if key not in expected:continue
  corner=re.search(rb'Path Type\s*:\s*max\s*\((slow|fast) corner\)',chunk,re.I)
  budget=re.search(rb'(?:MaxDelay|Max Delay|max_delay)[^\r\n]*15\.238',chunk,re.I)
  slack=re.search(rb'Slack\s*\((MET|VIOLATED)\)\s+(-?\d+\.\d+)',chunk)
  scored.append({'start':key[0],'end':key[1],'corner':corner[1].decode().lower() if corner else None,'exact_MaxDelay_15_238':bool(budget),'slack':float(slack[2]) if slack else None,'raw':chunk.decode('ascii','backslashreplace')})
 save('native_mailbox_exception_records.json',{'report':str(p),'report_sha256':sha(p),'records':scored,'old_async':old_async,'phase':'unrouted mapped DB, not PNR timing acceptance'})
 assert all(r['exact_MaxDelay_15_238'] for r in scored) and len({(r['start'],r['end'],r['corner']) for r in scored})==2560,'Native exact mailbox exception coverage incomplete'
 sites=json.loads((E/'native60_site_binding.json').read_bytes());assert sites['passed']
 source=json.loads((E/'sourcehash.json').read_bytes())
 assert all(sha(W/n)==h==sha(B/n) for n,h in source['hashes'].items())
 projectraw=(W/'project.pds').read_bytes()
 registrations=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',projectraw) if x.startswith((b'inputs/',b'rtl/'))]
 assert registrations==json.loads((E/'registration186.json').read_bytes()) and len(registrations)==186,'Actual project source registrations drift'
 save('source_current_validation.json',{'files':741,'byte_identical_build04':True,'actual_project_registrations':186,'project_sha256':sha(W/'project.pds'),'source_set_sha256':source['source_set_sha256']})
 guard()
 adf=W/'device_map/v7_sdt_top_map.adf';pcf=W/'device_map/v7_sdt_top.pcf'
 # Prepared input only; no PNR is executed by this task.
 nexttext=ARCH+'add_constraint {'+pcf.as_posix()+'}\npnr -force_to_run -input_db_file {'+adf.as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_in_route TRUE -fix_hold_violation_iterations 6 -report_timing\n'
 (E/'next_real_pnr.tcl').write_text(nexttext,encoding='ascii')
 save('actual_review_handoff.json',{'status':'PASS_FRESH_COMPILE_SYNTHESIS_MAP_NATIVE_REPLACEMENT_CDB','source_files':741,'source_byte_identical_build04':True,'registered_sources':186,'source_set_sha256':source['source_set_sha256'],'mapADF':str(adf),'mapADF_sha256':sha(adf),'PCF':str(pcf),'PCF_sha256':sha(pcf),'CDB':str(E/'mapping_native_CDB_raw.txt'),'CDB_sha256':sha(E/'mapping_native_CDB_raw.txt'),'clock_replacement_verified':True,'old_camera_async':old_async,'budget_ns':15.238,'fresh_pairs':1280,'native_MaxDelay_pair_corners':2560,'U_retained':364,'DDR_requested_MHz':131.25,'production60_sites':60,'next_PNR_script':str(E/'next_real_pnr.tcl'),'PNR_executed':False,'bit':False,'program':False,'original_PNR_failures_preserved':{'Setup':-.071,'Hold':-1.711,'Removal':-.038},'timing_acceptance':'Not granted; subsequent real PNR must resolve setup/hold/removal without new exemptions','actual_tool_rcs':{n:json.loads((E/(n+'_receipt.json')).read_bytes())['rc'] for n in ['compile02','synthesize02','mapping02','native_clock_exception']}})
 print('原生CDB与1280对/2560角15.238核验完成，60site，DDR131.25；下一轮PNR输入已交接',flush=True)
if __name__=='__main__':
 try:main()
 except BaseException:
  import traceback
  save('finalize_failure_'+str(time.time_ns())+'.json',{'traceback':traceback.format_exc()});raise
