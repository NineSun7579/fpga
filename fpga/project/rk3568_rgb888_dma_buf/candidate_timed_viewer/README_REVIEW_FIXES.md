# Current scheme2 review revision

This revision addresses the independent review findings supplied by the parent.
All writes remain in `candidate_viewer`; no board calls or driver edits. The
old early-BEGIN ownership description in README_SCHEME2.md is superseded here.

## Queues no longer hold a kernel consumer lease

Acquisition still claims a published camera bank and validates RAW tag, camera,
source, epoch and publication against that same hold. Conversion completes on
that held RAW bank. It then releases the FPGA hold and restores selectors.
The token reserves the **converted FPGA DDR destination**, not an RX consumer
lease. No RGB input F2H or BEGIN happens during acquisition.

The single userspace admission gate stays occupied through analytics, GUI and
inference queues, preventing another viewer converter job from overwriting the
DDR destination. All other viewer camera reads use the original camera slots
and scratch below 4 MiB. Those reads remain available while the token is queued.
Cancellation simply retires that userspace reservation; it emits no BEGIN/END.
Exclusive driver ownership and absence of a separate converter owner remain
requirements. A second application bypassing that ownership is unsupported.

Coherent context initialization/query happens during model cache loading.
The first DMA-BUF import and binding happen on the inference worker **before**
BEGIN. In verification mode, the conventional CPU-reference run also happens
before BEGIN. After the last model-revision check, the inference worker's
`Input::consume` locks the shared transport mutex, performs the final RGB F2H
from the reserved destination, verifies bytes if requested, and immediately
issues BEGIN. No metadata/scratch operation can interleave. It sets
`consumerHeld` before releasing the mutex. The normal bound synchronous RKNN
run and decode finish before END. Context init, imports and queue waits no
longer extend global DMA exclusion.

Input import still uses full RX mapping base, offset `0x400000`, size 921600 for
height 480 or 1228800 for height 640. The driver reservation remains 1228800.
`candidate_driver/pango_zc.c` was inspected read-only: disjoint writes only
invalidate readiness on overlap, and only a valid 921600/1228800-byte input
transfer publishes the fixed reserved extent. No driver modification is needed
for this deferred F2H+BEGIN sequence.

## Model identity and atomic rotation

Admission metadata now contains exact model path, input height and monotonically
increasing model revision. The admission mutex owns next-selection publication,
arming, claim and occupied-state retirement. Retirement updates the next model
**before** making the slot available under that same lock. A newer revision
published during queue cancellation cannot be replaced by stale metadata.

The inference cache index advances only after the frame has been accepted and
run. Rejected geometry/model/revision/source frames do not advance it. Setters
invalidate old admission metadata immediately. A final revision/stop check under
`m_mutex` precedes synchronous consumption, so a setter cannot race between that
check and F2H+BEGIN. Cancellation does not falsely advance a model rotation.

## Independent coherent context contract and CPU route

Each candidate coherent context initializes from the exact original model bytes
with DISABLE_FLUSH_INPUT_MEM_CACHE, independently queries IO count, input attrs
and all output attrs, and compares them against the original context. Comparison
includes tensor index, dimensions, element/byte counts, format, dtype,
quantization, scale/zero-point/fractional length and stride metadata.

Only batch-1 packed NHWC native INT8 or UINT8 inputs `[1,480,640,3]` or `[1,640,640,3]` are
admitted. Width/height stride must be zero/default or equal logical size, and
size_with_stride must be zero/default or equal packed bytes. Other dtypes,
NCHW, padded strides, differing coherent outputs or query/init failures are
logged as `CPU_ROUTE ... coherent-contract-unsupported` before FPGA admission.
Native signed attributes are queried and compared unchanged. Binding constructs
an explicit UINT8 NHWC user contract with pass_through=0 so RKNN performs its
input conversion. This is subject to target validation with the standalone
probe below and then live DMA-BUF parity. Parent must inspect target model logs;
verification cannot claim output parity for models using CPU_ROUTE.

Import/bind failure before consumption also retires the unsubmitted reservation,
disables that shared context and sends later frames through CPU admission. The
first rejected frame reports inference failure. DMA, active-consumer and
uncertain RKNN failures retain quarantine semantics.

## Safe unpublished source

At the 3-second source-admission deadline, only exact status `1` (held, not
frozen/busy/completed/failed/quarantined) plus publication state `2` (unpublished,
drain idle) allows recovery. No converter job has been submitted. The viewer
releases the hold, checks idle/publication clearance, restores selectors, retires
userspace admission and returns no frame. Other deadline states remain
quarantined because cancellation/ownership is uncertain.

## Verification and local evidence

The existing opt-in parity controls and exact native-byte comparison remain.
CPU golden is computed from RAW copied under the original hold and retained by
the token. Input byte comparison now occurs after deferred F2H on the inference
worker, under the producer mutex before BEGIN. Native CPU-reference capture
precedes consumption. Bound native verification and its separate unchanged
float-decoder run occur inside the kernel lease. Performance sampling stays
disabled in verification mode. All receipt markers are hardware-test evidence
only when produced on the target; local fixtures do not establish RKNN parity.

Local tests now additionally cover:

- queued scratch DMA without BEGIN, then synchronous F2H+BEGIN and exclusion;
- queue cancellation with no RGB transfer and no BEGIN/END;
- same-height model revision change and rejection of stale rotation metadata;
- concurrent rotation retirement and fresh capture (100 repetitions), plus
  concurrent single-slot claims;
- packed INT8/UINT8 acceptance and unsupported dtype, padded stride, NCHW and quantization
  mismatch rejection;
- actual acquisition safe unpublished timeout/release/selector restoration and
  admission becoming available again;
- existing all-RGB565-value input golden, crop/padding, camera/geometry/MVP,
  native-output helper and classes-only syntax tests.

Local commands are in README_SCHEME2.md. After rebuilding the test units, run
`local_build/protocol_test` with RGB=1 both with and without VERIFY=1. Its timeout
case intentionally takes about 3 seconds. No target build/link, full OpenCV
VisionPipeline compilation or live hardware validation occurred in this session.

Parent should discard earlier source snapshots for deployment and rebuild this
revision. Driver receipt inspection and live importer/packed-contract/input and
native-output parity remain prerequisites to deploying the enabled path.

## Standalone runtime input-conversion probe

`model_contract_probe.cpp` is deliberately excluded from the viewer qmake source
list. It opens only the supplied model file and calls RKNN APIs; it has no PCIe,
DMA-BUF or FPGA calls. Parent can build and run it on the target:

```sh
g++ -std=c++17 -O2 model_contract_probe.cpp -lrknnrt -o model_contract_probe
./model_contract_probe /path/to/actual_MVP.rknn
```

Both contexts use default flags 0, preserving ordinary RKNN memory cache
handling. The original route receives UINT8 patterns through inputs_set; the
second allocates ordinary rknn_create_mem backing, copies those same bytes and
binds explicit UINT8 NHWC/pass_through=0. Independently queried native input and
output attrs are checked and logged before binding. Three deterministic patterns
cover unsigned values across the full packed input. Every returned native output
byte (want_float=0) is compared exactly. `ALL_3_PAIRS_PASS` validates runtime user
UINT8 conversion to that model's native input for ordinary memory. It does not
validate coherent DMA-BUF import, cache ownership or live camera parity; those
remain required before enabled deployment.
