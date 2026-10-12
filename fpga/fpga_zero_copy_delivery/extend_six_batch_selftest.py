"""Extend copied host selftests with byte-level edits; leave baseline untouched."""
from make_six_batch import ROOT, replace

def main():
    p = ROOT / 'six_camera_batch_viewer_src/thumbnail_delivery_selftest.cpp'
    raw = p.read_bytes()
    raw = replace(raw, 'struct Fake {', '''struct Fake {
    static bool defaultBatch;
    bool batching = defaultBatch;
    int snapshots = 0, failSnapshot = 0, mutateSnapshot = 0;
    uint32_t mutateReg = 0, mutateValue = 0;
    std::vector<uint32_t> snapshotStates;
    bool readSnapshot(void* output, size_t count) {
        if (!batching) throw std::logic_error("snapshot sent to old hardware");
        if (!output || count != SnapshotBytes) throw std::logic_error("snapshot size");
        ++snapshots;
        snapshotStates.push_back(state);
        if (snapshots == failSnapshot) return false;
        std::memset(output, 0, count);
        auto* words = static_cast<uint32_t*>(output);
        for (uint32_t reg = 0; reg <= Freeze; reg += 16) {
            if (reg == Command || reg == 0x70) continue;
            if (!read(reg, words[reg / 4])) return false;
        }
        if (snapshots == mutateSnapshot) words[mutateReg / 4] = mutateValue;
        return true;
    }''')
    raw = replace(raw, 'case Caps: value = badCaps ? 3 : RequiredCaps;',
                  'case Caps: value = badCaps ? 3 : (RequiredCaps | (batching ? SnapshotCap : 0));')
    raw = replace(raw, '};\n}\nint runSelfTest()', '};\nbool Fake::defaultBatch = false;\n}\nint runSelfTest()')
    raw = replace(raw, '    Fake healthy;', '''    for (bool batchMode : {false, true}) {
    Fake::defaultBatch = batchMode;
    Fake healthy;''')
    raw = replace(raw, '    Cursor raw, display;', '''    if (batchMode) {
        expect(healthy.snapshots > 0 && healthy.copies == 1, "caps bit3 enables snapshot transport");
        std::fprintf(stderr, "BATCH_HEALTHY snapshots=%d scalar_or_model_reads=%d states=", healthy.snapshots, healthy.reads);
        for (auto state : healthy.snapshotStates) std::fprintf(stderr, "%u,", state);
        std::fprintf(stderr, "\\n");
        for (int n = 1; n <= healthy.snapshots; ++n) {
            Fake io; io.failSnapshot = n;
            expect(execute(io) == -1, "each snapshot failure quarantines");
        }
        // Corrupt every field used in idle, selector, held, completed, post-copy,
        // and restore validation. Fresh snapshots must expose each mutation.
        struct Mutation { int snapshot; uint32_t reg, value; int maxCopies; };
        const Mutation mutations[] = {
            {1, Supported, 0x1f, 0}, {2, InputBytes, RawBytes+16, 0},
            {2, Status, 0x40, 0}, {2, Mode, 1, 0}, {2, Camera, 0, 0},
            {2, OutputBank, 1, 0}, {2, Destination, RgbDestination+16, 0},
            {2, OutputBytes, RgbBytes+16, 0}, {2, Freeze, 4, 0},
            {3, Camera, 1, 0}, {3, OutputBank, 1, 0}, {3, Mode, 0, 0},
            {3, Destination, Destinations[0][0]+16, 0}, {3, OutputBytes, Bytes+16, 0},
            {3, Bank0, SourceBanks[0][0]+16, 0}, {3, Bank1, SourceBanks[0][1]+16, 0},
            {4, Freeze, 4, 0}, {5, Source, 0xdead0000, 0},
            {6, Epoch, 99, 0}, {6, SourceSequence, 999, 0}, {6, Freeze, 0, 0},
            {7, Bank0, 0xdead0000, 0}, {8, Jobs, 99, 0},
            {9, Epoch, 99, 0}, {9, SourceSequence, 999, 0}, {9, Freeze, 0, 0},
            {10, OutputBytes, Bytes+16, 0},
            {11, Epoch, 99, 1}, {11, SourceSequence, 999, 1}, {11, Freeze, 0, 1},
            {12, Bank1, 0xdead0000, 1}, {13, Freeze, 4, 1},
            {14, Mode, 1, 1}, {14, Camera, 0, 1}, {14, OutputBank, 1, 1},
            {14, Destination, RgbDestination+16, 1}, {14, OutputBytes, RgbBytes+16, 1}
        };
        for (const auto& mutation : mutations) {
            Fake io; io.mutateSnapshot = mutation.snapshot;
            io.mutateReg = mutation.reg; io.mutateValue = mutation.value;
            int result = execute(io);
            if (result != -1) std::fprintf(stderr, "MUTATION_MISSED snapshot=%d reg=%x\\n", mutation.snapshot, mutation.reg);
            expect(result == -1 && io.copies <= mutation.maxCopies, "stage snapshot mutation quarantines before unsafe copy");
        }
    } else expect(healthy.snapshots == 0, "caps7 preserves scalar fallback");
    } // both scalar fallback and batching run the entire existing fault suite
    Cursor raw, display;''')
    p.write_bytes(raw)
    print('Extended isolated scalar/batch host failure suite')

if __name__ == '__main__': main()
