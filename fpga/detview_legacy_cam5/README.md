# Legacy GPU viewer CAM5 validation source

`src/main.cpp` preserves the locally tested older six-camera GPU viewer, including
the RGB565 row-stride correction, retained double-buffer panes and per-camera
delivered-frame counters. It is an archival source snapshot, not a replacement
for the evolved full application in the repository root `detview_tdm/`.

The root viewer retains upstream HDMI, MVP-R1, tracking, temporal filtering and
calibration functionality. Complete matching source and validation for the later
display fixes are in `fpga/detview_display_fix/` and
`fpga/display_latency_delivery/`.
