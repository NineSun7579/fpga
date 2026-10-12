"""Prepare a local candidate from SHA-verified retained bytes; never contact a board."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = "/userdata/linaro/detview-calibration-work/"
MAIN_SHA = "d3a38d77338168b6d95a8731efe99e7b443f08b0dee7bcc831d33bc544a0fd23"
BINARY_SHA = "0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact(data: bytes, anchor: str, replacement: str) -> bytes:
    old, new = anchor.encode("utf-8"), replacement.encode("utf-8")
    if data.count(old) != 1:
        raise ValueError(f"expected one exact anchor, found {data.count(old)}: {anchor[:100]!r}")
    return data.replace(old, new, 1)


def instrument(main: bytes) -> bytes:
    if sha(main) != MAIN_SHA:
        raise ValueError("main.cpp baseline SHA mismatch; refusing any patch")
    edits = [
        ('#include "camera_dma.h"\n', '#include "camera_dma.h"\n#include "stall_timing.h"\n'),
        ('    bool openDev() {\n', '    bool openDev() {\n        StallTiming::IoctlDrain diagnosticDrain;\n'),
        ('    bool regWrite(uint32_t addr, uint32_t val) {\n', '    bool regWrite(uint32_t addr, uint32_t val) {\n        StallTiming::IoctlDrain diagnosticDrain;\n'),
        ('    bool regRead(uint32_t addr, uint32_t &val) {\n', '    bool regRead(uint32_t addr, uint32_t &val) {\n        StallTiming::IoctlDrain diagnosticDrain;\n'),
        ('    bool ddrRead(uint32_t addr, uint32_t len, void *out) {\n', '    bool ddrRead(uint32_t addr, uint32_t len, void *out) {\n        StallTiming::IoctlDrain diagnosticDrain;\n'),
        ('''                   qint64& capturedMs) {
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        QMutexLocker lock(&dmaMutex_);
''', '''                   qint64& capturedMs, StallTiming::CameraAttempt& diagnostic) {
        StallTiming::IoctlDrain diagnosticDrain;
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        const auto waitBegin = StallTiming::Stamp::now();
        QMutexLocker lock(&dmaMutex_);
        const auto holdBegin = StallTiming::Stamp::now();
        diagnostic.add(StallTiming::DmaWait, waitBegin, holdBegin);
        auto diagnosticReturn = [&](int result) {
            lock.unlock();
            diagnostic.add(StallTiming::DmaHold, holdBegin, StallTiming::Stamp::now());
            return result;
        };
'''),
        ('        if (!cameraTagLocked(ping + FRAME_BYTES, a) || !cameraTagLocked(pong + FRAME_BYTES, b)) return -1;\n',
         '        if (!cameraTagLocked(ping + FRAME_BYTES, a) || !cameraTagLocked(pong + FRAME_BYTES, b)) return diagnosticReturn(-1);\n'),
        ('        if (bank < 0) return 0;\n', '        if (bank < 0) return diagnosticReturn(0);\n'),
        ('        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return -1;\n',
         '        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return diagnosticReturn(-1);\n'),
        ('''        if (actual != selected) return 2;
        lock.unlock();
        timer.restart();
        tdm::copyCameraPixels(output, pixels, FRAME_BYTES);
        copyNs = timer.nsecsElapsed();
''', '''        if (actual != selected) return diagnosticReturn(2);
        diagnosticReturn(1);
        timer.restart();
        const auto copyBegin = StallTiming::Stamp::now();
        tdm::copyCameraPixels(output, pixels, FRAME_BYTES);
        const auto copyEnd = StallTiming::Stamp::now();
        copyNs = timer.nsecsElapsed();
        diagnostic.add(StallTiming::Copy, copyBegin, copyEnd);
'''),
        ('''        alarm(sec);
        int r = ::ioctl(fd_, cmd, op);
        const int ioctlErrno = errno;
        alarm(0);
''', '''        alarm(sec);
        const auto syscallBegin = StallTiming::Stamp::now();
        int r = ::ioctl(fd_, cmd, op);
        const int ioctlErrno = errno;
        const auto syscallEnd = StallTiming::Stamp::now();
        alarm(0);
'''),
        ('''    int ioctlTmo(unsigned long cmd, DmaOp *op, unsigned sec) {
        timeoutHit_ = false;
''', '''    int ioctlTmo(unsigned long cmd, DmaOp *op, unsigned sec) {
        const uint32_t requestedAddress = op ? op->ddr3_addr : 0;
        const uint32_t requestedOffset = op ? op->offset_addr : 0;
        const uint32_t requestedBytes = op ? op->total_length : 0;
        timeoutHit_ = false;
'''),
        ('''        if (ms >= 30.0) {
            fprintf(stderr, "[diag]''', '''        StallTiming::Span legacyLog;
        if (ms >= 30.0) {
            const auto logBegin = StallTiming::Stamp::now();
            fprintf(stderr, "[diag]'''),
        ('''            fflush(stderr);
        }
        if (timeoutHit_) {
            err_ = "ioctl timeout";
            noteFailure();
            return -1;
        }
        if (r < 0) {
            noteFailure();
            return r;
        }
        failures_ = 0;
        return r;
''', '''            fflush(stderr);
            legacyLog = StallTiming::Span::between(logBegin, StallTiming::Stamp::now());
        }
        auto recordDiagnostic = [&](int applicationRc) {
            StallTiming::IoctlRecord record;
            record.syscall = StallTiming::Span::between(syscallBegin, syscallEnd);
            record.legacyLog = legacyLog;
            record.wrapperBegin = uint64_t(ts0.tv_sec) * 1000000000ULL + uint64_t(ts0.tv_nsec);
            record.wrapperEnd = uint64_t(ts1.tv_sec) * 1000000000ULL + uint64_t(ts1.tv_nsec);
            record.device = reinterpret_cast<uintptr_t>(this);
            record.command = cmd;
            record.address = requestedAddress;
            record.offset = requestedOffset;
            record.bytes = requestedBytes;
            record.rc = r; record.savedErrno = ioctlErrno;
            record.alarm = timeoutHit_; record.applicationRc = applicationRc;
            for (int camera = 0; camera < CAM_COUNT; ++camera) {
                for (int bank = 0; bank < 2; ++bank) {
                    const uint32_t base = CAM_BASE[camera][bank];
                    if (record.address >= base && record.address <= base + FRAME_BYTES) {
                        record.camera = camera + 1;
                        if (cmd == F2H_CMD && record.address == base + FRAME_BYTES && record.bytes == 16)
                            record.role = 1;
                        else if (cmd == F2H_CMD && record.address == base && record.bytes == FRAME_BYTES + 16)
                            record.role = 2;
                    }
                }
            }
            StallTiming::ioctls().record(record);
        };
        if (timeoutHit_) {
            err_ = "ioctl timeout";
            recordDiagnostic(-1);
            noteFailure();
            return -1;
        }
        if (r < 0) {
            recordDiagnostic(r);
            noteFailure();
            return r;
        }
        failures_ = 0;
        recordDiagnostic(r);
        return r;
'''),
        ('        QByteArray frame(FRAME_BYTES, 0);\n',
         '        QByteArray frame(FRAME_BYTES, 0);\n        StallTiming::CameraWindow diagnosticWindow(idx + 1);\n'),
        ('''        while (running_) {
            if (paused_ && paused_->load())''', '''        while (running_) {
            diagnosticWindow.poll();
            if (paused_ && paused_->load())'''),
        ('''            QElapsedTimer readTimer; readTimer.start();
            // A display snapshot''', '''            StallTiming::CameraAttempt diagnostic(diagnosticWindow);
            const auto readBegin = StallTiming::Stamp::now();
            QElapsedTimer readTimer; readTimer.start();
            // A display snapshot'''),
        ('''            if (!frame.isDetached()) frame = QByteArray(FRAME_BYTES, Qt::Uninitialized);
            uint32_t selectedTag''', '''            const auto allocBegin = StallTiming::Stamp::now();
            if (!frame.isDetached()) frame = QByteArray(FRAME_BYTES, Qt::Uninitialized);
            char* writablePixels = frame.data();
            diagnostic.add(StallTiming::Alloc, allocBegin, StallTiming::Stamp::now());
            uint32_t selectedTag'''),
        ('''                                                frame.data(), selectedTag, dmaNs, copyNs, capturedMs);
            if (result == 0) { msleep(6); continue; }
            if (result == 2) { ++unstable; msleep(1); continue; }
            if (result < 0) {
                { QMutexLocker lock(&frames_->mutex); ++frames_->errors[idx]; }
                msleep(25);
                continue;
            }
            if (delivered && measureTagAdvance) sequenceAdvance += uint32_t(selectedTag - deliveredTag);
''', '''                                                writablePixels, selectedTag, dmaNs, copyNs, capturedMs, diagnostic);
            diagnostic.add(StallTiming::Read, readBegin, StallTiming::Stamp::now());
            if (result == 0) { diagnostic.finish(result); msleep(6); continue; }
            if (result == 2) { ++unstable; diagnostic.finish(result); msleep(1); continue; }
            if (result < 0) {
                const auto publishWaitBegin = StallTiming::Stamp::now();
                { QMutexLocker lock(&frames_->mutex);
                  const auto publishHoldBegin = StallTiming::Stamp::now();
                  diagnostic.add(StallTiming::PublishWait, publishWaitBegin, publishHoldBegin);
                  ++frames_->errors[idx];
                  lock.unlock();
                  diagnostic.add(StallTiming::PublishHold, publishHoldBegin, StallTiming::Stamp::now()); }
                diagnostic.finish(result);
                msleep(25);
                continue;
            }
            if (delivered && measureTagAdvance) {
                sequenceAdvance += uint32_t(selectedTag - deliveredTag);
                diagnostic.tag(deliveredTag, selectedTag);
            }
'''),
        ('''                QImage pixels(IMG_W, IMG_H, QImage::Format_RGB888);
                const uint16_t *src''', '''                const auto imageAllocBegin = StallTiming::Stamp::now();
                QImage pixels(IMG_W, IMG_H, QImage::Format_RGB888);
                diagnostic.add(StallTiming::Alloc, imageAllocBegin, StallTiming::Stamp::now());
                const auto convertBegin = StallTiming::Stamp::now();
                const uint16_t *src'''),
        ('''                                       IMG_W, pixels.scanLine(y));
                VisionFrame packet;''', '''                                       IMG_W, pixels.scanLine(y));
                diagnostic.add(StallTiming::Convert, convertBegin, StallTiming::Stamp::now());
                VisionFrame packet;'''),
        ('''                visionSink_(packet);
            }
            QMutexLocker lock(&frames_->mutex);
''', '''                const auto sinkBegin = StallTiming::Stamp::now();
                visionSink_(packet);
                diagnostic.add(StallTiming::Sink, sinkBegin, StallTiming::Stamp::now());
            }
            const auto publishWaitBegin = StallTiming::Stamp::now();
            QMutexLocker lock(&frames_->mutex);
            const auto publishHoldBegin = StallTiming::Stamp::now();
            diagnostic.add(StallTiming::PublishWait, publishWaitBegin, publishHoldBegin);
'''),
        ('''            if (frame.size() != FRAME_BYTES)
                frame.resize(FRAME_BYTES);
''', '''            if (frame.size() != FRAME_BYTES) {
                const auto resizeBegin = StallTiming::Stamp::now();
                frame.resize(FRAME_BYTES);
                diagnostic.add(StallTiming::Alloc, resizeBegin, StallTiming::Stamp::now());
            }
'''),
        ('''            frames_->fps[idx] = captureRate.rate(completedMs);
            lock.unlock();
            const qint64 auditNow''', '''            frames_->fps[idx] = captureRate.rate(completedMs);
            lock.unlock();
            diagnostic.add(StallTiming::PublishHold, publishHoldBegin, StallTiming::Stamp::now());
            diagnostic.finish(result);
            const qint64 auditNow'''),
    ]
    for old, new in edits:
        main = exact(main, old, new)
    return main


def write_verified(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"refusing to overwrite differing local bytes: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if sha(path.read_bytes()) != sha(data):
        raise ValueError(f"post-write SHA mismatch: {path}")


def prepare(provenance: Path, output: Path, project_file: Path | None = None) -> dict:
    output = output.resolve()
    if not output.is_relative_to(HERE):
        raise ValueError("output must be inside this agent's diagnostic directory")
    receipt_bytes = provenance.read_bytes()
    receipt = json.loads(receipt_bytes)
    retained, absent = {}, []
    for entry in receipt["files"]:
        if not entry["path"].startswith(ROOT):
            continue
        relative = PurePosixPath(entry["path"][len(ROOT):])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe retained path")
        if "text" not in entry:
            absent.append({"path": str(relative), "sha256": entry["sha256"], "size": entry["size"], "status": "hash_only_no_bytes"})
            continue
        data = entry["text"].encode("utf-8")
        if sha(data) != entry["sha256"] or len(data) != entry["size"]:
            raise ValueError(f"cannot reconstruct exact retained UTF-8 bytes: {relative}")
        retained[str(relative)] = (data, entry["sha256"])
    if retained["src/main.cpp"][1] != MAIN_SHA:
        raise ValueError("receipt contains an unexpected main baseline")
    if next(e["sha256"] for e in receipt["files"] if e["path"] == ROOT + "build/detview") != BINARY_SHA:
        raise ValueError("receipt contains an unexpected original executable hash")
    if project_file:
        expected = next(e for e in absent if e["path"] == "src/detview.pro")
        data = project_file.read_bytes()
        if sha(data) != expected["sha256"] or len(data) != expected["size"]:
            raise ValueError("parent-retained detview.pro bytes do not match baseline SHA/size")
        retained["src/detview.pro"] = (data, expected["sha256"])
        absent.remove(expected)
    baseline = retained["src/main.cpp"][0]
    candidate = instrument(baseline)
    header = (HERE / "stall_timing.h").read_bytes()
    baseline_files, candidate_files = [], []
    for relative, (data, digest) in sorted(retained.items()):
        write_verified(output / "frozen" / relative, data)
        baseline_files.append({"path": relative, "sha256": digest, "size": len(data)})
        if relative.startswith(("src/", "sdk/")):
            changed = candidate if relative == "src/main.cpp" else data
            write_verified(output / "candidate" / relative, changed)
            candidate_files.append({"path": relative, "sha256": sha(changed), "size": len(changed)})
    write_verified(output / "candidate/src/stall_timing.h", header)
    candidate_files.append({"path": "src/stall_timing.h", "sha256": sha(header), "size": len(header)})
    diff = "".join(difflib.unified_diff(baseline.decode("utf-8").splitlines(True), candidate.decode("utf-8").splitlines(True),
        fromfile="a/src/main.cpp", tofile="b/src/main.cpp"))
    diff += "".join(difflib.unified_diff([], header.decode("utf-8").splitlines(True), fromfile="/dev/null", tofile="b/src/stall_timing.h"))
    write_verified(output / "diagnostic.patch", diff.encode("utf-8"))
    declarations = {
        "PangoDev::openDev": b"    bool openDev() {",
        "PangoDev::regWrite": b"    bool regWrite(uint32_t addr, uint32_t val) {",
        "PangoDev::regRead": b"    bool regRead(uint32_t addr, uint32_t &val) {",
        "PangoDev::ddrRead": b"    bool ddrRead(uint32_t addr, uint32_t len, void *out) {",
        "PangoDev::cameraRead": b"    int cameraRead(int camera,",
        "PangoDev::ioctlTmo": b"    int ioctlTmo(unsigned long cmd, DmaOp *op, unsigned sec) {",
        "CameraWorker::run": b"    void run() override {",
    }
    scopes = []
    for name, declaration in declarations.items():
        positions = []
        for data in (baseline, candidate):
            origin = data.index(b"class CameraWorker : public QThread {") if name == "CameraWorker::run" else 0
            positions.append(data[:data.index(declaration, origin)].count(b"\n") + 1)
        scopes.append({"function": name, "baseline_line": positions[0], "candidate_line": positions[1]})
    manifest = {
        "stage": "prepared_not_built", "board_access": False, "deployed": False,
        "provenance_sha256": sha(receipt_bytes), "baseline_main_sha256": MAIN_SHA,
        "original_binary_sha256": BINARY_SHA,
        "source_to_original_binary": "matching runtime snapshots; critical ioctl/camera/worker scopes independently disassembled; full compiler-input binding unavailable",
        "frozen_manifest_complete": False, "project_bytes_present": "src/detview.pro" in retained,
        "pending": ["compiler/toolchain and dependency identities", "actual isolated qmake commands/options", "object hashes", "linked diagnostic executable hash", "runtime validation"],
        "hash_only_files": absent, "baseline_files": baseline_files, "candidate_files": candidate_files,
        "application_diff_files": ["src/main.cpp", "src/stall_timing.h"], "patch_sha256": sha(diff.encode("utf-8")),
        "functions_changed": ["PangoDev::openDev", "PangoDev::regWrite", "PangoDev::regRead", "PangoDev::ddrRead", "PangoDev::cameraRead", "PangoDev::ioctlTmo", "CameraWorker::run"],
        "function_scopes": scopes,
    }
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_bytes())
        for key in ("baseline_files", "candidate_files", "patch_sha256"):
            if old[key] != manifest[key]:
                raise ValueError(f"prepared manifest differs: {key}; use a fresh local output directory")
    manifest_path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance", type=Path, default=HERE.parent / "board_provenance_readonly.json")
    parser.add_argument("--output", type=Path, default=HERE / "prepared")
    parser.add_argument("--project-file", type=Path, help="optional exact bytes separately retained by parent; not synthesized")
    args = parser.parse_args()
    result = prepare(args.provenance, args.output, args.project_file)
    print(json.dumps({key: result[key] for key in ("stage", "baseline_main_sha256", "project_bytes_present", "application_diff_files", "patch_sha256")}, indent=2))
