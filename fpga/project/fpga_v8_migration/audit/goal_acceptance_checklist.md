# FPGA / RK3568 acceleration acceptance

The requested result is faster completed inference using FPGA and RK3568,
demonstrated on the specified wb_v8 model and identical physical RAW input.
Completion requires a validated integrated FPGA image, correct owned host input,
preserved video/motion functionality, and paired board FPS that includes camera
acquisition and handoff. Component passes and the existing RK3568 speedup do
not complete the cooperative FPGA objective.

## Requirement to evidence map

| Requirement | Concrete evidence | Current acceptance limit |
| --- | --- | --- |
| Specified PT/ONNX/RKNN identity and model semantics | `../artifacts/manifest.json`, README artifact hashes and graph/numeric audits | Identified; hardware full-network integer accuracy remains unaccepted |
| Same model / same input / strict detection parity | `../pipeline_board_runtime_compatible/`, `../host_acceleration/BOARD_RESULTS.md` | RK3568-only experiment accepted: 14.5684 to 16.0670 FPS; excludes acquisition/display |
| Unfiltered RAW feeds inference; preserve signed features and SiLU | Graph/numeric assets; `../capture_core_contract/REPORT.md`; `../whole_candidate_v2/README.md` | Simulated downstream stream certified; physical upstream image/format remains unverified |
| Retain all six video paths and four motion taps | Frozen motion inputs, v2 replay diff/interface audit, v2 source hashes | Source preservation passes; routed RAM/pins and board coexistence remain required |
| FPGA input bytes match software RAW preparation | `../capture_core_contract/artifacts/full_640x480/checker.json`, `../raw_preprocess/host_pair_artifacts/results.json` | Five simulated full pairs, 6,144,000 bytes; physical pairs not acquired |
| Owned RAW/output copies have identical complete source identity | `../capture_host/VALIDATION.md`, `../cooperative_host/VALIDATION.md`, `../paired_input_guard/artifacts_02/results.json` | Abstract transport/controller and retained fixture checks; live driver binding remains required |
| Dual leases prevent buffer reuse; matched releases only | `../capture_lease/`, `../capture_arm_contract/REPORT.md` | Actual RTL/FIFO simulation passes; live ownership/reset policy unestablished |
| ARM/SOF priority without combinational feedback | `../capture_arm_contract/REPORT.md`, `../whole_candidate_v2/README.md` | Corrected component/whole synthesis loops=0; routed and board behavior still required |
| DDR IDs/routes/backpressure correct | `../ddr_adapter_contract/REPORT.md`, capture/core fixtures | Actual generated FIFO evidence; vendor DDR scheduling is simulated |
| Control mapping and synthesized address rejection | `../cooperative_endpoint/register_map.json`, `../component_synthesis/endpoint_netlist_sim_01/REPORT.md` | Original connected component netlist passes 654 operations; whole mapped/physical decoder remains required |
| H2F completion after final accepted B; stable stalled writes and legal PCIe requests | `../pcie_h2f_transport_contract/REPORT.md`, v2 actual elaborated hierarchy | 50 simulated cases pass; actual hard-IP/MSI/Linux ordering unverified |
| F2H bytes stable in host memory before copy/ACK | PCIe F2H parity receipt, recovered host/driver audit | Controller parity passes; posted-write visibility/retirement remains unproven |
| Exclusive DDR banks, RX/TX buffers and protocol owner | `../driver_ownership_audit/README.md`, `../current_viewer_binding_02/snapshot_03.json` | Driver global ownership confirmed; runtime reservation not established |
| Persistent fresh generations and coordinated quiescent reset | `../epoch_allocator/` Linux selftests; exact v2 reset wiring | Allocator test journals pass; physical domain provisioning and reset certification absent |
| Full FPGA resources, clocks, pins and timing | `../whole_candidate_v2/`, `../whole_candidate_v2_route_01/README.md` | PnR completes; core setup -0.429 ns, hold -0.028/-0.015 ns slow/fast; all 611 failures retained; timing not closed |
| Current viewer source/executable binding and feature preservation | `../current_viewer_rebuild_02/README.md`, `../current_viewer_native_candidate_02/manifest.json` | Current baseline exact rebuild passes; candidate full build return 0, final audits pending |
| Native profile/runtime/output semantic correctness | `../viewer_native_runtime_probe/`, `../current_native_runtime_probe_02/certification_summary.json` | Current adapter board certification passes 120 strict cases/30 runs with zero error; full viewer orchestration remains unvalidated; active rotation models are unsupported |
| Isolated image identity, physical reset, byte correctness and coexistence | To be retained after routed validation and image generation | No candidate image loaded or board acceptance |
| Completed cooperative FPS improvement | Paired benchmark on shared physical RAW, same model, identical output checks, acquisition/handoff included | Not measured; no FPGA cooperative speedup claimed |

## Required order of remaining work

1. Complete routed timing/resource/pin/motion-RAM audit and preserve exact source
   and constraint binding. Address actual failures without hiding paths or changing
   the benchmark clock assumptions.
2. Establish the supported coordinated reset and persistent generation domain,
   quiesce all driver users, reserve the exact buffers and DDR banks, and certify
   H2F/F2H completion and timeout quarantine with the actual platform.
3. Generate and identify the isolated validated image; perform physical stream,
   byte correctness, ownership/reset, six-video and motion coexistence checks.
4. Feed both benchmark profiles the same complete physical RAW identity. Certify
   software/FPGA input equality, compare every completed detection, and measure
   acquisition through completed inference. Report sample counts, scheduling,
   failures and all excluded costs explicitly.

The current live driving-demo rotates trafficlight-16cls and wb_v4_combo.
The requested pinned wb_v8 acceleration candidate does not accelerate those
profiles. Their float paths and geometry/overlay features must remain intact;
testing the pinned target must explicitly select its exact file/hash.

Until these gates have real evidence, the session objective remains active.
