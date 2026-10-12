# CAM1 runtime delay experiments

The original frozen bitstream and timing remain unchanged. Experiments write only CAM1 `0x20000030` to alter the runtime input delay shared by HREF, VSYNC and data. CAM2 is an untouched concurrent control. The reader at that address returns post-filter pixel count, so it is not a delay readback. Each completed experiment restores140. On any uncertain completion, submissions stop and mappings/fd are held, without attempting a restore.

The first A/B/A experiment completed without transfer errors. After2 seconds settling per step, each stage measured approximately7.8–8.0 seconds:

| Step | CAM1 source sequence delta | DDR short delta | Overflow delta | Published delta | CAM2 short delta |
| --- | --- | --- | --- | --- | --- |
|140|352|33|0|286|0|
|40|352|20|0|312|0|
|140|360|41|0|278|0|

Stable source-window samples were sometimes307199 at both settings, and one40-setting sample was307198.40 therefore does not eliminate the failure. Sampling counts are not a count of all physical frames and source/DDR endpoints are read sequentially, not atomically. No pixel-value validation was performed. A reduced short count in a brief stage is insufficient to select a production delay.

The primitive is configured `DELAY_STEP_SEL("PORT")` and wired to runtime `reg_dly_step` for all ten delayed input signals. Values0–255 are accepted by the RTL register. A further bounded sweep measures0,40,80,120,160,200,240, then restores140, with2 seconds settling and80 compact samples per stage. This is a diagnostic sweep, not hardware image-quality or full six-camera acceptance.

The sweep completed and restored140. CAM1 short-count deltas, in measurement order, were19,25,49,33,10,3,2,2. CAM2 short/overflow deltas remained0 in all stages; all CAM1 overflow deltas also remained0. Since the final140 stage was just as low as240, ordering/time drift is a confounder. No production delay was selected. A longer alternating140/240 repeat was launched to test reproducibility.

The longer alternating repeat completed and restored140. Each stage lasted15.7–17.1 seconds after2 seconds settling. In order140,240,140,240,140, CAM1 DDR short deltas were12,109,228,94,87. CAM2 short deltas remained0; both cameras' overflow deltas remained0. Stable CAM1 source samples at240 included counts as low as307193. Thus240 does not provide a reliable cure;140 also remains intermittently faulty. All completed control/read transactions returned ordinary success; no DMA timeout was observed.

Frozen decoder inspection also showed CAM1/CAM2 SCCB passthrough command offsets+0x100 and+0x300 route to the prep/motion segment, not the corresponding camera registers. Only special CDC stats reads+0x190..+0x1c0 are routed back. Existing cam3 SCCB scripts cannot be applied to CAM1/CAM2 without new decoder support; no sensor commands were attempted.

Next discriminating physical experiment: with both boards powered off, exchange the complete CAM1 and CAM2 camera+attached-cable assemblies at their100H board connectors; retain port-based FPGA settings. Reload the same V7 after cold start and compare source/DDR counters. A fault moving toCAM2 implicates the moved assembly or its interaction with that port; remaining atCAM1 points to the fixed port/logic path. Neither outcome alone identifies an electrical component. This experiment needs the user to perform the physical exchange; it cannot be done throughSSH.

## Superseding diagnostic direction

The user rejected hardware attribution and a physical swap. No hardware defect has been established by these traces; the swap proposal above is not an approved next action. Continue isolated actual-RTL simulation of source capture/counter/snapshot logic and the DDR frame-boundary valid/count decision. Preserve the running viewer and existing board configuration. Source count windows and DDR short counters are observations, not independent proof of a sensor/electrical fault.
