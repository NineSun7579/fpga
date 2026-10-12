Prepared locally only. No SSH, remote build, RKNN run, board operation or calibration change is authorized by this preparation. Existing cache_parity/parity references remain unchanged.

The candidate is a complete frozen copy of direct_ingress/src, whose original main.cpp SHA256 is fb670f155d04ae90bab2ba44b7019de49a069bf5564bee097205324698ebab04. Only the exact cache_parity early --parity-selftest branch is inserted before --rotate-selftest and before controller/camera construction. Removing that branch reconstructs every original source byte. No worker/controller code is otherwise changed.

This prepares an actual RKNN shared-image comparison against the original baseline harness (619b6eb48a32ca26e99cdcde0101b494e4da788893b76a4e5174cde776948d86), reusing its existing private binary and complete source receipt. Both harnesses receive identical pinned 640x480 RGB888 scene bytes and the same pinned RKNN detection model. Baseline pads through its original square-input path; candidate uses its unchanged RAW worker preprocessing and output cache. Each scene gets three fresh process/model reloads per harness and three successful inference completions per reload. The established comparator retains full class/score/box tuples, repeat stability checks and positive detection evidence; empty-only matches remain inconclusive. Screenshot crops contain overlays, as recorded in the manifest. This covers the selected detection model and supplied images; lane/rotation/controller paths require separate acceptance.

The manifest pins all source files, original/reconstructed inventories, the branch, scenes, model, existing baseline binary/receipt, prepared tools/documents and inherited builder/board tools. Expected SDK header and runtime SHA256 values come from local host/detview copies; their equality to the target has not been observed. The later runner rejects a target mismatch before compilation, and verifies SDK/runtime/model/binary/scene hashes before and after inference. The candidate has no binary hash yet: its future private build receipt must match the complete frozen inventory and provide a binary SHA256 before execution. No fabricated candidate binary or target SDK verification is claimed.

Local static audit (safe now, no board imports):

```powershell
python project/performance_100h/ingress_parity/verify_local.py
```

Prepared command for the parent to launch ONLY after all observations, compiles and other parity runs end, and board access is separately authorized:

```powershell
python project/performance_100h/ingress_parity/run_later.py --after-observation --after-compiles --baseline-receipt project/performance_100h/parity/builds/619b6eb48a32ca26/receipt.json
```

The runner refuses the existing board-session lock, reuses baseline 619b, builds only the candidate in a private SHA directory with make -j1, and preserves the established cache_parity runner's reporting and credential handling. It has been syntax-audited locally only, and has not been imported or executed. Do not run it during local-only work.

Image parity bypasses VisionPipeline::inferenceRequested and the actual controller. A future `match` report cannot establish direct ingress, transition, pause or shutdown safety. Follow CONTROLLER_ACCEPTANCE.md on the deployed target separately; leave controller acceptance pending until evidence exists. Preserve camera calibration, driver configuration, deployed application and existing model assets throughout.
