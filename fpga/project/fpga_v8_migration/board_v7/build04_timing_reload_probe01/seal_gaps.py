from probe import E,sha,save
import json,re
F=E.parent/'build04_final_route_runtime01'
def raw(p):
 p=Path(p);return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p))
from pathlib import Path
logs=[p for p in (E/'probes').rglob('*') if p.is_file()]
report=E/'probes/diagnostic_reload02/report_timing/v7_sdt_top.rtr'
s=report.read_bytes().decode('utf-8','replace')
summary=dict(diagnostic_only=True,production_identity=False,old_async_rows=[line.strip() for line in s.splitlines() if re.search(r'^\s*cmos[1-4]_pclk\s+asynchronous',line)],budget_15_238_present='15.238' in s,MaxDelay_present='MaxDelay' in s,DDR131_25_native_observed='131.2500 MHz' in s,single_pair_rejected=True,report=raw(report))
save(E/'native_report_findings.json',summary)
methods={
 'official_no_prerequisites':'Explicit -input_db_file / -force_to_run help is real. MAP report_timing requires PNR phase (Flow-0013); official TA manual lists only PNR/PLC/Syn. Production MAP reload without prerequisites is blocked, not verified.',
 'mapped_graph_unchanged':'All production mapADF/native source and copied hashes remain identical around actual probes; no prerequisite flow detected. A successful replacement-CDB mapped graph reload is not established; graph export, if available, proves original graph only.',
 'old_group_absent':'Rejected: native diagnostic report still lists all four cmos_pclk asynchronous clock groups. add_constraint registration did not establish replacement.',
 'exact_U368_B4_364':'Only frozen offline coverageproof exists. No real post-replacement native exact 364 collection/clock relation proof.',
 'complement_exact':'Only frozen offline constraint memberships exist. No measured native post-replacement complementary collection proof.',
 'MaxDelay15.238':'Rejected: no native 15.238/MaxDelay, synthesis template pins rejected with Timing-4006 and STA-3016; single-pair options ignored.',
 'DDR131.25':'Native diagnostic report observes ddrphy_sysclk 131.2500 MHz, but replacement was not loaded and unchanged DDR multicycle cannot be inferred.',
 'same_domain_preserved':'No replacement-loaded native comparison. Existing diagnostic report is bound but insufficient to prove preservation.',
 'CDB_raw_binding':'Real original mapADF/native hashes and diagnostic rtr/rtr.db/rtp.adf bound. No successfully replacement-loaded production CDB exists.'}
coverage={k:dict(verified=False,method=v,raw_files=[raw(E/'probes/mapped_reload01/stdout.log'),raw(report),raw(E/'copy_manifest.json')]) for k,v in methods.items()}
save(E/'timing_reload_gaps.json',dict(schema='independent-physical-evidence/v1',kind='timing_reload',independent=True,reviewer='independent timing reload subagent; negative findings only',source_candidate_id='source_diagnostics_timing_build_04',contract_sha256=sha(F/'candidate_specific_expectation_contract.json'),map_adf_sha256=sha(E/'inputs/device_map/v7_sdt_top_map.adf'),replacement_clock_sha256=sha(E/'inputs/constraints/clock.fdc'),measured=False,gate_eligible=False,coverage=coverage,retained_clock_pairs=json.loads((E/'reference/coverageproof.json').read_bytes())['retained_clock_pairs'],next_action='Main-session separate fresh diagnostic PNR with replacement clock, or establish official TA CLI reload interface on routed DB; never mutate MAP phase. Rebind single-pair actual routed endpoints before reports. Production mapped coverage remains blocked even if diagnostic loading semantics succeeds.',bit=False,remote=False,flash=False))
save(E/'evidence_hashes.json',[raw(p) for p in E.rglob('*') if p.is_file() and p.name!='evidence_hashes.json'])
print('Sealed negative evidence; all nine coverage entries false; gate remains closed')
