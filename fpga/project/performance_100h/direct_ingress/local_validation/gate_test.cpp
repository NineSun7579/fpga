#include <QCoreApplication>
#include <QImage>
#include <QMutex>
#include <QMutexLocker>
#include <QSemaphore>
#include <QThread>
#include <QWaitCondition>
#include <QElapsedTimer>
#include <atomic>
#include <thread>
#include <cstdio>
#include <cstdlib>

static void check(bool value, const char *message) {
    if (!value) { fprintf(stderr, "FAIL %s\n", message); std::abort(); }
}
static qint64 monotonicMs() { QElapsedTimer timer; timer.start(); return timer.msecsSinceReference(); }
struct VisionFrame { QImage image; int sourceGeneration; quint64 frameId; };
struct Rate {
    int count = 0;
    void add(qint64) { ++count; }
};
class VisionPipeline : public QObject {
    Q_OBJECT
public:
    QMutex mutex;
    QSemaphore failureEntered;
    int failures = 0;
    int lastGeneration = 0;
    quint64 lastId = 0;
    void inferenceFailed(int gen, quint64 id) {
        failureEntered.release();
        QMutexLocker lock(&mutex);
        ++failures; lastGeneration = gen; lastId = id;
    }
signals:
    void inferenceRequested(VisionFrame frame);
};
// Fake device worker, real production mailbox methods and dequeue bytes.
// No RKNN, controller, capture, or VisionPipeline algorithm is compiled here.
class InferenceThread : public QThread {
public:
    QMutex m_mutex;
    QWaitCondition m_cond;
    QImage m_pending;
    int m_pendingGeneration = 0;
    quint64 m_pendingFrameId = 0;
    bool m_hasPending = false, m_modelChanged = false;
    std::atomic<bool> m_stop{false};
    QSemaphore beforeWait;
#include "submit.inc"
#include "clear_pending.inc"
#include "stop.inc"
    VisionFrame take() {
        QMutexLocker lock(&m_mutex);
#include "dequeue.inc"
        return {hadPending ? frame : QImage(), sourceGeneration, frameId};
    }
    bool pending() { QMutexLocker lock(&m_mutex); return m_hasPending; }
    void run() override {
        while (!m_stop) {
            QMutexLocker lock(&m_mutex);
            beforeWait.release();
#include "wait_predicate.inc"
        }
    }
};
class GateHarness : public QObject {
public:
    QMutex m_ingressMutex;
    bool m_ingressEnabled = false, m_paused = false, m_shuttingDown = false;
    int m_ingressGeneration = 0, m_sourceGeneration = 1;
    InferenceThread *m_infer;
    VisionPipeline *m_vision;
    Rate m_requestRate;
    GateHarness(InferenceThread *infer, VisionPipeline *vision)
        : m_infer(infer), m_vision(vision) {
#include "connection.inc"
    }
#include "close_ingress.inc"
#include "open_ingress.inc"
    // Controlled configuration seam: only caller on GUI thread changes fields.
    void commit(bool paused = false) {
        closeIngress();
        ++m_sourceGeneration;
        m_paused = paused;
        m_requestRate.count = 0;
        openIngress();
    }
};
static VisionFrame frame(int gen, quint64 id) {
    QImage image(8, 8, QImage::Format_RGB888);
    image.fill(QColor(int(id % 255), 71, 19));
    return {image, gen, id};
}
static void send(VisionPipeline &vision, VisionFrame f) {
    std::thread worker([&] { emit vision.inferenceRequested(f); });
    worker.join();
}
static void waitIngressHeld(GateHarness &gate) {
    QElapsedTimer timer; timer.start();
    while (gate.m_ingressMutex.tryLock()) {
        gate.m_ingressMutex.unlock();
        check(timer.elapsed() < 5000, "request must acquire ingress before race");
        QThread::msleep(1);
    }
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    fprintf(stdout, "Qt=%s threads=real std::thread/QThread GUI=no events until checks\n", qVersion());
    InferenceThread infer;
    VisionPipeline vision;
    GateHarness gate(&infer, &vision);
    send(vision, frame(1, 1));
    check(!infer.pending() && vision.failures == 1, "startup closed rejection");
    gate.openIngress();
    send(vision, frame(1, 2));
    check(infer.pending(), "worker direct submits while GUI blocked");
    check(gate.m_requestRate.count == 0, "only rate notification queued");
    auto first = infer.take();
    check(first.sourceGeneration == 1 && first.frameId == 2 && !first.image.isNull(), "owned mailbox identity");
    QCoreApplication::processEvents();
    check(gate.m_requestRate.count == 1, "functor invoke delivery");
    fprintf(stdout, "PASS startup / GUI blocked direct submission / functor invoke\n");

    // Force production submit to hold ingress while blocked on inference mutex.
    // Close must wait for that submit, then clear it before returning.
    for (int i = 0; i < 100; ++i) {
        infer.m_mutex.lock();
        std::thread request([&] { emit vision.inferenceRequested(frame(gate.m_sourceGeneration, 100 + i)); });
        waitIngressHeld(gate);
        QSemaphore closeStarted, closeDone;
        std::thread closer([&] { closeStarted.release(); gate.closeIngress(); closeDone.release(); });
        check(closeStarted.tryAcquire(1, 5000), "closer started");
        check(!closeDone.tryAcquire(1, 10), "close cannot pass a held submit");
        infer.m_mutex.unlock();
        request.join();
        check(closeDone.tryAcquire(1, 5000), "close finishes after submit");
        closer.join();
        check(!infer.pending(), "close clears racing submit");
        gate.closeIngress(); // idempotent nested close
        const int old = gate.m_sourceGeneration;
        gate.commit();
        send(vision, frame(old, 300 + i));
        check(!infer.pending(), "stale generation cannot refill after reopen");
        send(vision, frame(gate.m_sourceGeneration, 400 + i));
        check(infer.pending(), "current generation accepted after commit");
        gate.closeIngress();
        check(!infer.pending(), "clear precedes config mutation");
        // Inject stray slot while closed: final open must discard it too.
        infer.submit(frame(old, 500 + i).image, old, 500 + i);
        gate.openIngress();
        check(!infer.pending(), "open final clear discards old slot");
    }
    gate.commit();
    QCoreApplication::processEvents();
    check(gate.m_requestRate.count == 0, "stale queued rates discarded after generation change");
    fprintf(stdout, "PASS 100 forced submit-vs-close races / stale generations / both clears / stale GUI rates\n");

    send(vision, frame(gate.m_sourceGeneration, 800));
    auto inFlight = infer.take();
    gate.commit(true);
    send(vision, frame(gate.m_sourceGeneration, 801));
    check(!infer.pending(), "paused ingress rejects current requests");
    check(inFlight.sourceGeneration != gate.m_sourceGeneration && inFlight.frameId == 800,
          "dequeued request retains old identity across pause/reset");
    gate.commit(false);
    send(vision, frame(gate.m_sourceGeneration, 802));
    check(infer.pending(), "resume accepts fresh generation");
    gate.closeIngress(true);
    check(!infer.pending(), "permanent close clears pending");
    gate.openIngress();
    send(vision, frame(gate.m_sourceGeneration, 803));
    check(!infer.pending(), "permanent close cannot reopen");
    QCoreApplication::processEvents();
    check(gate.m_requestRate.count == 0, "shutdown queued rate rejected");
    fprintf(stdout, "PASS pause/reset/resume / old dequeue identity / permanent close / shutdown rates\n");

    // Rejection must drop ingress before calling into a blocked vision reply.
    while (vision.failureEntered.tryAcquire()) {}
    vision.mutex.lock();
    std::thread rejected([&] { emit vision.inferenceRequested(frame(0, 900)); });
    check(vision.failureEntered.tryAcquire(1, 5000), "rejection reaches vision reply");
    check(gate.m_ingressMutex.tryLock(), "rejection releases ingress before waiting for vision");
    gate.m_ingressMutex.unlock();
    gate.closeIngress();
    vision.mutex.unlock();
    rejected.join();
    check(vision.lastGeneration == 0 && vision.lastId == 900, "rejection releases original identity");
    fprintf(stdout, "PASS rejection-vs-vision-lock ordering and identity\n");

    {
        InferenceThread mailbox;
        VisionPipeline source;
        GateHarness concurrent(&mailbox, &source);
        concurrent.openIngress();
        std::atomic<int> published{1};
        std::atomic<quint64> ids{1000};
        std::atomic<bool> finish{false};
        QSemaphore emitted;
        std::thread producers[4];
        for (auto &producer : producers) producer = std::thread([&] {
            while (!finish.load()) {
                emit source.inferenceRequested(frame(published.load(), ids.fetch_add(1)));
                emitted.release();
                QThread::yieldCurrentThread();
            }
        });
        check(emitted.tryAcquire(4, 5000), "concurrent producers active");
        for (int i = 0; i < 200; ++i) {
            const bool paused = (i % 3 == 0);
            concurrent.commit(paused);
            published.store(concurrent.m_sourceGeneration);
            check(emitted.tryAcquire(4, 5000), "requests overlap configuration cycles");
            if (paused) check(!mailbox.pending(), "pause stays closed during active producers");
            else {
                auto pending = mailbox.take();
                check(pending.image.isNull() || pending.sourceGeneration == concurrent.m_sourceGeneration,
                      "configuration never dequeues stale pending generation");
            }
        }
        concurrent.closeIngress(true);
        check(emitted.tryAcquire(4, 5000), "emissions continue across permanent close");
        check(!mailbox.pending(), "shutdown prevents producer refill");
        finish.store(true);
        for (auto &producer : producers) producer.join();
        QCoreApplication::processEvents();
        check(concurrent.m_requestRate.count == 0, "shutdown drops queued rates from all producers");
        fprintf(stdout, "PASS 4 producers / 200 concurrent pause-reset commits / permanent close; emitted=%llu\n",
                static_cast<unsigned long long>(ids.load() - 1000));
    }

    // Stop races with actual predicate/wait transition; wait releases same mutex.
    for (int i = 0; i < 200; ++i) {
        InferenceThread sleeping;
        sleeping.start();
        check(sleeping.beforeWait.tryAcquire(1, 5000), "worker reaches locked wait seam");
        QElapsedTimer timer; timer.start();
        sleeping.stop();
        check(!sleeping.isRunning(), "production stop joins waiting worker");
        check(timer.elapsed() < 5000, "stop wake completes bounded");
    }
    fprintf(stdout, "PASS 200 predicate/wait-vs-stop joins\nLOCAL_GATE_SELFTEST_PASS\n");
    return 0;
}
#include "gate_test.moc"
