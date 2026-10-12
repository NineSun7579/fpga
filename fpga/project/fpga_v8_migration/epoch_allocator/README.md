# Durable reset generations

`allocate_epoch.py` reserves a nonzero 32-bit generation under a Linux process
lock and commits it with file plus directory fsync before returning it. Allocation
never wraps, automatically initializes a missing journal or reuses an unsuccessful
reservation. It has no FPGA, DMA, reset or ARM side effects.

Provisioning is explicit. The physical reset-domain name and last-used upper bound
must be established externally. Zero is suitable only for an independently proven
unused domain. Never provision separate journals for two processes that control
the same FPGA, or restore an older journal after newer epochs have been used.
Storage loss/rollback requires authoritative recovery of the used upper bound.
The allocator cannot prove its own journal has not been rolled back.

The coordinating host reserves an epoch first, then resets all outstanding
capture/core/fabric/DDR/PCIe activity together, verifies quiescence and initializes
the new endpoint with that epoch. A timeout or uncertain DMA outcome requires
external recovery; allocating a number or issuing ARM does not retire old traffic.
The stable domain must identify the physical FPGA ownership/reset domain, rather
than a model file, PID, boot ID or executable name.

Tests run `python3 selftest.py` on Linux using temporary simulation-only journals.
They cover 64 concurrent process allocations, restart, missing/corrupt state,
wrong domains, storage errors, symlink rejection and exhaustion. This directory
does not establish the board's persistent production journal or reset wiring.
