from build_candidate import *
idle('before_explicit_physical_defaults')
assert not (HERE/'pnr_started.json').exists()
p=HERE/'project.pds'; data=p.read_bytes()
anchor=b'(_command cmd_pnr'
records=[b'(_option fix_hold_violation_iterations (_integer 500))',
         b'(_option fix_hold_violation_in_route (_switch ON))',
         b'(_option fix_hold_violation_threshold_for_clock_path_cross_srb (_integer 200))']
assert all(x.split(b' (_')[0] not in data for x in records)
p.write_bytes(data.replace(anchor,anchor+b'\n'+b'\n'.join(b'            '+x for x in records)))
(HERE/'project_before_pnr.pds').write_bytes(p.read_bytes())
save('explicit_defaults.json',{'records':[x.decode() for x in records],'basis':'Exact accepted CLI names and help data types; values are baseline defaults explicitly requested in handoff','timing_constraints_unchanged':True})
verify_protected()
