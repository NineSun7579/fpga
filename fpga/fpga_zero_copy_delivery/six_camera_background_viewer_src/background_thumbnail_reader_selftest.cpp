#include "background_thumbnail_reader.hpp"

#include <algorithm>
#include <array>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace background_thumbnail;

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

struct Bank {
    std::uint32_t guard = 0;
    std::uint32_t sequence = 0;
    std::uint32_t tag = 0;
    std::vector<std::uint8_t> bytes = std::vector<std::uint8_t>(kFrameBytes);
};

// Writer events are independent of reader decisions: injected by event ordinal,
// including within DMA/copy, rather than computed from reader validation logic.
struct Fake final : Transport {
    std::array<std::array<Bank, 2>, 6> banks;
    std::vector<std::uint8_t> scratch;
    std::vector<std::string> trace;
    std::function<void(Fake&, const std::string&)> schedule;
    unsigned operations = 0;
    unsigned failOperation = 0;
    unsigned payloadReads = 0;
    bool confirmed = true;
    std::size_t transferBytes = kTransferBytes;
    int sizeAdjustment = 0;

    Fake() { publish(0, 0, 10, 7, 0x31); }
    void publish(unsigned c, unsigned b, std::uint32_t seq, std::uint32_t gen,
                 std::uint8_t value) {
        Bank& bank = banks[c][b];
        bank.guard = (gen << 2) | 2u;
        bank.sequence = seq;
        bank.tag = seq;
        std::fill(bank.bytes.begin(), bank.bytes.end(), value);
    }
    void event(const std::string& name) {
        trace.push_back(name);
        if (schedule) schedule(*this, name);
    }
    bool metadata(unsigned c, unsigned b, std::uint32_t& value, bool guard) {
        require(c < 6 && b < 2, "invalid physical camera/bank reached transport");
        const std::string label = std::string(guard ? "guard" : "sequence") +
                                  ":" + std::to_string(c) + ":" + std::to_string(b);
        event(label + ":before");
        ++operations;
        if (operations == failOperation) return false;
        value = guard ? banks[c][b].guard : banks[c][b].sequence;
        event(label + ":after");
        return true;
    }
    bool readGuard(unsigned c, unsigned b, std::uint32_t& value) override {
        return metadata(c, b, value, true);
    }
    bool readSequence(unsigned c, unsigned b, std::uint32_t& value) override {
        return metadata(c, b, value, false);
    }
    bool readPayloadOwned(unsigned c, unsigned b, OwnedPayload& out) override {
        require(c < 6 && b < 2, "invalid payload mapping");
        event("dma:before");
        ++operations;
        ++payloadReads;
        if (operations == failOperation) return false;
        scratch.resize(kFrameBytes);
        const auto half = static_cast<std::ptrdiff_t>(kFrameBytes / 2);
        Bank& bank = banks[c][b];
        std::copy(bank.bytes.begin(), bank.bytes.begin() + half, scratch.begin());
        event("dma:middle");
        std::copy(bank.bytes.begin() + half, bank.bytes.end(), scratch.begin() + half);
        out.tag = bank.tag;
        event("copy:before");
        out.bytes.resize(kFrameBytes);
        std::copy(scratch.begin(), scratch.begin() + half, out.bytes.begin());
        event("copy:middle");
        std::copy(scratch.begin() + half, scratch.end(), out.bytes.begin() + half);
        event("copy:after");
        if (sizeAdjustment < 0) out.bytes.pop_back();
        if (sizeAdjustment > 0) out.bytes.push_back(0);
        out.transferredBytes = transferBytes;
        out.contiguousMappingConfirmed = confirmed;
        event("dma:after");
        return true;
    }
};

