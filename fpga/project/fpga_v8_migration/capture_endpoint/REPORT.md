# Isolated capture control-chain report

Status: **PASS**, ModelSim 10.6e, `python run_tests.py`.

The regression completed **499 operations, 4,288 matched public trace events,
26,488 clock cycles**. Both authored RTL modules compiled as Verilog-2001;
only the new testbench used SystemVerilog. RTL and TB compilation reported
zero errors and warnings. The simulator reported no errors; its existing
global `-novopt` setting emits the standard optimization warning.

| Public evidence | Count |
| --- | --- |
| Final manager/output-bank state snapshots | 499 |
| Full AW/W/B handshakes | 119 / 374 / 118 |
| Full AR/R handshakes | 367 / 622 |
| Router upstream local AW/W/B | 114 / 114 / 113 |
| Router upstream local AR/R | 361 / 361 |
| Capture child AW/W/B | 102 / 102 / 101 |
| Capture child AR/R | 279 / 279 |
| Cooperative child AW/W/B | 12 / 12 / 12 |
| Cooperative child AR/R | 82 / 82 |
| Config commands / actual acknowledgements / observed acknowledgements | 7 / 7 / 7 |
| Host descriptor claims | 3 |
| Host releases / actual acknowledgements / observed acknowledgements | 4 / 4 / 4 |
| Cooperative descriptor claims / bridge commands / source releases | 3 / 3 / 3 |
| Attempted source SOF contract events | 6 |
| Publication contract events | 4 |
| Retired-error contract events | 1 |
| Coordinated resets | 3 |

One downstream ARM response is intentionally reset while held, accounting
for the AW/B count differences. One host-release request has its downstream
token deliberately corrupted: the actual manager rejects it, the original
bound descriptor survives, and the rejection propagates as SLVERR. The later
correct release succeeds. All other releases retain their exact identity.

The child write channels exercised AW first on 39 writes and W first on 40;
the router upstream exercised AW first on 57 and W first on 30. Periodic
independent AW/W/B/AR/R gates and full B/R stalls tested routing and holding
slots. Read and write targeted opposite children concurrently, and a second
AW/W changed child route while the prior B was held.

Verified ARM cases include zero/current generation manager rejection,
fresh-generation acceptance, source-engine busy rejection, host-bound
rejection and source leases remaining after host release. Busy ARM never
queued behind leases, so the host could proceed with its required ACK.
An attempted SOF on the actual ARM dispatch edge was blocked by manager
`lease_block`; the manager did not receive a false admitted event. Actual
config and host-release acknowledgement delivery was delayed 80 cycles:
B waited and host-bound state persisted until the acknowledgement arrived.

Host RAW ownership cases include an offered-but-unclaimed release, empty/
wrong/high-bit/duplicate CLAIM, immutable eight-word bank0 metadata through
bank1 publication, a stalled descriptor response during that publication,
host-first and cooperative-first release ordering, wrong sequence/generation/
token/camera/bank ACK keys, high-bit camera/bank ACK keys, zero doorbells and
high-only/partial strobes. Before the valid bank0 release, the oracle and
actual register reads established ten bad ACKs and one manager-level release
rejection while both source banks remained HELD. Matched host release alone
retained the source for cooperative work. Matched cooperative release alone
retained the other source for host work. Only both releases freed each bank.

The real existing cooperative controller completed both output-bank CLAIM/
ACK sequences through route 0. Source identities came from the actual
capture manager's offered descriptor, but expected identities came from
the independent planned source-event records. All 128 seven-bit routed IDs
returned unchanged. Real 16-byte all-strobe writes with pseudo-random upper
96 bits performed exactly one selected low-word access; generation/ACK
staging did not trigger neighboring doorbells. Unknown and RO addresses
returned the proper child errors. Invalid physical windows/alignment/SIZE
and a 256-beat rejected write/read remained contained by the preserved
AXI128 endpoint. The prior finalized endpoint tests were not rerun.

Reset discarded an actual held ARM B together with manager/controller state.
A fresh generation was then armed; the same source bank/sequence with an
old-generation host ACK failed and the new matching key succeeded. Manager
retired-error count and a bad publication's protocol fault/disarm status
were verified through the register interface.

SV monitors checked X/Z on every full/local bus and manager/controller
output, including idle/reset and ungated child outputs; full and local
data/response/address stability under stalls; offered descriptor stability;
independent router ownership; and no guessed ARM/RAWACK B before an observed
manager acknowledgement. Python compared every planned operation/channel
against public accepted transactions and states without DUT hierarchy.

All **26 protected files** matched their initial and final SHA-256 manifests,
including every existing cooperative-endpoint file and simulation artifact.
The new module scan found unique declarations; its initial scan covered
9,762 preexisting RTL files using byte-level matching. Parent RTL hashes:

| Preserved dependency | SHA-256 |
| --- | --- |
| AXI128 endpoint | `5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e` |
| Cooperative controller | `fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae` |
| Capture manager | `04e908f9be9aa10ebf4eb19604d747c7dd7d2e48bd8aa52dbe069fc6e246865c` |
| Capture wrapper | `a69152c43fd67ae074c4801d778e2b0afab82b8af4c6695267a89e60d71b42d8` |

`register_map.json` fixes the 32 local/physical register mappings and STATUS
bits; `port_api.json` fixes named port widths/directions and chain bindings.
The runner validates both against the RTL before simulation. Results,
candidate/trace hashes, exact tool commands, initial/before/after source
hash manifests, tool logs and comparison evidence are in `artifacts/`.

Scope is the actual-manager/control-chain handshake and ownership boundary
with **injected source publication contracts and controlled bridge status**.
This run does not instantiate the camera/wrapper/FIFO/DMA or compare frame
bytes. It does not confirm a physical camera format, loaded upstream image,
camera-to-50K path, DDR capacity/content, global decode, host ioctl BRESP,
CDC, timing or whole cooperative acceptance. Parent stream/datapath/global
integration remains necessary. No PDS, SSH, IP or production source was
changed; all new files are under `capture_endpoint/`.
