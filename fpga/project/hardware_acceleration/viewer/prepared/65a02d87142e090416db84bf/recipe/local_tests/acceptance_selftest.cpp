#include "acceptance_metrics.h"
#include <QCoreApplication>
#include <cassert>
#include <thread>
#include <vector>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    using namespace viewer_acceptance;
    Counters counters(true), disabled(false);
    disabled.inference(true); disabled.frameRequest(0, 614416, 614400);
    assert(disabled.delivered(0) == 0 && disabled.snapshot().completed == 0);
    counters.inference(true); counters.inference(true); counters.inference(false);
    PaintIdentities paints;
    const auto id = counters.delivered(0);
    paints.beginPaint();
    paints.drawn(0, id, false); // Unallocated texture must not count.
    counters.swapped(paints);
    assert(counters.snapshot().paints[0] == 0);
    paints.beginPaint(); paints.drawn(0, id, true);
    assert(counters.snapshot().paints[0] == 0); // Upload/draw alone is not swap.
    counters.swapped(paints); counters.swapped(paints);
    paints.beginPaint(); paints.drawn(0, id, true); counters.swapped(paints);
    assert(counters.snapshot().paints[0] == 1);
    const auto newer = counters.delivered(0);
    paints.beginPaint(); paints.drawn(0, newer, true);
    paints.beginPaint(); counters.swapped(paints); // Settings/no draw replaces staged camera paint.
    assert(counters.snapshot().paints[0] == 1);
    paints.beginPaint(); paints.drawn(0, newer, true); paints.drawn(1, 0, true);
    counters.swapped(paints);
    paints.beginPaint(); paints.drawn(0, id, true); counters.swapped(paints); // Old frame cannot recount.
    for (size_t c = 1; c < Cameras; ++c) {
        counters.delivered(c);
        paints.drawn(c, 1, true);
    }
    counters.swapped(paints); // One swap can count one fresh frame on five cameras.
    auto s = counters.snapshot();
    assert(s.completed == 2 && s.failed == 1 && s.paints[0] == 2 && s.paintNewFrames == 3);
    for (size_t c = 1; c < Cameras; ++c) assert(s.paints[c] == 1);
    // Capture IDs are cumulative rather than camGen/sourceGeneration: a reset
    // followed by another successful delivery gives a new ID; merely switching
    // generation/model/layout with unchanged pixels never stages a new ID.
    const auto afterReset = counters.delivered(0);
    assert(afterReset > newer);
    paints.beginPaint(); paints.drawn(0, afterReset, true); counters.swapped(paints);
    counters.frameRequest(0, 614416, 614400); // Failed request: no delivered() call.
    counters.frameRequest(0, 614416, 614400); // Unstable read: also not delivered.
    counters.tagRequest(0, 16); counters.tagRequest(0, 16);
    const auto before = counters.snapshot();
    assert(before.dmaRequests[0] == 2 && before.dmaBytes[0] == 1228832 && before.payloadBytes[0] == 1228800);
    assert(before.tagBytes[0] == 32 && before.delivered[0] == 3);

    std::vector<std::thread> producers;
    for (size_t c = 0; c < Cameras; ++c) producers.emplace_back([&, c] {
        for (int i = 0; i < 10000; ++i) {
            counters.frameRequest(c, 614416, 614400);
            counters.delivered(c);
            counters.inference(i % 2 == 0);
        }
    });
    for (int i = 0; i < 100; ++i) {
        s = counters.snapshot();
        assert(s.beginNs >= s.startedNs && s.endNs >= s.beginNs);
        assert(s.completed >= before.completed && s.failed >= before.failed);
    }
    for (auto &thread : producers) thread.join();
    s = counters.snapshot();
    assert(s.completed == 30002 && s.failed == 30001);
    for (size_t c = 0; c < Cameras; ++c) {
        assert(s.delivered[c] == before.delivered[c] + 10000);
        assert(s.dmaRequests[c] == before.dmaRequests[c] + 10000);
        assert(s.dmaBytes[c] == before.dmaBytes[c] + 6144160000ULL);
    }
    // The runner supplies a fresh private directory. Verify atomic file output
    // and five-second suppression without sleeping or generating repeated logs.
    Reporter reporter;
    reporter.inference(true); reporter.delivered(0);
    reporter.report(); reporter.report();
    QFile file(qEnvironmentVariable("DETVIEW_ACCEPTANCE_DIR") + "/snapshot.json");
    assert(file.open(QIODevice::ReadOnly));
    const auto obj = QJsonDocument::fromJson(file.readAll()).object();
    assert(obj.value("snapshot").toString() == "1" && obj.value("completed").toString() == "1");
    assert(obj.value("scanout_verified").toBool() == false);
    assert(obj.value("per_camera_paints").toArray().size() == 6);
    struct stat st{};
    const auto dir = QFile::encodeName(qEnvironmentVariable("DETVIEW_ACCEPTANCE_DIR"));
    assert(lstat(dir.constData(), &st) == 0 && (st.st_mode & 0777) == 0700);
    assert(lstat((dir + "/snapshot.json").constData(), &st) == 0 && (st.st_mode & 0777) == 0600);
    std::puts("PASS actual paint identities, repeated/settings/old frame rejection, all-attempt DMA, concurrent counters, bounded snapshot and private atomic file");
}
