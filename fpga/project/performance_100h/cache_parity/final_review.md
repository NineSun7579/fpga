# Independent local final review

Reviewed completed run `run_bf6d599692ac0dc4_1791077103421728300`. Verdict: exact detection-tuple parity is supported for the pinned current detection model and the bright screenshot crop. No source-pin, receipt, completion, or comparison discrepancy was found. The dark screenshot crop is empty-only and inconclusive for positive detection parity. This is a scoped result, not lane, multiple-model, mixed-model, or general output-cache certification.

Only this review file was written. Audit commands used local reads, SHA-256, Pillow crop comparison, and `python -B` to import `compare.py` without writing bytecode. No SSH, build, board execution, or verification-file rewrite was performed. `verify_local.py` and `run_later.py` were inspected but not executed.

## Recomputed results

Called the pinned `compare.compare()` on every baseline/candidate raw-log pair. Each entire returned comparison object equals the corresponding stored `report.json` object, including frames and tuples. Exact matching uses zero score/coordinate tolerance; the additional tolerance checks use score `1e-6` and coordinates `1e-4` pixels. Independently repeated the zero-tolerance comparisons across all reloads and frames; all four scene/harness stability results equal the report.

| Scene/reload | Baseline counts | Candidate counts | Exact tuple match | Positive evidence |
| --- | --- | --- | --- | --- |
| candidate_cam1_reload1 | 0, 0, 0 | 0, 0, 0 | yes | no |
| candidate_cam1_reload2 | 0, 0, 0 | 0, 0, 0 | yes | no |
| candidate_cam1_reload3 | 0, 0, 0 | 0, 0, 0 | yes | no |
| bright_baseline_cam1_reload1 | 2, 2, 2 | 2, 2, 2 | yes | yes |
| bright_baseline_cam1_reload2 | 2, 2, 2 | 2, 2, 2 | yes | yes |
| bright_baseline_cam1_reload3 | 2, 2, 2 | 2, 2, 2 | yes | yes |

All 12 raw logs contain exactly one successful load and the successful summary `{event: summary, requested: 3, completed: 3, errors: 0, rc: 0}`. `compare.parse()` validates all 36 sequential frame completions and detection counts and rejects error events, unsuccessful loads, and nonfinite tuples. The request contains precisely the expected 12 jobs; report result events match their scene/kind sequence with all process return codes zero, followed by `finished` with `hashes_verified_before_after: true`.

The following two tuples are identical in every bright frame in both harnesses: 3 frames × 3 reloads × 2 harnesses = 18 positive frame completions. Tuple columns are `(class, score, x1, y1, x2, y2)`:

```text
(1, 0.586596847, 203.950729, 250.829865, 671.067871, 562.769348)
(1, 0.377569348, 65.0481262, 193.934799, 522.816711, 592.861084)
```

Coordinates are the existing decoder's model-input coordinates, with the manifest describing a 640×640 input and gray114 padding at y=80. This verifies emitted detection tuples, not raw output-tensor equality or annotated ground-truth accuracy. The screenshot crops retain labels/display overlays.

## Source, receipt, and input chain

Rehashed all complete baseline and candidate harness inventories against the manifest; independently recomputed their JSON-inventory snapshot digests. Both report build objects equal their on-disk receipts in full. Receipt source inventories match the manifest and the local source directories named in the receipts. Both build receipts' archived `source/` inventories also match. Both archived build logs hash to their receipts' build-log pins. The reused baseline receipt hash matches `reused_baseline.json`.

| Pin | SHA-256 |
| --- | --- |
| Manifest | `bf6d599692ac0dc495b5425cc5ec1ba8b5fc66dc1bac4397af752e8e51ce808e` |
| Report | `ba69592c6bc10186f5cd09b31641e699b4fa42c2ab1268104c2d121b65547436` |
| Request | `fab34ce71434e2c3eda80817ce1775943b6979273b8ef691df12d0f027f739b6` |
| compare.py | `444876c24cd8601c23f692b4cd7d52b0f193959050f59e21e2e47c5b6e59914d` |
| Baseline harness snapshot | `619b6eb48a32ca26e99cdcde0101b494e4da788893b76a4e5174cde776948d86` |
| Candidate harness snapshot | `d287796f1ef146db541cc62ba646211c3ca0894436476151b2c4f3baeae1991e` |
| Baseline receipt | `3f9177ee1ef4da543192cf8dace919ef108384480a70044f1dc98b1420f4d643` |
| Candidate receipt | `ab35027067727a8f3900e3855298f6b669b15e4d20650681dc468d809b2ae026` |
| Baseline build log | `30f5b8a3720406a0ed66e69a8cd5b63b637ab7f606ee4653aefa74179187fb7a` |
| Candidate build log | `1a8647063d406dc9504df211a823a79f8feaf96984bce73f2052d80a18677d19` |
| Baseline binary, receipt/request pin | `5887fc2d32734b234e1005d020c781fa2f0f47f4d9ef607790fc1315025c8c03` |
| Candidate binary, receipt/request pin | `ab0652c66a576daf4b02298ab46a0fb0c2561358718aa88ca4ab567e3034c768` |
| Current model, manifest/request pin | `21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31` |
| Dark crop candidate_cam1.png | `f32cd160163a500df3885af311b23a82783b6aaad14fae2cbd4adf037d93a0ee` |
| Dark source screenshot | `7701625dd970d3722ea2e1842360bd11ec6306aa521b100f5ea026cb84e0bb95` |
| Bright crop bright_baseline_cam1.png | `f914a521b554307ab90f3fa93f7233da21b22503dc9c454ad72174197b8afb86` |
| Bright source screenshot | `06b3286754daef4e587cd82450ad84c02f76ab83db3b1cbaefc095a0b1b10ffc` |

