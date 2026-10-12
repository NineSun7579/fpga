"""ASCII byte edits only, applied to the isolated copied viewer."""
from make_six_batch import ROOT, replace

def main():
    root = ROOT / 'six_camera_batch_viewer_src'
    p = root / 'thumbnail_delivery.h'
    raw = p.read_bytes()
    raw = replace(raw, 'constexpr uint32_t RequiredCaps = 7;',
                  'constexpr uint32_t SnapshotCap = 8, SnapshotBytes = 304;\nconstexpr uint32_t RequiredCaps = 7;')
    raw = replace(raw, '    Transport& io;\n    uint32_t get(uint32_t reg) {', '''    Transport& io;
    bool batch = false, snapshotValid = false;
    uint32_t snapshot[SnapshotBytes / sizeof(uint32_t)]{};
    void invalidate() { snapshotValid = false; }
    void refresh() {
        if (!batch) return;
        invalidate();
        if (!io.readSnapshot(snapshot, SnapshotBytes))
            io.quarantine("six thumbnail snapshot DMA failed");
        snapshotValid = true;
    }
    uint32_t get(uint32_t reg) {
        if (batch) {
            if (!snapshotValid) refresh();
            check(reg <= Freeze && !(reg & 15), "six thumbnail snapshot offset");
            return snapshot[reg / sizeof(uint32_t)];
        }''')
    raw = replace(raw, '        if (!io.write(reg, value))',
                  '        invalidate();\n        if (!io.write(reg, value))')
    raw = replace(raw, '    uint32_t status() {\n        const auto value',
                  '    uint32_t status() {\n        refresh();\n        const auto value')
    raw = replace(raw, '    void configuration(int camera, int bank) {',
                  '    void configuration(int camera, int bank) {\n        refresh();')
    # Probe capability with existing scalar transport: old hardware never receives a snapshot.
    raw = replace(raw, '        check(get(SignatureReg) == Signature && (get(Caps) & RequiredCaps) == RequiredCaps &&',
                  '''        batch = false;
        invalidate();
        const auto signature = get(SignatureReg), caps = get(Caps);
        batch = (caps & SnapshotCap) != 0;
        check(signature == Signature && (caps & RequiredCaps) == RequiredCaps &&''')
    raw = replace(raw, '        put(Command, 3); wait(15, 11);',
                  '        invalidate(); // RAW tag DMA has reused metadata scratch.\n        put(Command, 3); wait(15, 11);')
    raw = replace(raw, '        identity(camera, bank, epoch, source, tag);\n        check(io.readTag',
                  '        invalidate(); // Never carry a snapshot over payload DMA.\n        identity(camera, bank, epoch, source, tag);\n        check(io.readTag')
    p.write_bytes(raw)
    p = root / 'main.cpp'
    raw = p.read_bytes()
    raw = replace(raw, '        bool write(uint32_t offset, uint32_t value) {', '''        bool readSnapshot(void* output, size_t count) {
            if (!output || count != thumbnail::SnapshotBytes ||
                !sixdma::scratchRange(sixdma::Metadata, count)) return false;
            DmaOp op{};
            op.offset_addr = sixdma::Metadata;
            op.ddr3_addr = thumbnail::Base;
            op.total_length = uint32_t(count);
            if (dev.ioctlTmo(F2H_CMD, &op, 2) != 0) return false;
            if (op.offset_addr != sixdma::Metadata || op.ddr3_addr != thumbnail::Base ||
                op.total_length != count) return false;
            std::memcpy(output, dev.rx_ + sixdma::Metadata, count);
            return true;
        }
        bool write(uint32_t offset, uint32_t value) {''')
    p.write_bytes(raw)
    print('Optimized isolated host transport/reader')

if __name__ == '__main__':
    main()