Frame sentinel() {
    Frame f;
    f.camera = 5;
    f.bank = 1;
    f.guard = 123;
    f.sequence = 456;
    f.tag = 789;
    f.bytes = {4, 5, 6};
    return f;
}
bool equalFrame(const Frame& a, const Frame& b) {
    return a.camera == b.camera && a.bank == b.bank && a.guard == b.guard &&
           a.sequence == b.sequence && a.tag == b.tag && a.bytes == b.bytes;
}
Result attempt(Fake& fake, Frame& output, const Cursor& cursor = Cursor{},
               unsigned camera = 0, std::uint32_t caps = kCapability) {
    const Cursor saved = cursor;
    const Result r = Reader::read(fake, camera, caps, cursor, output);
    require(cursor.committed == saved.committed && cursor.camera == saved.camera &&
            cursor.sequence == saved.sequence, "read modified cursor");
    return r;
}
void rejected(Fake& fake, Outcome outcome, Reason reason,
              const Cursor& cursor = Cursor{}, unsigned camera = 0,
              std::uint32_t caps = kCapability) {
    Frame output = sentinel();
    const Frame old = output;
    const Result r = attempt(fake, output, cursor, camera, caps);
    require(r.outcome == outcome && r.reason == reason, "wrong rejection category");
    require(equalFrame(output, old), "rejection changed prior output");
}
void accepted(Fake& fake, unsigned bank, std::uint32_t seq,
              const Cursor& cursor = Cursor{}, unsigned camera = 0) {
    Frame output = sentinel();
    const Result r = attempt(fake, output, cursor, camera);
    require(r.outcome == Outcome::accepted && r.reason == Reason::none, "expected acceptance");
    require(output.camera == camera && output.bank == bank && output.sequence == seq &&
            output.tag == seq && output.guard == fake.banks[camera][bank].guard &&
            output.bytes == fake.banks[camera][bank].bytes, "accepted wrong frame");
}

unsigned tests = 0;
void test(const std::string& name, const std::function<void()>& body) {
    try { body(); ++tests; }
    catch (const std::exception& e) { throw std::runtime_error(name + ": " + e.what()); }
}
Cursor cursor(std::uint32_t sequence, unsigned camera = 0) {
    return {true, camera, sequence};
}