Every prepared-tool hash matches the manifest. Image bytes and original screenshot hashes were independently recomputed; decoded RGB crop pixels equal the original screenshots cropped at the manifest rectangles `(0,68,640,548)` and `(0,60,640,540)`, respectively. Both crop dimensions are exactly 640×480.

Request model path is `/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn`; its pin equals the sole manifest model asset. Request binary paths and hashes equal the receipts. Every request image path/hash maps to the expected manifest scene. The inspected sealed runner hashes every request pin before and after all subprocesses and invokes each job separately with `--parity-selftest IMAGE --model MODEL`, explaining the three process reloads per scene/harness.

Evidence boundary: there are no local `detview` binary copies under `performance_100h`. This audit independently verifies local sources, receipts, build logs, request consistency, and raw-log computations. It relies on the retained runner's `finished` event for remote model/binary/image hash verification; it does not independently reread remote binaries or the remote model. Receipts and logs are retained evidence, not cryptographically authenticated attestations.

## Output-cache scope and unchanged worker

Candidate original main pin is `1ff7a8400a7a8dd48834ed56a740579ba93efce48a8b79687bf18085efbc71b9`, with original source snapshot `400bdadbec3e38dfbd1c59dc3c1483d4f34d0bbb328555a393efe5df0e5a641c`. Harness main is `0e9cd0e4366fddc83d88d041f169ad637259810519427d03087de099243e65a0`. The exact inserted early branch hashes to `11f250fdc8fc7e58d47745ccaeac15eff361ac91b8a427cbc07aa14a9ccbfc45`; removing just that block before the `--rotate-selftest` anchor restores the original main hash and complete original source inventory/snapshot. Consequently the candidate inference-worker body and all other source files are byte-identical to the pinned output-cache candidate. The harness-only change dispatches before camera/controller construction.

All 12 actual SDK load messages say `4 outputs cached`. The filename's `dfl6` does not establish six RKNN outputs. The inspected candidate worker emits this message from queried `ioNum.n_output` after successfully querying each output attribute and constructing the cached model. The measured model therefore exercised four cached output descriptors/attributes. The worker resets descriptors with `want_float = 1`, gets SDK outputs, decodes, releases outputs, then clears descriptors; this review does not claim native/preallocated output-mode coverage.

The harness selects exactly one non-lane detection model and calls `worker.setModels(chosen)`. Coverage comprises the existing baseline controller-padded-square path versus the pinned candidate raw-RGB worker preprocessing/cache path on two still-image crops, three repeated submissions per fresh process. It does not exercise lane-mask decoding, round-robin multiple-model scheduling, mixed models, in-process model changes/reload invalidation, forced SDK failures, live camera/display behavior, long-duration pointer lifetime, or cache performance. Matching output does not isolate the cache change from other differences already present between the baseline and candidate snapshots.

## Raw-log hashes

All paths below are within the reviewed run directory. These hashes were computed during this independent review; the original report does not seal raw-log digests.

| Raw log | SHA-256 |
| --- | --- |
| candidate_cam1_reload1_baseline.log | `3fd35cbdf1defd95131e8ed7b0727143607dd26283bc4d7069c1af0cf53ed68c` |
| candidate_cam1_reload1_candidate.log | `baa5f71eaafb730350b29b0f52007a27734dbb68b7e8c987359909564bb8f3f3` |
| candidate_cam1_reload2_baseline.log | `d56060569ff2985d52764be424d2e52aaf40a6b7543b8185f7220e688f500277` |
| candidate_cam1_reload2_candidate.log | `fe44719fd9bdceff97fe91f178766c789ada0d9c7bce232a56e8956b35fe737f` |
| candidate_cam1_reload3_baseline.log | `e594fa93680eada1dfceead13a825149486d066f6582a54a1d6f031c67a4eb5d` |
| candidate_cam1_reload3_candidate.log | `487a1af76e69cb2832eafa5a1dcfc0aa72858bfcf69d3b5306057d2007383846` |
| bright_baseline_cam1_reload1_baseline.log | `40cf1c8382227c9d95019200f0a3cd6f3046668a402f7fa823754a332c8036b2` |
| bright_baseline_cam1_reload1_candidate.log | `f68941afc48a7db96f3f8dd4656ad51075c87c9adf9e5e0d28fc9f4138bf31c8` |
| bright_baseline_cam1_reload2_baseline.log | `802a683d4854fda560909363ad25e74167ca207897e5a5e94158a67e289e389b` |
| bright_baseline_cam1_reload2_candidate.log | `91ea93b51cc1b90e38011550b200c3e183b6a97bf1a0e8ba98b70f239ebbfcad` |
| bright_baseline_cam1_reload3_baseline.log | `cbae0c76b48d00ff6e56393b96a4f415e956d04257875ede3401c98cfe48032d` |
| bright_baseline_cam1_reload3_candidate.log | `d8588b66e481aa414ba818df19f0978bc959ec638ab60318455436c008472ec4` |

No defect was found in the locally auditable completed-run parity evidence. `report.status = match` is justified by the bright positive tuples within the stated scope; treating dark empty frames as positive proof, assuming six actual SDK outputs, or claiming lane/multiple-model/mixed-model coverage would exceed this evidence.
