"""Fresh official staged attempt; correct phase chain and new graph gates before PNR."""
import ctypes
import re
import shutil
import traceback
from pathlib import Path
import preflight
import physical_flow as flow

def main():
    base=preflight.HERE;root=base/'route_attempt_03'
    preflight.require(not root.exists(),'Preserve every real attempt')
    flow.wait_idle();flow.protected();preflight.verify()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.ReleaseMutex.argtypes=[ctypes.c_void_p];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance')
    preflight.require(handle and ctypes.get_last_error()!=183,'Another cooperating controller holds PDS mutex')
    try:
        root.mkdir();(root/'evidence').mkdir()
        before=flow.snapshot()
        shutil.copytree(base/'constraints_candidate',root/'constraints_candidate')
        original=(root/'constraints_candidate/clock.fdc').read_bytes()
        raw=(base/'project.pds').read_bytes()
        # Only this new project source paths become absolute; generated DB outputs remain local.
        def source_path(match):
            relative=match[2].decode('ascii').replace('\\','/')
            if relative.startswith(('inputs/','rtl/')):
                return b'('+match[1]+b' "'+(base/relative).as_posix().encode('ascii')+b'"'
            return match[0]
        raw=re.sub(rb'\((_file|_ip_source_item) "([^"]+)"',source_path,raw)
        raw=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw)
        anchor=b'(_option optimize_multi_corner_timing (_switch ON))'
        preflight.require(raw.count(anchor)==1,'Unique official PNR option block required')
        options=(anchor+b'\n            (_option gplace_seed (_integer 2))'
                 b'\n            (_option groute_seed (_integer 2))'
                 b'\n            (_option enable_route_constraint_iterate (_switch ON))'
                 b'\n            (_option route_constraint_iterate_times (_integer 3))'
                 b'\n            (_option route_constraint_slack (_double 0.0))'
                 b'\n            (_option route_constraint_max_timing_path (_integer 32))'
                 b'\n            (_option generate_bitstream (_switch OFF))')
        # Avoid an unverified s-expression datatype: iteration slack defaults to zero;
        # actual impl.tcl is retained and checked for every option reaching PNR.
        options=options.replace(b'\n            (_option route_constraint_slack (_double 0.0))',b'')
        raw=raw.replace(anchor,options);(root/'project.pds').write_bytes(raw)
        for name in ['manifest.json','routed_acceptance.py','targeted_reports.py','audit_physical_mailbox.py',
                     'audit_remaining_physical.py','prepare_local_delivery.py']:
            shutil.copy2(base/name,root/name)
        flow.HERE=root;flow.EVIDENCE=root/'evidence';flow.PROJECT=root/'project.pds';preflight.HERE=root
        flow.record('physical_settings.json',{'source_root':str(base),'source_snapshot':before,
            'project_sha256':preflight.sha(root/'project.pds'),'attempt02_failure':'DMR input rejected; official stages required',
            'seeds':{'placement':2,'route':2},'route_constraint_iteration':3,'RTL_FDC_content_changed':False,
            'remote_or_program':False,'bit_allowed':False})
        comp=flow.stage('compile','compile','compile','v7_sdt_top_comp.adf','Compile')
        syn=flow.stage('synthesize','synthesize','synthesize','v7_sdt_top_syn.adf','Synthesize')
        cg,ca=flow.export_graph('compile',comp,False);sg,sa=flow.export_graph('actual_pre_constraints',syn,True)
        proof=flow.derive(cg,sg,sa)
        preflight.require((root/'constraints_candidate/clock.fdc').read_bytes()==original,'Fresh graph generated a different constraint: do not continue')
        flow.record('coverageproof_synthesis.json',proof);flow.runtime_constraints(proof,sg)
        flow.stage('map','dev_map','device_map','v7_sdt_top_map.adf','Device Map')
        cg,ca=flow.export_graph('compile_post_constraints',comp,False);sg,sa=flow.export_graph('actual_post_constraints',syn,True)
        proof=flow.derive(cg,sg,sa)
        preflight.require((root/'constraints_candidate/clock.fdc').read_bytes()==original,'Map constraint bytes changed: no PNR')
        flow.record('coverageproof_synthesis.json',proof);flow.runtime_constraints(proof,sg)
        route=flow.stage('pnr','pnr','place_route','v7_sdt_top_pnr.adf','Place & Route')
        recipe=(root/'impl.tcl').read_bytes()
        flow.record('actual_pnr_option_binding.json',{'seed2_placement':b'-gplace_seed 2' in recipe,
            'seed2_route':b'-groute_seed 2' in recipe,'route_constraint_iteration':b'-enable_route_constraint_iterate' in recipe,
            'impl_sha256':preflight.sha(root/'impl.tcl')})
        preflight.require(b'-gplace_seed 2' in recipe and b'-groute_seed 2' in recipe,'Requested physical seeds not actually applied')
        cg,ca=flow.export_graph('compile_final_pnr',root/'compile/v7_sdt_top_comp.adf',False)
        sg,sa=flow.export_graph('actual_final_pnr',root/'synthesize/v7_sdt_top_syn.adf',True)
        proof=flow.derive(cg,sg,sa)
        preflight.require((root/'constraints_candidate/clock.fdc').read_bytes()==original,'Final PNR graph constraint mismatch')
        flow.record('coverageproof_final_pnr_synthesis.json',proof)
        flow.record('final_graph_constraint_comparison.json',{'same_generated_bytes':True,'physical_pairs':1320,
            'route_sha256':preflight.sha(route),'final_syn_sha256':preflight.sha(root/'synthesize/v7_sdt_top_syn.adf')})
        flow.runtime_constraints(proof,sg)
        flow.export_graph('routed',route,False)
        import audit_physical_mailbox
        audit_physical_mailbox.main()
        import audit_remaining_physical
        audit_remaining_physical.main()
        preflight.HERE=base;flow.HERE=base
        preflight.require(flow.snapshot()==before,'Attempt03 modified original registered input bytes')
        flow.HERE=root
        flow.status('ATTEMPT03_REAL_AUDITS_COMPLETE_SIGNOFF_REQUIRES_ALL_GATES')
    finally:
        kernel.ReleaseMutex(handle);kernel.CloseHandle(handle)

if __name__=='__main__':
    try:main()
    except BaseException:
        flow.EVIDENCE.mkdir(exist_ok=True)
        (flow.EVIDENCE/'official_attempt03_failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        flow.status('OFFICIAL_ATTEMPT03_FAILED_EVIDENCE_PRESERVED')
        raise
