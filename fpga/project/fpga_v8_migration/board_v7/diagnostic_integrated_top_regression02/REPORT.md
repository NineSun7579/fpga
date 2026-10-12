# Build02 integrated full-top ModelSim regression02

PASS: exact09 golden and actual build02 integrated RTL each completed the unchanged original suite plus all four camera reset checks (14668 checks each). Both four-state traces match record by record after local reset, starting at 20 ns.

Compiled 243 RTL/IP/simulation-model files per variant. Build02 registers 186 sources; the actual reachable compile list includes 75 registered RTL/source files and 168 official IP/model files. This is a complete original full-top compile closure, not a primitive-only substitution.

Actual compile delta: 235 entries are byte-identical. Six entries contain the requested camera/control/lease/diagnostic changes or top lease-module binding. Two further files (PCIe FIFO and reset fault guard) have existing ASYNC_REG to syn_preserve/syn_allow_retiming attribute substitutions only; independent removal of attribute spans proves all remaining bytes identical. See actual_compile_delta.json. These are not hidden functional golden changes.

Build02 actual registered v7_sdt_top, camera wrapper/binding and matching registered parents are byte-copied into integrated/. Camera ov5640_reg comes from build02 inputs/source. The actual top binds fpga_v8_capture_lease_prefix at u_v8_capture_lease. Camera read decode, full-address control decode, lease prefix and explicit diagnostic 28 CE / 32 PE implementations are all compiled together. See replacement_contract.json, both compile.f files, registered_modules.json, hierarchy.txt and actual_parent_bindings.json.

Golden original source_diagnostics_top_candidate top, camera wrapper/binding, camera register, control and lease SHA256 exactly match frozen exact09 inputs. See golden_exact09_provenance.json. No golden functional edits or extra latency compensation.

Expanded trace compares 976 signal expressions in 36 groups: original top external outputs, AXI paths, all original camera outputs and camera register outputs, source and motion frame counters, cooperative outputs, all lease/control outputs, bank state, sequence, generation, claims/releases and config strobes. The original regression01 diagnostic monitor is also retained unchanged. See trace_fields.json and compressed traces. Internal redundant published-prefix predicates are excluded.

Sampling uses actual host/camera/control clock edges with 2/3/4/5 ps post-NBA offsets, including camera negedge launch observation. Time-zero primitive INIT differences are excluded by the existing local-reset start at 20 ns. Identical consecutive group records are omitted losslessly; SAMPLES records preserve every sampled-edge count.

| Trace | Records | Bytes | SHA256 |
|---|---:|---:|---|
| comparison.trace | 6792 | 14036839 | e5da4bf3e24ec027e319950d793378b336779ba3af12884e5235eb90593ec12f |
| integrated.trace | 8323690 | 1341671801 | 787c45fb650404edbfea6e54c9e84584cec48afb0e0efe44e199b9b9e8fb3426 |

Six real camera RTL structures and four real motion detector RTL instances are asserted from ModelSim loaded hierarchy. Motion history exists as four 8-bit x 19200 RTL arrays (32 bitplanes). There are **no 32 independent motion RAM primitive instances in this RTL**: history inference into 32 physical RAM resources requires synthesis evidence. This run cannot honestly assert 32 primitive instances or physical-resource acceptance; actual_parent_bindings.json explicitly records motion_physical_RAM_instances_verified=false.

Uses the unchanged original official DDR/IP/interface simulation models and existing official vendor ModelSim library; no new stub. Existing sim_order.py only normalizes declarations/active USE_OV5640 branch for ModelSim. Integrated views and their .diff files are regenerated from copied build02 registered sources.

Coverage limits: the original TB forces AXI/control clocks, DDR init and I2C completion, with free_clk stopped. Four full DVP source frames and original AXI register/reset/lease diagnostics are exercised; this does not verify complete DMA full-frame DDR writes, DDR calibration, PCIe training, raw transport throughput or end-to-end cooperative processing. No PDS, remote action, device access, synthesis, routing or physical timing acceptance. Existing warnings remain recorded in real logs.

Protected RTL/IP/config/scripts/evidence inputs: 3003 hashes unchanged before/after, including build02/runtime/controller sources. See frozen_before.json and frozen_after.json. Independent copies use read_bytes/write_bytes, preserving GBK bytes. No upstream source is modified.

Evidence: results.json, audit.json, actual_parent_bindings.json, actual_project_registration.json, optimization_lineage.json, golden_exact09_provenance.json, golden_sim_view_proof.json, replacement_contract.json, trace_fields.json, baseline/ and integrated/ compile/TB/simulation logs, hierarchy and .trace.gz. hashlog.json seals all delivered files except work libraries and itself.

Reproduce from workspace root: `C:/Users/NineSun/anaconda3/python.exe project/fpga_v8_migration/board_v7/diagnostic_integrated_top_regression02/run.py`, then `.../audit.py`. Only the isolated regression02 tree is written.

Real simulation warnings: baseline=633, integrated=633. Full messages are preserved in warnings.json and simulation.log; these existing connection/width/model warnings are not physical signoff.
