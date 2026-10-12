# Model-specific finish validation

Run `python run_validation.py` here. Requires NumPy and ModelSim 10.6e (the default
path is `C:/modeltech64_10.6e/win64`). This directory is the only write destination.
The existing finish RTL and activation LUT are read-only compilation inputs.
No prior regression, full graph execution, production change or PDS run is used.

The runner verifies the numeric/task/calibration/specialized-model hash chain and
each of the 55 exported NPZ hashes. It validates shared unsigned16 multipliers,
signed32 folded biases, exact input-zero-point folding, and int32 raw bounds from
the actual int8 weights. The original release model is separately recorded.
The existing frame_01 trace must reference the same numeric.json hash.

The DUT uses LANES=2, matching the live CONV_CHA_PAR_OUT setting. Every task
programs its own exact 256-byte activation table while the complete pipeline is
idle, including all six Clip tasks and 49 SiLU tasks. Every real output channel
is exercised with its own folded bias. Fixtures cover conservative signed raw
bounds, tight achievable weight bounds, all-code-zero raw input, all-input-zp
cancellation (also modeling zp-filled spatial padding), trace extrema, signed32
extrema, reachable residues closest below/at/above Q16 half ties, and saturation
transition neighbors. Random inputs use the layer's actual frame trace min/max,
with 128 random words per task. Exhaustive 256-code lookup sweeps use model
coefficients and biases. Gaps, held source offers, long stalls, changing live
constants, bypass and last are checked against actual RTL handshakes. Searched
half-residue and saturation-transition fixtures also run with bypass so LUTs
that merge neighboring codes cannot hide a requantization mismatch.

Pair base channel c maps to s_data[31:0]/bias[31:0] for c and [63:32] for c+1.
The vectors retain group/channel positions and valid-lane masks. For CO=3, the
last real pair is channels [2,3] with mask 1 and bias[1]=0. No per-lane bypass is
available: the dummy lane still runs through the same table and is compared
physically. Only real lanes enter semantic comparisons; C16 serialization fills
dummy channels with output zero-point after masking. All pairs in a padded C16
group, including fully dummy pairs, are tested. Bypass is applied to the whole
word in dedicated tests; it never changes how a real Clip/SiLU fixture is checked.

C16 fixture shape is [1, CO, 1, fixture_count], using group/pixel/channel byte
order from feature_layout.py. Paired output positions are reconstructed and
compared byte-for-byte and by SHA256 against the codec's scalar-golden tensor.
These are synthetic fixture hashes, not hashes of the original frame feature maps.

The independent Python scalar uses unlimited integers and the exact exported
LUT bytes. Every vector is separately checked against the current
integer_reference.py Q16 expression and its extracted saturate_q16 function.
The simulation checker compares every valid cycle, including stalls, both
physical bytes and last. Unknown outputs and trace length differences fail.

`test_results/TEST_REPORT.md` records measured counts and limits. `manifest.json`
pins source, asset, constant, vector, stimulus and trace hashes. Per-task JSON
lists every channel, weight sum, raw bounds, masked padding and searched residues.
This proves exported-constant integration in the isolated finish primitive;
it does not validate full convolution MACs, legacy RAM wrapping, inference
accuracy, DMA, instruction scheduling or board behavior.
