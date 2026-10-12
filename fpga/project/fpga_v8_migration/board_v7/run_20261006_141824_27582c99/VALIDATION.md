# V7 cold-start retest

The user confirmed both boards were powered off/on. RK3568 boot ID changed to `dd39b8d1-cf2d-404e-914d-45eb87278794`; old observer and its mappings no longer belong to this boot.

V7 was reloaded into SRAM with programmer success, single PG2L100H and final DONE=1. Frozen bit SHA256 is `dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`. Flash was not modified.

Rebinding the unbound RK PCIe host enumerated endpoint 0755:0755, Gen2 x2. The existing fixed driver was loaded from `driver/pango_pci_driver_fixed_20260926.ko`, SHA256 `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`, with measured loaded build-id `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`. This eliminates the identified late-snapshot window in this candidate; it does not establish a complete transport certificate.

Identity probe passed (COOP/CAPL/version, LAST_ERROR=0, RAW=0x182, banks FREE). Seven exclusive observations completed over 30.769 seconds, with no timeout and no new admission fault observed. Each H2F register write zeroed the upper 96 bits; last operation direction/address/length are retained. Observer closed mappings/FD after successful ordinary transfers.

Runtime audit did NOT pass: CAM1 tags advanced only 9 over the interval; every CAM1 motion snapshot had frame_error set and no valid comparison. CAM2–4 snapshots each advanced six times with seven comparison-valid samples and consistent bitmap/count/bbox. Tag deltas: CAM2 1386; CAM3/4 792; CAM6 1244. CAM5 unarmed, delta0 expected; dual-consumer leases and payload validation remain pending. Read-only SFP diagnostic status alternated55/63, requiring mapping review before causal attribution.

Evidence: `runtime/camera_observation.json`, `observation_audit.json`, `probe.log`, `last_operation.json`, `kernel_identity.txt`, and programming `receipt.json`/logs. The finite completion removes the earlier observed MSI timeout over this trace only; no sustained six-camera/physical RAW/COOP payload certification is claimed. CAM1 diagnosis is ongoing.

## Additional input diagnosis and recovery observation

Finite input reads and shortened source-window reads also completed. CAM1 had6 one-pixel-short inputs among44 stable source-window samples; CAM2 had50 stable samples, all307200 pixels. Sampled CDC drop counts remained0. CAM1 DDR short count grew7918→7949; overflow count0 and stored fault indicated307199 pixels. See `runtime/CAM1_DIAGNOSIS.md`; this does not identify the electrical or capture-logic root cause.

A later independent 30-second observation completed and passed all28 motion-record bitmap/count/bbox/frame-error checks. Each camera1–4 had7 comparison-valid records with6 sequence advances. CAM1 flags recovered to1/3, and its tag advanced1220, versus CAM2 1389, CAM3/4 794 and CAM6 1245. CAM5 remained unarmed. Original failing trace is preserved; recovered motion does not erase the verified intermittent source short frames. Followup raw trace and audit are under `runtime/followup/`. No DMA timeout occurred in any of these completed traces. Full RAW/COOP payload and lease validation remains blocked by the missing production completion/visibility evidence contract.

## Continued delay experiments and current device owner

Completed A/B/A140–40–140, eight-step sweep, and longer140–240 alternating repeat; all restored140 and completed without timeout. No tested value eliminated CAM1 short frames. CAM2 remained an error-free counter control in each measured interval. The repeated140 short deltas12/228/87 versus240 deltas109/94 demonstrate that the preliminary low-error240 stage is not a reproducible fix. See `runtime/DELAY_TRIAL.md` and retained traces/audits.

After the final trial released at kernel uptime1482.303, another client allocated mappings at1562.228. A non-DMA owner inspection identified PID3279 `/userdata/detview-driving-demo/detview-driving-demo --driving-demo --fullscreen --no-tracking --rotate-model trafficlight-16cls,wb_v4_combo`. This process was not started by these diagnostics. No new DMA client was opened after identifying this owner, and no viewer was stopped or modified. Further live DMA checks cannot run concurrently. Physical camera/cable cross-swap requires both boards powered off, followed by reloading the same frozen V7 and verifying new ownership/session conditions.
