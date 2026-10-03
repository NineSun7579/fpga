Physical constraint repair evidence (2026-10-02)

Cause: DevMap correctly retained FDC attributes and generated
device_map/hdmi_ddr_ov5640_top.pcf. The final runner started standalone
PNR without importing that PCF, so intent attributes survived while actual
PLACE annotations and implemented IO cell settings were wrong.

Confirmed supported phase API:
add_constraint -physical -pcf {absolute/generated.pcf}
pnr -input_db_file {absolute/mapped.adf} ...

Read-only extraction: copy database; mpnr -input {copy}; .switch_db
-input {copy} -output {text}. Audit actual INSTANNOTATE/PLACE annotations,
the referenced IO cell's IOSTANDARD/VCCIO/drive/slew/termination parameters,
external port-to-primitive connectivity, and HSST site/pad connections.
PAP_IO_LOC intent alone is not accepted as placement evidence.

bad_route_audit.json rejects all 40 implemented GPIO placements, 16 camera
IO standards, and four missing pull-ups. Isolated place-only run imports
the current generated PCF into a copy of the prior production mapped DB.
correct_place_audit.json has zero problems: all 40 GPIOs placed correctly,
all IO parameters match original FDC, ten dedicated HSST pads connect to
HSST_88_340 with channels 2/3 and reference clock 0. key1/key2 have no
external connections after optimization; their explicit LOC/IO constraints
remain in the validated 42-port PCF. Critical pins: P20/H12/E16/F16.
Physical IO digest: bdc8a0b0243e4632f1d239c3a9dcaa3007416e93acd8f91567db873deb1787b5

Production RTL/IP/FDC files were not edited. All 293 source/FDC hashes match
the prior final archive. Top SHA256:
f035cd6c9c81b881cdcb2a81110707d13b6030fd6bb916f1ffcd7376b438dd4c
TX SHA256:
79236044f0302db5227201b542aa073f778656672ef447f9731a50af79f4d230

Fixed runner: project/tools/build_50k_final.py plus audit_50k_physical.py.
It validates the generated PCF before PNR, archives the mapped input,
explicitly imports physical constraints, audits the actual original route,
audits the exact timing-modified route, and requires all placement and IO
digests to match before STA/release bitgen. Source/hash and existing full
production STA/clock/Gray CDC gates remain enforced.

Old archive bitstream_final_50k_20261002_222104 is preserved and marked
INVALID_HARDWARE.md. Do not burn its bitstream.

Fresh full build launched in a visible PowerShell terminal, runner PID 2624:
bitstream_final_50k_20261002_235509
Monitoring shell ID: sh_0fd53eb54001PRUJRyu2kZJ9BR
Final state: complete, physical_audit_passed=true. Final physical audit,
full STA, constraint preservation, and source audits have zero problems.
All 36,187 placements and IO parameters are identical in original/audited DBs.
Bit SHA256: 28259c9da062d4e4f332dbdb4c7711c88fe1a3986927aaab70b5da5eaa7e5354
Original route SHA256: d8c889b30f910fd863215b12559e12589eb0db34b20225ebbd14c95a1a184e36
Audited route SHA256: 288eeedece5fd9deef32e98cd7508fbc9de85020e28faa981ecf8a0c6ab8b760

JTAG scan independently confirmed PGL50H at device index 0. Authorized
reburn completed with the exact verified bitstream, programming 100%,
"The done bit is 1", and "cfg_program -device_index 0 successfully".
See the final archive's jtag_reburn.log and jtag_reburn_proof.json.
SFP/video functional behavior after reburn remains for the parent session
to inspect; no functional hardware success is inferred from JTAG DONE.
