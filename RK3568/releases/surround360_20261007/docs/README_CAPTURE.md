# Surround360 capture

`surround::CaptureSource(bool synthetic = false, QObject* parent = nullptr)` is
a Qt Core/Gui capture worker. Construct it in the GUI thread, call `start()`,
and periodically read `snapshot()`. Call `stop()` before destroying the UI;
the destructor also interrupts and joins the worker. The class inherits
`QThread` and needs no additional moc generation or OpenCV dependency.
Build `capture_source.cpp` and `capture_selftest.cpp` with C++11 or newer.

Snapshots contain six owned 640x480 RGB888 `QImage`s, monotonic capture times,
successful frame counts (`sequences`), FPGA commit tags (`tags`), accumulated
read/rejected-frame errors, and measured FPS. Arrays are indexed from zero:
C1/C2 are a same-direction front stereo pair, C3 left, C4 right, and C5/C6
a same-direction rear stereo pair. Capture preserves both eyes; projection
selects one eye per module until stereo calibration exists. `producedMs` records the
latest successful capture or terminal error update. Images are initially null.
Snapshots are copied under a mutex and remain valid after later captures.
Qt image detachment also protects the worker when a caller edits its copy.

Board mode opens `/dev/pango_pci_driver` after acquiring an exclusive advisory
lease on `/tmp/surround360_capture.lock`. The lease prevents another copy of
this tool from opening the device. **Stop detview, camview, and any other
device owner before starting board capture**: older applications do not share
this lease, and the existing driver's open operation resets DMA state. The
parent launcher must coordinate those applications; this worker does not
terminate processes or reload/change the driver.

The existing driver ABI and DDR addresses are preserved:

| Input | Ping | Pong | Position |
| --- | --- | --- | --- |
| C1 | 0x00800000 | 0x00A00000 | Front 1 |
| C2 | 0x00C00000 | 0x00E00000 | Front 2 |
| C3 | 0x01000000 | 0x01200000 | Left |
| C4 | 0x01400000 | 0x01600000 | Right |
| C5 | 0x01800000 | 0x01A00000 | Rear 1 |
| C6 | 0x01C00000 | 0x01E00000 | Rear 2 |

Each bank holds 614400 bytes of little-endian RGB565 followed by a 32-bit
commit tag. The worker initializes the driver's TX/RX 4 MiB allocations using
MAP commands 0/1 and mmaps them at offsets 0/1 MiB. TX is never written or
submitted. All transfers use the existing F2H read ioctl. One RX frame slot
starts at zero; separate 16-byte metadata scratch starts at 0x3ff000. No DMA
request points to a stack or Qt image buffer. There are no FPGA register,
camera enable, NN, or H2F operations.

One worker visits C1 through C6 sequentially each round, capped at approximately
29.4 complete rounds per second. Slow rounds do not cause catch-up bursts.
Bank selection uses wrap-safe unsigned tag differences and skips unchanged
tags. Zero/zero is uninitialized before the first frame; a wrapped zero is
valid after delivery. The full-frame embedded tag and a separate post-read
tag must both match the selected commit. Rejected frames retain the previous
image. RGB565 conversion allocates independent RGB888 storage before RX reuse.

Unchanging sources retain their last image and are not counted as DMA errors.
Every five seconds `[capture]` logs FPS, tags, delivered counts, and errors
for all six inputs; rates include idle time. Open/map failures and six
consecutive failed capture attempts stop the worker and populate `error` for
the HUD. The GUI process remains alive. There is no automatic reopen or
hardware recovery.

On Linux, capture reserves process-wide `SIGALRM`/`alarm()` while board mode
runs. The non-restarting handler forwards alarms to the worker if delivered
to another thread, ensuring the blocked ioctl receives the timeout signal.
Do not use another alarm owner concurrently. Mapping ioctls use three-second
timeouts and read ioctls use two-second timeouts; shutdown waits for the current
capture attempt. As with the existing application, this depends on the
driver's blocking wait responding to signals. The previous signal handler is
restored and both mappings, device FD, and lease FD are released on exit.

Synthetic mode opens no device, installs no signal handler, and runs at 25
rounds per second. Each camera has a different color, grid, C1–C6/position
label, frame number, and moving white rectangle. Create `QGuiApplication` or
`QApplication` before starting it so Qt font rendering is available.

`surround::runCaptureSelfTest()` returns zero on success and prints
`CAPTURE_SELFTEST_PASS`. Invoke it after constructing the application's Qt GUI
application (on a headless host set `QT_QPA_PLATFORM=offscreen`). It checks bank
selection, wraparound, duplicate suppression, commit consistency, truncation,
RGB565 primary colors, image ownership, all six synthetic sources, camera-six
progress, snapshot immutability, and stopping the worker. It never opens the
board device. Actual DMA throughput and driver timeouts need a separately
coordinated board trial.
