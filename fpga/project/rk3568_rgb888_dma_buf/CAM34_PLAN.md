# C3/C4 shared recognition implementation

1. Isolated viewer copied from the verified per-model-geometry source.
2. Average each adjacent horizontal RGB565 pair; C3 occupies x=0..319, C4 x=320..639, retain all 480 rows. Final input is RGB888 640x480.
3. Reuse virtual-camera queue with latest owned buffers, generation and <=40 ms pairing skew; require both new frame sequences and <=100 ms age. Disable unrelated captures while the pair view is active.
4. Keep canonical padding for existing consumers, crop it before rectangular RKNN; render one shared detection region and log camera-specific original-coordinate boxes.
5. Run pixel/freshness/coordinate tests, ARM64 full build, real 640x480 model on RK3568, desktop screenshots and actual NPU input dump, sustained FPS logs.
6. Document that first version performs composition on RK3568 after two RAW DMA reads; no FPGA or PCIe-bandwidth reduction claim.
