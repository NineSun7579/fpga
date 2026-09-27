"""Record source identities for the current CAM3 build without altering sources."""
from pathlib import Path
import hashlib
import json

paths=[
 'source/top.v',
 'source/ov5640/ovreg_axil_decode.v',
 'source/ov5640/ov5640_ddr/ov5640_ddr_w.v',
 'source/axi_crossbar/ddr_w_arb.v',
 'source/axi_dma/axi_dma_write.v',
 'source/constraints/ov5640.fdc',
 'source/constraints/clock.fdc',
 'project_kf/project.pds',
 'sim/preprocess/cam3_decode_after.log',
 'drm_gate_test/fixed_sim.log',
]
result={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
Path('cam3_verified_sources.json').write_bytes(json.dumps(result,indent=2).encode('ascii'))
print('Recorded',len(result),'source and validation SHA256 identities')
