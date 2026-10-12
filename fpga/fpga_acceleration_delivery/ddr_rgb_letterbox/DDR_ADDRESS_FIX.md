The downloaded padding mismatch is an address-unit / burst-layout mismatch,
not evidence of a minimum two-beat DDR command requirement.

The generated x16 HMIC example increments `normal_wr_addr` by 8 for each
128-bit W beat (`ipcore/ddr3/example_design/rtl/test_wr_ctrl_v1_0.v:219`),
increments the initialization AW address by 128 for a 16-beat burst (:139),
and increments `normal_rd_addr` by 8 for each R beat
(`test_rd_ctrl_v1_0.v:250`). Its addresses count 16-bit DDR words.
The example random length generator permits AWLEN/ARLEN zero; there is no
source evidence here that single-beat commands are forbidden.

Byte-level inspection of the GBK top shows the AW and AR latch shims forward
`ddr_axi_*addr[27:0]` unchanged to `ddr3_*_addr` and then the encrypted IP.
No byte-to-word shift occurs. The production camera writer and PCIe reader
both use up to 16 beats and advance the bus address by beats * 16. Consequently
their shared layout has 256 contiguous physical bytes per 512-byte physical
slot. Preserve this existing layout and the source/destination base addresses.

The old candidate used AWLEN=0 and bus-address increments of 16. Its physical
write starts advance by 32 bytes: sixteen written bytes, sixteen untouched
bytes. A host burst16 sees exactly alternating written/untouched 16-byte
blocks. The downloaded first 153600 bytes contain 4800 even blocks entirely
114 and zero odd blocks entirely 114. The native-address regression reproduces
all 9600 block classifications exactly. The old reader also used this wrong
single-beat stride, so fixing only the writer cannot restore image pixels.

The endpoint now buffers up to 16 input/output beats and uses ARLEN/AWLEN=15
for complete bursts, advancing each bus address by 256. Final partial bursts
retain their real length and final byte strobes; no arbitrary RGB padding is
introduced. Bases require 256-unit alignment so bursts do not cross a 4 KiB
AXI boundary. The integrated fixed camera and RGB bases meet that requirement.
Already issued bursts drain after faults, and completion waits for the final B.

Tests:

- `python sim/test_ddr_address_contract.py`: native-word mapping, generated
  contract evidence, captured alternating padding signature, two full frames.
- `python run_tests.py`: ModelSim native-address model, full frames ready/stalled,
  partial bursts, burst boundaries, read/write/last faults and quarantined reset.
- `python run_integration_tests.py`: real MMIO/crossbar/seven-master arbiter,
  burst16 plus final partial burst, competing cameras and freeze admission.

Only isolated candidate files change. Production source/IP/project hashes are
checked by the endpoint suite. PDS and board access are left to the parent.
