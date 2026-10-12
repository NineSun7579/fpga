from build_candidate import *
idle('before_export_after_outer_timeout')
route=HERE/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf'
before=json.loads((HERE/'final_export_02_started.json').read_bytes())
original=json.loads((HERE/'failed_export_01/final_export_result.json').read_bytes())['route_sha256_before']
assert sha(route)==original
save('final_export_02_interrupted.json',{'reason':'Outer background shell 120000 ms timeout terminated export before result receipt','global_pds_idle_verified':True,'route_sha256':sha(route),'route_db_unchanged':True,'previous_started_receipt':before,'work_retained':'final_export_02','new_work':'final_export_03'})
source=(HERE/'export_final.py').read_text().replace('final_export_02','final_export_03')
scope={'__name__':'resumed_readonly_export','__file__':str(HERE/'export_resume.py')}
exec(compile(source,str(HERE/'export_final.py'),'exec'),scope)
scope['main']()
