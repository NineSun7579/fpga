# 100H Flash programming result

- Device: PG2L100H, device_index 0; JTAG clock 1MHz.
- Bitstream: project/bitstream_six_recovery_20261002_192245/top.sbit.
- SHA256: c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a.
- Outer Flash erase succeeded (20.3 seconds), program succeeded (89.7 seconds), readback verify succeeded (31.5 seconds).
- Evidence: log/100h_spi_program_verify.log.
- Reusable script: project/flash_100h_spi_verified_20261003.tcl.
- Power-cycle boot verification was not performed.
- Programmer window closed; task-owned JTAG server stopped after verification.

## Flash recognition support

The board description specifies XT25BF128FSSIGU-W, but repeated JTAG scans returned JEDEC ID 0x1c7118, including at 1MHz. ESMT's EN25QX128A (2X) datasheet revision 1.2, Table 6, gives this exact ID and 128Mbit capacity. The installed PDS flash table did not include this ID.

Added EN25QX128A to C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/arch/cdt/flash_list_cd.cfl with 128Mbit capacity, SPI X1 / 24-bit address, and datasheet timings: page program typical/max 0.5/3ms, block erase 0.3/2s, chip erase 60/200s. Page times use the same numeric convention as existing table entries (500/3000); the local read_me labels all timing units ms, inconsistently with its existing page-program entries. The added profile passed physical erase/program/readback verification.

Original table backup: log/flash_list_cd_before_100h.cfl. Datasheet: log/EN25QX128A_datasheet.pdf, downloaded from https://www.esmt.com.tw/download/EN25QX128A-2X-Ind?open=1.
No RK SPI switch or GPIO was changed.
