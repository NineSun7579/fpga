from build_candidate import *
# Completed v2 immutable 4175-file baseline is independently checked now;
# restore its original hashes to coverage, without changing any guarded file.
prior=json.loads((M/'whole_candidate_v2_route_01/protected_before.json').read_bytes())
assert len(prior)==4175
assert all(Path(p).is_file() and sha(Path(p))==h for p,h in prior.items())
before=json.loads((HERE/'protected_before.json').read_bytes())
save('protected_initial_v3_scope.json',before)
for p,h in prior.items():
    if p in before: assert before[p]==h
    before[p]=h
save('protected_before.json',before)
save('baseline4175_coverage.json',{'completed_v2_baseline_files':4175,'all_original_hashes_still_identical':True,'initial_scope_files':len(json.loads((HERE/'protected_initial_v3_scope.json').read_bytes())),'expanded_scope_files':len(before),'baseline_snapshot_origin':'whole_candidate_v2_route_01/protected_before.json','no_guarded_file_written':True})
verify_protected()
print('All 4175 original protected files unchanged; full coverage',len(before))
