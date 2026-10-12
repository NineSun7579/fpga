# MVP accuracy round1 source handoff

This isolated source copy adds the `MVP-R1` alias for
`MVP_accuracy_round1_rk3568_int8.rknn`, discovered in `/root/npu/mvp`.
The parent session owns model files, metadata staging, target builds and deployment.

The deployment sidecar must be named `<actual RKNN path>.deployment.json`.
Use the delivered `deployment_manifest.json` unchanged as its contents; it is
already the supported profile format. The names sidecar, when supplied, must be
`<actual RKNN path>.names.json` with the delivered five-name JSON array.
The new filename requires the deployment sidecar. Existing models without one
keep their previous policy. A present sidecar with an unknown name, bad JSON,
missing/string/extra class thresholds, wrong input/class order/regmax/output
contract or wrong release SHA rejects model loading with a reason.

The supported manifest name is `MVP accuracy-first round1`. Its RKNN SHA256 is
`6cdfe6c8d834e2b99994633b483e048819a79c440562a2ea1ccbc55947be03e2` and its float
model SHA256 is `b418d1e662e661616866a0961a4401345fca89410fe8797740e79f2905bde272`.
The load path re-reads the sidecar and hashes the exact RKNN byte buffer before
passing that same buffer to `rknn_init`. A manifest copied next to old model bytes
cannot enable this policy. Runtime input and raw6 output shapes are still queried
and checked by the existing MVP model setup.

For this profile only, dequantized raw five-class logits undergo sigmoid and one
argmax per anchor. Candidates at confidence 0.001 undergo complete class-aware
NMS at IoU 0.7. The global score-ranked NMS result is capped at 300, then filtered
by `person=.35, vehicle=.45, zebra=.25, traffic_light=.35, traffic_sign=.40`.
There is no candidate truncation before NMS or replenishment after class filtering.
Existing uniform-confidence and IoU .45 policies remain unchanged. Shared and
independent lane models retain their existing contracts and decode paths.

The HUD displays the R1 class thresholds and NMS IoU. The confidence setting
states that class thresholds are fixed, with the active percentages in its hint.
`P/V/Z/TL/TS` mean person/vehicle/zebra/traffic_light/traffic_sign. Confidence
keys and setting arrows leave the policy fixed and show a status message.

Local verification passed:

```text
python mvp_decode_hostcheck.py --round1-package ../mvp_accuracy_round1_import_20261007
MVP_PRODUCTION_HOSTCHECK_PASS
ROUND1_IMPORTED_FILE_SHA_BINDING_PASS
ROUND1_DELIVERED_NMS_MATCH_PASS (all four scenarios)
```

The host check compiles the production methods verbatim, exercises the candidate
floor, five-class filtering, legacy policy, IoU selection and NMS cap order, and
compares production NMS/filtering with the delivered Python postprocess followed
by the documented global cap. It also hashes the imported model and checks the
compiled SHA binding with matching and altered-byte digests.

The target build should run `QT_QPA_PLATFORM=offscreen ./detview --mvp-round1-selftest`
and `--mvp-selftest`. These include Qt JSON/file metadata tests and actual file-byte
SHA mismatch rejection in addition to production decoder tests. Qt is unavailable
in the local Windows toolchain, so those Qt tests and the full target build have
not been run by this source-only subagent.

Changed files relative to `mvp_detview_src`: `main.cpp`, `detview.pro`,
`mvp_decode_hostcheck.py`; added `mvp_round1_policy.h` and this README.