void run() {
    test("owned frame and explicit commit", [] {
        Fake fake;
        Cursor current;
        Frame frame;
        require(attempt(fake, frame, current).outcome == Outcome::accepted, "first read");
        require(!current.committed, "implicit commit");
        // Simulate application generation rejection: intentionally do not commit.
        Frame reread;
        require(attempt(fake, reread, current).outcome == Outcome::accepted, "lost rejected generation");
        require(Reader::commit(0, reread, current), "explicit commit failed");
        require(current.committed && current.sequence == 10, "commit identity");
        require(!Reader::commit(0, reread, current), "duplicate commit");
        rejected(fake, Outcome::retry, Reason::no_fresh_bank, current);
    });
    for (unsigned camera = 0; camera < 6; ++camera) {
        for (unsigned bank = 0; bank < 2; ++bank) {
            test("physical camera " + std::to_string(camera) + " bank " + std::to_string(bank), [=] {
                Fake fake;
                for (auto& pair : fake.banks) for (auto& entry : pair) entry.guard = 0;
                fake.publish(camera, bank, 100 + camera * 2 + bank, 9,
                             static_cast<std::uint8_t>(0x40 + camera * 2 + bank));
                accepted(fake, bank, 100 + camera * 2 + bank, Cursor{}, camera);
            });
        }
    }
    for (unsigned camera : {6u, 7u, 0xffffffffu}) {
        test("invalid camera " + std::to_string(camera), [=] {
            Fake fake;
            rejected(fake, Outcome::invalid_request, Reason::camera_out_of_range, Cursor{}, camera);
            require(fake.operations == 0, "invalid camera did IO");
        });
    }
    test("cursor belongs to another camera", [] {
        Fake fake;
        rejected(fake, Outcome::invalid_request, Reason::cursor_camera_mismatch, cursor(9, 1));
        require(fake.operations == 0, "mismatched cursor did IO");
    });
    for (std::uint32_t caps : {0u, 8u, 15u}) {
        test("missing capability " + std::to_string(caps), [=] {
            Fake fake;
            rejected(fake, Outcome::unsupported, Reason::missing_capability, Cursor{}, 0, caps);
            require(fake.operations == 0, "unsupported did IO");
        });
    }
    for (std::uint32_t guard : {0u, 1u, 3u, 0xfffffffdu, 0xffffffffu}) {
        test("invalid/busy guard " + std::to_string(guard), [=] {
            Fake fake;
            fake.banks[0][0].guard = guard;
            rejected(fake, Outcome::retry, Reason::no_fresh_bank);
            require(fake.payloadReads == 0, "DMA from invalid/busy bank");
        });
    }
    test("busy newest bank permits stable completed bank", [] {
        Fake fake;
        fake.publish(0, 1, 11, 8, 0x32);
        fake.banks[0][1].guard |= 1u;
        accepted(fake, 0, 10);
    });
    test("bank one newest", [] { Fake fake; fake.publish(0, 1, 11, 8, 0x32); accepted(fake, 1, 11); });
    test("bank zero newest", [] { Fake fake; fake.publish(0, 1, 9, 8, 0x32); accepted(fake, 0, 10); });
    test("equal banks deterministically choose zero", [] {
        Fake fake; fake.publish(0, 1, 10, 8, 0x32); accepted(fake, 0, 10);
    });
    test("half range between banks", [] {
        Fake fake; fake.publish(0, 1, 10u + 0x80000000u, 8, 0x32);
        rejected(fake, Outcome::retry, Reason::ambiguous_sequence);
        require(fake.payloadReads == 0, "ambiguous bank DMA");
    });
    test("half range against cursor", [] {
        Fake fake; rejected(fake, Outcome::retry, Reason::ambiguous_sequence, cursor(10u + 0x80000000u));
    });
    test("equal to cursor", [] { Fake fake; rejected(fake, Outcome::retry, Reason::no_fresh_bank, cursor(10)); });
    test("older than cursor", [] { Fake fake; rejected(fake, Outcome::retry, Reason::no_fresh_bank, cursor(11)); });
    test("one fresh bank", [] {
        Fake fake; fake.publish(0, 1, 11, 8, 0x32); accepted(fake, 1, 11, cursor(10));
    });
    test("published zero without cursor", [] { Fake fake; fake.publish(0, 0, 0, 0, 0x30); accepted(fake, 0, 0); });
    test("zero after source wrap", [] {
        Fake fake; fake.publish(0, 0, 0, 0, 0x30); accepted(fake, 0, 0, cursor(0xffffffffu));
    });
    test("zero beats ffffffff across banks", [] {
        Fake fake; fake.publish(0, 0, 0xffffffffu, 2, 0x31); fake.publish(0, 1, 0, 3, 0x32);
        accepted(fake, 1, 0, cursor(0xfffffffeu));
    });
    test("committed zero is not unpublished", [] {
        Fake fake; fake.publish(0, 0, 0, 0, 0x30);
        rejected(fake, Outcome::retry, Reason::no_fresh_bank, cursor(0));
    });

    Fake baseline;
    Frame baselineFrame;
    require(attempt(baseline, baselineFrame).outcome == Outcome::accepted, "schedule baseline");
    require(baseline.operations == 13 && baseline.trace.size() == 30, "unexpected reader event coverage");
    // Every event edge around all 12 metadata reads and DMA/copy. A writer that
    // starts after the final captured guard cannot corrupt already owned bytes.
    for (std::size_t at = 0; at < baseline.trace.size(); ++at) {
        test("writer enters edge " + std::to_string(at) + " " + baseline.trace[at], [=] {
            Fake fake;
            fake.schedule = [=](Fake& f, const std::string&) {
                if (f.trace.size() == at + 1) {
                    f.banks[0][0].guard = (8u << 2) | 1u;
                    std::fill(f.banks[0][0].bytes.begin(), f.banks[0][0].bytes.end(), 0x99);
                    if (f.trace.back() == "copy:middle") std::fill(f.scratch.begin(), f.scratch.end(), 0x99);
                }
            };
            Frame output = sentinel();
            const Frame old = output;
            const Result r = attempt(fake, output);
            if (at + 1 == baseline.trace.size()) {
                require(r.outcome == Outcome::accepted && output.bytes == baselineFrame.bytes,
                        "writer after final read damaged detached frame");
            } else {
                require(r.outcome == Outcome::retry, "writer edge accepted unsafe frame");
                require(equalFrame(output, old), "writer edge changed output");
            }
        });
    }
    // Failed rewrites may leave valid+same sequence/tag. The FULL generation
    // guard still must invalidate every bracket after the initial guard capture.
    for (std::size_t at = 1; at + 1 < baseline.trace.size(); ++at) {
        test("same-sequence failed rewrite edge " + std::to_string(at), [=] {
            Fake fake;
            fake.schedule = [=](Fake& f, const std::string&) {
                if (f.trace.size() == at + 1) f.publish(0, 0, 10, 8, 0x99);
            };
            rejected(fake, Outcome::retry, Reason::metadata_changed);
        });
    }
    for (unsigned operation = 1; operation <= 13; ++operation) {
        test("transport failure operation " + std::to_string(operation), [=] {
            Fake fake;
            fake.failOperation = operation;
            rejected(fake, Outcome::transport_fault,
                     operation == 10 ? Reason::payload_io : Reason::metadata_io);
            require(fake.operations == operation, "continued after transport failure");
        });
    }
    test("sequence alone changes during DMA", [] {
        Fake fake;
        fake.schedule = [](Fake& f, const std::string& event) {
            if (event == "dma:middle") ++f.banks[0][0].sequence;
        };
        rejected(fake, Outcome::retry, Reason::metadata_changed);
    });
    test("generation wraps during DMA", [] {
        Fake fake; fake.publish(0, 0, 10, 0x3fffffffu, 0x31);
        fake.schedule = [](Fake& f, const std::string& event) {
            if (event == "dma:middle") f.publish(0, 0, 10, 0, 0x99);
        };
        rejected(fake, Outcome::retry, Reason::metadata_changed);
    });
    test("tag mismatch without metadata change", [] {
        Fake fake; fake.banks[0][0].tag = 11;
        rejected(fake, Outcome::retry, Reason::tag_mismatch);
    });
    test("zero tag must match exactly", [] {
        Fake fake; fake.banks[0][0].tag = 0;
        rejected(fake, Outcome::retry, Reason::tag_mismatch);
    });
    for (int malformed = 0; malformed < 5; ++malformed) {
        test("owned payload contract " + std::to_string(malformed), [=] {
            Fake fake;
            if (malformed == 0) fake.confirmed = false;
            if (malformed == 1) fake.transferBytes = kTransferBytes - 16;
            if (malformed == 2) fake.transferBytes = kTransferBytes + 16;
            if (malformed == 3) fake.sizeAdjustment = -1;
            if (malformed == 4) fake.sizeAdjustment = 1;
            rejected(fake, Outcome::transport_fault, Reason::payload_contract);
        });
    }
    test("scratch reuse while post metadata is being read", [] {
        Fake fake;
        fake.schedule = [](Fake& f, const std::string& event) {
            if (event == "dma:after") std::fill(f.scratch.begin(), f.scratch.end(), 0x99);
        };
        accepted(fake, 0, 10);
    });
    test("scratch and output isolated across later accepted/rejected reads", [] {
        Fake fake;
        Frame first;
        require(attempt(fake, first).outcome == Outcome::accepted, "first read");
        const Frame saved = first;
        fake.publish(0, 0, 11, 8, 0x99);
        Frame second;
        require(attempt(fake, second).outcome == Outcome::accepted, "second read");
        std::fill(fake.scratch.begin(), fake.scratch.end(), 0x77);
        fake.banks[0][0].guard |= 1;
        require(attempt(fake, first).outcome == Outcome::retry, "expected failed later read");
        require(equalFrame(first, saved) && second.bytes.front() == 0x99 &&
                second.bytes.back() == 0x99, "owned frame aliases scratch/other output");
    });
    for (unsigned invalid = 0; invalid < 7; ++invalid) {
        test("commit validation " + std::to_string(invalid), [=] {
            Fake fake;
            Frame frame;
            require(attempt(fake, frame).outcome == Outcome::accepted, "commit fixture");
            Cursor current;
            unsigned camera = 0;
            if (invalid == 0) camera = 6;
            if (invalid == 1) frame.camera = 1;
            if (invalid == 2) frame.bank = 2;
            if (invalid == 3) frame.guard |= 1u;
            if (invalid == 4) frame.tag = 11;
            if (invalid == 5) frame.bytes.pop_back();
            if (invalid == 6) current = cursor(9, 1);
            const Cursor saved = current;
            require(!Reader::commit(camera, frame, current), "invalid commit accepted");
            require(current.committed == saved.committed && current.camera == saved.camera &&
                    current.sequence == saved.sequence, "failed commit modified cursor");
        });
    }
    test("commit wrap zero", [] {
        Fake fake; fake.publish(0, 0, 0, 0, 0x30);
        Cursor current = cursor(0xffffffffu);
        Frame frame;
        require(attempt(fake, frame, current).outcome == Outcome::accepted &&
                Reader::commit(0, frame, current) && current.sequence == 0, "wrap commit");
    });
}
} // namespace

int main() {
    try {
        run();
        std::cout << "PASS " << tests << " meaningful adversarial tests\n";
        std::cout << "Coverage: 12 physical camera/bank mappings; 30 writer-entry edges; "
                     "28 same-sequence rewrite edges; 13 transport-failure positions; "
                     "wrap, ambiguity, ownership, explicit commit and payload contract\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL after " << tests << " tests: " << e.what() << '\n';
        return 1;
    }
}
