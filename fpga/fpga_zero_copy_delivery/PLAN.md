# FPGA offload implementation and comparison

## Scope confirmed by user

Implement FPGA preprocessing with shared host input memory and FPGA display
processing, disable the FPGA legacy NPU, and compare before/after performance.
RK3568 RKNN YOLO stays enabled. The clarification supersedes the earlier
interpretation that the user wanted to disable RK3568 inference.

Do not replace RAW camera banks used by YOLO. Display thumbnails are an
independent output. Keep the cam5 recovery, PCIe completion-order fixes,
DDR native address/burst contract and all six capture channels.

## Implementation units

1. Remove the legacy FPGA NPU hierarchy in an isolated integrated PDS project.
   Audit all tied-off interfaces. Unsupported old commands must not report a
   fabricated successful completion. Compare resources and timing with the
   prior integrated image; freeing LUT/DSP alone is not a CPU speedup.
   Source audit subsequently established that the running letterbox baseline
   already excludes legacy NPU instances and PDS entries. The candidate fills
   44 retired-master tieoffs, preserves camera/PCIe/delivery interfaces, and
   passed retained ModelSim fabric and cam5 hold/resume tests. Do not credit
   an additional NPU resource reduction relative to this baseline.
2. Audit and implement a compatible shared input memory path. PCIe must DMA
   into memory that RKNN can bind with the correct device mappings, extent,
   tensor stride/layout, cache synchronization and lifetime. Passing a PCI bus
   address as an NPU physical address without proof is prohibited.
3. Add an RGB565 640x480 to 320x240 display-only downscale output. At identical
   frame rate this reduces payload from 614400 to 153600 bytes per frame per
   thumbnail. These are arithmetic payload estimates until integrated and
   measured. Full-size selected preview and RAW inference need their own path.

## Baseline already collected

`host_baseline.json`: installed full detview PID4701 with RKNN active,
60.360 seconds, CPU209.591% (100% is one core), peak RSS177088KiB.
Installed low-latency application and current FPGA SRAM remain working.
Latest observed NPU/GPU frequencies were 900/800MHz; record frequencies in
the paired benchmark rather than assume they remain fixed.

`probe_shared_input.log`: actual RK3568 RKNN runtime successfully allocated
1228800-byte input memory, exported an fd, re-imported that fd and accepted
UINT8/NHWC input binding (return0). Logical and native input both reported
1228800 bytes. This probe did not open PCIe or execute inference; it establishes
only the RKNN API capability, not working cross-device zero-copy.
`shared_input_parity.log`: two distinct RGB fixtures compared normal inputs_set
with an imported RKNN shared input binding. Six native outputs per fixture,
1125600 output bytes compared exactly, with different fixture outputs confirmed.
This test still produces the shared input through CPU memcpy and is not a
PCIe-to-NPU zero-copy test.
The same parity check also passed at input offsets2097152 and2250752 bytes,
demonstrating actual runtime offset support for a dedicated RX input slot and
an additional80-row crop offset. Each offset compared1125600 native output bytes.
Matching kernel headers and Module.symvers are present under
`/usr/src/linux-headers-6.1-rockchip`, kernel.release6.1.99, matching uname.
The NPU has an IOMMU group, while the PCIe endpoint exposed no iommu_group link.
The import implementation must map for the PCIe device rather than reuse NPU
I/O addresses.

The first actual hardware smoke test (`pointer_pairs2_summary.json`, one warmup
and two timed pairs) verified the new2MiB RX slot, exact FPGA input byte parity
and exact native output parity. It deliberately still used inputs_set with the
borrowed coherent RX pointer, not DMA-BUF binding. Coherent-pointer inputs_set
averaged15.50ms versus0.73ms from ordinary CPU memory; it regressed sharply.
The sample is too short for a formal throughput result, but rejects the
userspace-pointer shortcut. The full viewer was restored as PID6263 after
ordinary completion, with no driver or FPGA replacement.

Current loaded driver Build ID was rechecked as
1102cfd04acaeeea21ca4d03fe27ddbb32b7340a. The recoverable fixed module is
`/userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko`,
SHA2560244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861,
vermagic6.1.99 SMP mod_unload aarch64. Identity receipt is retained.

The isolated pango_zc driver successfully built on actual matching Rockchip6.1.99
headers (moduleSHA256fc1ecd6dfbdef8e833f24e59ea7221701dd9e5815734fd7ad5ea1775f8ad960d).
The build warns GCC12.2 differs from kernel-build GCC10.3; no compile/link errors.
After cleanly stopping the viewer and unloading the old module, the new driver
loaded and bound to0002:21:00.0. Driver swap receipt is `driver_swap.json`.
Shared-input hardware smoke is in progress, not yet a successful zero-copy claim.
Update: the first attempt stopped before DMA because the ARM64 allocator
installs vm_ops. The driver now preserves allocator callbacks and relies on
backing file references for generation lifetime. Revised moduleSHA256
4506c0f7c3a3c6fb14315a03488ed2a9ec608a42eef7466a0c951983e91106f6
loaded successfully. The shared_pairs2 hardware test passed exact RGB and native
output parity using actual PCI DMA into the imported RX slot, with no app input
copy or inputs_set. Submission/lease0.01488ms vs baseline inputs_set0.68777ms.
Total stages33.20598ms CPU vs32.85116ms FPGA: only two timed pairs, insufficient
to claim a repeatable speedup. Viewer restored asPID8489. Initial240-pair run
overlapped a remaining make process, so rerun after all target compilation exits.
Coherent input contexts use RKNN_FLAG_DISABLE_FLUSH_INPUT_MEM_CACHE; producer
completion plus driver lease barriers publish device-written coherent memory,
avoiding inappropriate CPU-alias cache flush. Conventional baseline flags stay0.

Earlier same-input FPGA RGB888 preprocess result was 20.7620 versus CPU25.0570
inferences/s with viewer paused, not the live MVP rate. FPGA input delivery
18.293ms versus RAW DMA+CPU preprocess10.209ms. Shared memory may eliminate
host copies but does not eliminate the 1228800-byte PCIe RGB888 transfer.

## Evidence required for completion

- Actual RTL simulation for lossless stalls, frame boundaries and pixel parity.
- PDS synthesis/place-route result, resources, constraints and image hash.
- FPGA programming receipt and hardware control signature.
- Shared-buffer binding tested on the actual RK3568 runtime/driver. No hidden
  fallback copy may be labelled zero-copy.
- Frozen-frame input byte parity and detector result parity with RKNN enabled.
- Alternating same-condition live runs with process CPU, RSS, DDR/clock data,
  fresh display frames, actual transfer bytes, inference completion rate and
  per-stage wall time. Record faults and model identity.
- Preserve an original image/application rollback and leave the six-camera
  viewer working after testing.

Until these checks pass, describe partial units as candidates, not an achieved
hardware speedup or a completed zero-copy pipeline.
