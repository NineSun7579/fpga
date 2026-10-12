# Isolated concurrent candidate review

Only `candidate_concurrent_driver` and `candidate_concurrent_viewer` are changed.
They were copied from the current candidates, excluding viewer build outputs.
`original_sha256.json` records the originals at copy time. No board commands,
deployment, kernel-module loading, borrower changes, or ARM build were performed.

## Design and changes

The driver continues to serialize every PCI transfer with `pz.lock` held from
validation through MSI completion and the final DMA read barrier. The NPU's
consumer lease no longer excludes all PCI transfers: TX uses a different coherent
allocation and is allowed; RX is allowed only when its entire destination range
is disjoint from `[0x400000, 0x52c000)`. The reservation is always 1,228,800 bytes,
including the unused tail of the 921,600-byte MVP input. Wide overlap arithmetic
rejects crossing either boundary without overflow. Allocation bounds, alignment,
32-bit DMA address limits, and CPU-access exclusion are unchanged.

`g.pending` remains a barrier for every transfer. It represents export/BEGIN
publication across unlocked usercopy/export work, not DMA in flight. DMA is
protected by the mutex; BEGIN and END therefore cannot pass a running transfer.
No new pending assignment or unlocked DMA wait is introduced. END retains its
existing validation (including EINVAL for pending/wrong lease); the viewer's END
holds the same transport mutex as every PCI submission. `pz.active` is still IRQ
completion bookkeeping, not permission to bypass either lock or pending.

Readiness remains range based. Disjoint RX and TX preserve producer completion;
an overlapping RX without a lease invalidates it. Only a successfully completed
full-square or exact MVP read at the input offset republishes the full reservation.
END invalidates readiness, requiring a new producer read for the next BEGIN.

The viewer removes `consumerHeld` early returns from ordinary `regWrite`,
`regRead`, `ddrRead`, and `cameraRead`. Six aligned RAW slots and the metadata
scratch end at or below 4 MiB. All DMA submissions and scratch copies retain their
transport mutex; RAW slot CPU copying retains the existing one-worker-per-camera
ownership. `cameraReadFpga`, BEGIN overlap checks, and the occupied admission gate
are unchanged. Converter completion, camera release, and selector restoration
precede deferred RGB publication and BEGIN. Ordinary live RAW/tag reads cannot
start a second converter job. There are no ordinary `regWrite` call sites in this
main.cpp; converter writes use the guarded acquisition lambda. Allowing generic
TX at driver level does not validate arbitrary FPGA register effects.

## Exporter and attachment lifetime review

Exporter/map/unmap/release code is unchanged. The DMA-BUF export reference pins
the generation; DMA-BUF attachment/file ownership keeps that reference alive
until mappings and attachment users retire. The viewer Input backing pins its
transport and RX mapping across consumption. Explicit UNMAP/reallocation/export
and new CPU access remain blocked by the lease; mapped/exported state prevents
early deallocation. Attachment mapping still proves every mapped page resolves
to the original backing and rejects bounce mappings, with SKIP_CPU_SYNC used for
map/unmap. Thus attachment retirement introduces neither cache maintenance nor
bounce copyback onto concurrent RX. Existing quarantine behavior remains intact.

## Local evidence

- Seven existing bounds/ABI/lifetime source-contract tests pass.
- `local_concurrency_check.py` compiles the actual driver range/overlap,
  transfer, BEGIN and END bodies with host stubs. It passes six slots, exact
  boundaries before/after the reservation, crossing writes, full-window writes,
  unused MVP tail rejection, pending barriers, wrong token/range END, duplicate
  END, missing/stale producer readiness, CPU access, and BEGIN usercopy failure.
- Extracted actual PangoDev protocol executable passes flag-on, golden-RGB
  verification, and flag-off. Each of 12 leases (six cameras, two geometries)
  exercises ordinary metadata reads, register TX, and all six RAW-slot reads;
  compares the entire reserved slot before/after; checks RAW/tag identity,
  unchanged converter registers, and rejection of another admission claim.
  Existing cancelled-input, allocation failure and quarantine tests also pass.
- Classes-only Qt syntax compilation passes. This excludes the vendor-dependent
  entrypoint and is not a linked viewer/ARM build.

Logs and generated host test units are in each new candidate's `local_build`.
Host stubs do not validate IRQ ordering, DMA coherency, NPU execution, or timing.

## Remaining risks and parent validation

This is cooperative range ownership, not memory protection: existing writable
CPU aliases and a whole-RX DMA-BUF remain addressable. The unchanged borrower
must read only its declared input offset/length and perform no whole-buffer cache
maintenance or writes. The driver's begin_cpu_access still blocks globally.
The page-identity/no-bounce proof is essential for safe simultaneous disjoint use.

Generic TX remains capable of writing arbitrary FPGA registers/DDR. The current
viewer has no concurrent converter control path after sole admission; future
callers must preserve that rule and avoid modifying shared RGB destinations.
The host test's TX exercise is a simulated benign camera register write.

The mutex serializes PCI jobs but does not guarantee fairness. Camera traffic can
delay END or the next input publication, while PCI/NPU memory contention may
reduce the expected benefit. CPU RAW copying outside the mutex retains the prior
single-worker-per-slot assumption. Timeout/removal still quarantines the entire
generation; no cancellation or recovery policy changes are made.

Parent should build ARM viewer and module from these explicit new paths, retain
original restore artifacts, and validate live byte parity/native output pairs
and six-camera rates under concurrent NPU load before adoption. No hardware
performance improvement or hardware parity is claimed by this review.
