"""Seal review-only files and check read-only source evidence; does not launch tools."""
from prepare_offline import HERE,B04,sha,save
import json,time
bindings=json.loads((HERE/'bound_reused_scripts_and_evidence.json').read_bytes())['sha256']
extra=json.loads((HERE/'additional_dependency_binding.json').read_bytes())
bindings.update(extra)
changed=[p for p,h in bindings.items() if sha(p)!=h]
guard=json.loads((B04/'evidence/runtime/mapping60_01/protection_before.json').read_bytes())['build04']
mapping_root=B04/'evidence/runtime/mapping60_01'
actual={p.relative_to(B04).as_posix() for p in B04.rglob('*') if p.is_file() and not p.is_relative_to(mapping_root)}
original_drift=[n for n,h in guard.items() if not (B04/n).is_file() or sha(B04/n)!=h]
inventory=json.loads((HERE/'actual_offline_inventory.json').read_bytes())
files={p.relative_to(HERE).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
save('review_bundle_manifest.json',{'schema':1,'candidate_id':HERE.name,'source_candidate_id':B04.name,
     'status':'REVIEW_ONLY_BLOCKED','time':time.time(),'files':files,
     'bound_source_drift':changed,'original_build04_outside_mapping_guard_drift':original_drift,
     'original_build04_file_set_unchanged':actual==set(guard),
     'source_guard_basis':'Original mapping60_01/protection_before.json; no mutation of build04 permitted',
     'gates':{'mapping60':False,'mailbox_unique1320':False,'derive_complete':False,'timing_reload_proven':False,'io_full_bank':False},
     'measured_mailbox_unique_pairs':inventory['unique_actual_pairs'],
     'pds_started':False,'pnr_started':False,'bit_generated':False,'device_operations':False})
if changed or original_drift or actual!=set(guard):raise RuntimeError('Input drift detected; review manifest records details')
