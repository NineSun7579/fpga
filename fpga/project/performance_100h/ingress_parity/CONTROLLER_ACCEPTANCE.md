Required target acceptance, not executed or claimed by this preparation.

Use the actual production Controller with the pinned direct_ingress source, deployed Qt/RKNN toolchain and unchanged camera calibration. The image --parity-selftest branch constructs only InferenceThread and does not exercise the controller. The local extracted gate/mailbox tests in direct_ingress/local_validation also do not execute full production configuration handlers, reset, destructor, VisionPipeline history/completion logic or SDK inference. Keep these evidence categories distinct.

After all observations/compiles end and target work is authorized, first compile the exact full inventory with deployed Qt (the context-bound invokeMethod functor requires Qt >= 5.10); retain source hashes, compiler version, build receipt and binary hash. Run existing camera, preprocessing, DFL, lane and vision selftests, retaining logs. These selftests remain supporting evidence, not controller acceptance.

For actual controller runs, retain matched settings/input/model identities, timestamped logs and a transition ledger. Exercise camera and video RAW sources, detector and lane selections, tracking on/off, stereo on/off and 2–4 model rotation. Compare the pinned output-cache variant under matching input/settings using nonempty and empty detections and lane masks. Verify per-model format/confidence and rotation context order. Do not modify calibration or substitute display/stereo/tracker images for RAW inference.

Exercise the real handlers while inference is busy and the vision worker emits requests:

| Transition | Required observation |
| --- | --- |
| C format toggle | Gate closes before setFormat; one generation increment per committed reset; RAW input preserved. C in rotation is rejected without disturbing the gate. |
| P / Space pause and resume | Closure precedes mutation; pause remains closed; resume commits one new generation and reopens only after configuration completes. |
| Camera selection | Valid selection closes before setMode; invalid selection leaves active gate unchanged. Old generation completions cannot populate new results. |
| Model selection | Closure precedes setModel/setFormat; pending old image cannot be dequeued with the newly selected model. Invalid selections preserve active gate. |
| Confidence change | Closure precedes setConf and reset; new work uses committed settings. Record already-dequeued work separately: it is not cancelled. |
| Rotation entry/exit | Valid 2–4 model entry closes before setModels; exit/model selection commits coherently; invalid entry leaves working gate unchanged. |

Use target tracing or an actual-call interceptor around production submission/dequeue/result delivery. Deliberately hold a request before dequeue, change models through the real handler, and observe pending clear before new-model dequeue. Hold a request already dequeued across reconfiguration and prove its old generation/frame identity is rejected by the actual completion/history path. Inspect the real VisionPipeline pending map across reset; check that rejection/failure releases pending work without deadlock. Preserve the ingress -> inference lock order and release ingress before vision failure replies. Record how delays are imposed and the exact instrumented-source/binary hashes; instrumentation requires its own evidence, not the image harness receipt.

Delay GUI event processing while vision emits requests: actual inference submission must continue without GUI dispatch. Deliver queued rate notifications after a configuration reset and verify obsolete generations do not refill the new rate window. Verify each committed configuration advances generation once. The GUI may display request-rate updates late during a backlog; this is distinct from delayed submission.

Repeat exit during capture, vision emission, model loading, completion and condition waiting. Observe capture -> vision -> inference joins, no access to destroyed controller/vision state, permanent closure preventing reopen, and no lost stop wakeup. Record existing capture/driver blocking behavior rather than claiming cancellation of blocked operations.

Acceptance requires retained evidence for every applicable row, stale completion/pending-map checks and shutdown schedules, with no deadlock, stale overlay/rate/result adoption or mixed-generation pending work. Compare service time, successful completion rate, GUI responsiveness and npu_request_fps under matched settings. No speedup or direct-controller safety is established by local static audit or shared-image RKNN parity. Mark missing schedules/modes unverified; never report the worker image match as controller coverage.
