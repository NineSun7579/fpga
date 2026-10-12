# Recorded local validation

Run from `project/fpga_v8_migration/cooperative_host`:

```
python run_coop_host_tests.py
```

PASS with MSVC x64 **19.44.35222.0**, linker **14.44.35222.0**. g++ was not
available on this session's PATH; no g++ or board compilation is claimed.
The Windows runner calls `build_local_selftest.cmd`, which initializes the local
VS2022 Community environment and executes:

```
cl /Bv /std:c++17 /O2 /EHsc /W4 /WX coop_host_selftest.cpp /Feartifacts\coop_host_selftest.exe /Foartifacts\coop_host_selftest.obj
artifacts\coop_host_selftest.exe --fixture artifacts\host.fixture
artifacts\coop_host_selftest.exe --map
```

The successful strict build has no warnings. The header is included first by the
selftest and uses only C++17 standard headers. Tests need neither Qt, OpenCV nor
RKNN. The runner preserves compiler identity/output and all selftest stdout.

```
COOP_HOST_PASS cases=51 checks=5085 writes=122 reads=1219 dma=25
```

All 122 control writes were checked for aligned physical address, exactly 16
bytes, allowed register address, correct little-endian low word and zero upper
96 bits. The 25 DMA calls exercise an in-memory fake, including unsuccessful
calls. These counts are **not physical DMA measurements**.

The clean success fixture has 3 producer descriptors, 120 control reads and 15
control writes. All 27 C++ register definitions match the endpoint JSON map.
The independent sibling Python FIFO model passes. ModelSim 10.6e compiles the
actual candidate endpoint/controller plus its existing public-interface testbench
into this directory's `artifacts/work` and passes **142 operations / 722 public
events**. No sibling source/artifact was written by this runner. The harness's
seeded upper write lanes test the adapter's ignoring them; the C++ write-zero
contract is verified separately by the fake.

Representative verified failure conditions:

- Missing external reservation, insufficient RX capacity, unaligned/overlapping
  slots, RAW/output aliasing and physical DDR overflow fail before transport I/O.
- Invalid/stale/reset-mixed descriptors retain possible ownership, with no DMA
  and no synthetic ACK. Completing the other bank cannot switch bound metadata.
- Error, partial, truncated or throwing DMA faults with no release. A complete
  owned frame remains stable after ACK, immediate RX/DDR overwrite, and bank reuse.
- Uncertain CLAIM/ACK writes fault without retry. Definite rejected ACK keeps
  Owned and permits only explicit valid retry. Delivery without response uses
  hardware readback instead of fabricated AXI OKAY.
- Post-ACK observation failure faults even if hardware released the bank; the
  independently owned frame survives. Destructors never ACK, and terminal fault
  calls issue no I/O. Twelve concurrent polls serialize to one successful CLAIM.

| Artifact/source | SHA256 |
| --- | --- |
| `coop_host_protocol.hpp` | `e890b59c33eec10c459ccf814edf6925a63faa5a3bc14c7f65724f82dfb0d2af` |
| `coop_host_selftest.cpp` | `486208045d55cf4d1c2e22ec24cf6d24e2b22ff9e4406f261cc4fb260e1fb863` |
| `artifacts/host.fixture` | `19440f500208abdb1dda0e3f78f7a42d2c53ef4286ac26da50085483d5925ad8` |
| `artifacts/selftest.txt` | `e3b6b196dca88c402b1282390a36cf31dbdd5355331629bbae941533de38b7c9` |
| `artifacts/expected.trace` | `2f41ca5f1abbb17a00ee0ab80d7aa438a91f6a8d946ae20c846598affb208ff4` |
| `artifacts/actual.trace` | `f20e6b04780978fe8b24f2fa56e02f22c7f8ef840147dedd5e6d9ebe1110c86b` |

`artifacts/results.json` records the full commands, compiler output, complete
source/dependency pins, event counts, stdout hash and executable hash. Source and
sibling dependency hashes were checked unchanged before/after the run.

Limits: no real PCIe, physical DDR, driver reservation/retirement guarantees,
board deployment, loaded FPGA endpoint availability, source capture stability,
full-top routing/timing, or live RKNN parity was tested. Current loaded M02 must
never be accessed by this candidate until the functional endpoint is installed
and verified externally. This helper grants no installed-support claim.
