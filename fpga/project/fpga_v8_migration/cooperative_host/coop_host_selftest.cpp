#include "coop_host_protocol.hpp"

#include <algorithm>
#include <atomic>
#include <deque>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <thread>

using namespace coop_host;
namespace {
std::size_t checks = 0, cases = 0, observed_writes = 0, observed_reads = 0, observed_dma = 0;
void check(bool condition, const char* expression, int line) {
    ++checks;
    if (!condition) throw std::runtime_error(std::string("line ") + std::to_string(line) + ": " + expression);
}
#define CHECK(x) check(static_cast<bool>(x), #x, __LINE__)

Config config() {
    Config c;
    c.expected_generation = 0x11223344;
    c.rx_capacity = 0x800000; // Fake capacity only; no assertion about a real driver.
    c.control_rx_slots_end = 0x1000;
    c.frame_rx_offset = 0x400000;
    return c;
}
RuntimeReservation reservations() {
    // These declarations are true only for this process-local fake.
    RuntimeReservation r;
    r.exclusive_controller_client_lock = true;
    r.exclusive_output_banks = true;
    r.exclusive_rx_frame_slot = true;
    r.transport_control_buffers_reserved = true;
    r.endpoint_loaded_and_decode_reserved = true;
    r.coordinated_reset_fresh_generation = true;
    r.single_camera_identity_domain = true;
    return r;
}

// Independent two-bank FIFO hardware: immutable producer records, full-word ACK
// keys, and separate mutable RX storage. It does not use Candidate internals.
class Fake final : public Transport {
public:
    enum BankState : unsigned { Free = 0, Writing = 1, Ready = 2, Reading = 3 };
    struct Record {
        std::uint32_t sequence, generation, camera, source_bank, source_address;
        std::uint64_t token;
        std::uint32_t length = 1228800, address = 0;
    };
    struct Write { std::uint32_t physical; Beat bytes; IoStatus outcome; };
    std::array<BankState, 2> states{{Free, Free}};
    std::array<Record, 2> records{};
    std::array<std::vector<std::uint8_t>, 2> ddr;
    std::deque<unsigned> ready;
    int host = -1;
    std::array<std::uint32_t, 3> staged{{0, 0, 0}};
    std::vector<std::uint8_t> rx;
    std::vector<Write> writes;
    std::size_t reads = 0, dma_calls = 0, ack_bells = 0;
    unsigned rejects_claim = 0, rejects_ack = 0, done_count = 0, error = 0;
    bool delivery_only = false, force_claim_reject = false;
    bool wrong_ack_sequence_once = false, force_ack_reject = false;
    bool truncate_dma = false, throw_dma = false, dirty_upper_read = false;
    IoStatus dma_status = IoStatus::KnownOK;
    std::size_t dma_bytes = 1228800;
    std::optional<std::pair<std::uint32_t, IoStatus>> write_override;
    std::optional<std::pair<std::uint32_t, IoStatus>> read_override;
    std::map<std::uint32_t, std::uint32_t> read_value_override;
    bool override_write_has_effect = false;
    std::function<void(Fake&, std::uint32_t)> before_read, after_read, after_write;
    std::function<void(Fake&)> during_dma;
    std::ostringstream* fixture = nullptr;

    Fake() : ddr{{std::vector<std::uint8_t>(1228800), std::vector<std::uint8_t>(1228800)}}, rx(1228800) {}
    ~Fake() override { observed_writes += writes.size(); observed_reads += reads; observed_dma += dma_calls; }

    unsigned publish(std::uint32_t seq = 0x10203040, std::uint32_t gen = 0x11223344,
                     unsigned cam = 4, unsigned srcbank = 0,
                     std::uint64_t token = 0x9876543212345678ULL) {
        CHECK(srcbank < 2);
        unsigned bank = 0;
        while (bank < 2 && states[bank] != Free) ++bank;
        CHECK(bank < 2);
        states[bank] = Writing;
        const std::uint32_t src = srcbank ? 0x01a00000U : 0x01800000U;
        records[bank] = {seq, gen, cam, srcbank, src, token, 1228800,
                         bank ? 0x08200000U : 0x08000000U};
        for (std::size_t i = 0; i < ddr[bank].size(); ++i)
            ddr[bank][i] = static_cast<std::uint8_t>((i * 17 + seq + bank * 31) & 255);
        states[bank] = Ready;
        ready.push_back(bank);
        ++done_count;
        if (fixture) *fixture << "P " << std::hex << src << ' ' << seq << ' ' << gen << ' '
                              << cam << ' ' << srcbank << ' ' << token << ' ' << bank << '\n';
        return bank;
    }
    void common_reset() {
        states = {{Free, Free}}; ready.clear(); host = -1; staged = {{0, 0, 0}};
        rejects_claim = rejects_ack = done_count = error = 0;
    }
    static std::uint32_t low_word(const Beat& b) {
        return std::uint32_t(b[0]) | (std::uint32_t(b[1]) << 8) |
               (std::uint32_t(b[2]) << 16) | (std::uint32_t(b[3]) << 24);
    }
    static std::uint32_t local_address(std::uint32_t physical) {
        CHECK(physical >= 0x40010000 && physical < 0x40011000);
        CHECK((physical & 15) == 0);
        return (physical - 0x40010000) / 4;
    }
    std::uint32_t word(std::uint32_t local) const {
        if (local == 0) return 0x434f4f50;
        if (local == 8) return 0x10000;
        if (local == 4) return (!ready.empty() ? 4U : 0U) | (host >= 0 ? 8U : 0U) |
            (error ? 64U : 0U) | (unsigned(states[0]) << 10) | (unsigned(states[1]) << 12);
        if (local == 0x0c) return ready.empty() ? 0xffffffffU : ready.front();
        if (local == 0x10 || local == 0x30) return host < 0 ? 0xffffffffU : unsigned(host);
        if (local == 0x40 || local == 0x44 || local == 0x48) return staged[(local - 0x40) / 4];
        if (local == 0x50) return rejects_ack;
        if (local == 0x54) return rejects_claim;
        if (local == 0x60 || local == 0x64 || local == 0x68) return done_count;
        if (local == 0x6c) return error;
        if (host < 0) return 0;
        const Record& r = records[static_cast<unsigned>(host)];
        switch (local) {
        case 0x14: return r.sequence;
        case 0x18: return r.generation;
        case 0x1c: return r.length;
        case 0x20: return r.address;
        case 0x24: return r.camera;
        case 0x28: return r.source_bank;
        case 0x2c: return r.source_address;
        case 0x34: return static_cast<std::uint32_t>(r.token);
        case 0x38: return static_cast<std::uint32_t>(r.token >> 32);
        default: return 0;
        }
    }
    IoStatus read16(std::uint32_t physical, Beat& destination) override {
        const std::uint32_t local = local_address(physical);
        ++reads;
        if (before_read) before_read(*this, local);
        const auto overridden_value = read_value_override.find(local);
        const std::uint32_t value = overridden_value == read_value_override.end()
            ? word(local) : overridden_value->second;
        destination.fill(0);
        for (unsigned i = 0; i < 4; ++i) destination[i] = static_cast<std::uint8_t>(value >> (8 * i));
        if (dirty_upper_read) destination[15] = 1;
        IoStatus status = delivery_only ? IoStatus::DeliveryKnownUnknownResponse : IoStatus::KnownOK;
        if (read_override && read_override->first == local) status = read_override->second;
        if (fixture) *fixture << "R " << std::hex << physical << ' ' << value << ' '
                              << (status == IoStatus::KnownOK ? 0 : 2) << '\n';
        if (after_read) after_read(*this, local);
        return status;
    }
    bool commit(std::uint32_t local, std::uint32_t value) {
        if (local == 0x30) {
            const unsigned bank = value & 1;
            if (!force_claim_reject && host < 0 && !ready.empty() && ready.front() == bank) {
                host = static_cast<int>(bank); ready.pop_front(); states[bank] = Reading;
                return true;
            }
            ++rejects_claim; error = 3; return false;
        }
        if (local == 0x40 || local == 0x44 || local == 0x48) {
            staged[(local - 0x40) / 4] = value; return true;
        }
        CHECK(local == 0x4c);
        if (!(value & 1)) return true;
        ++ack_bells;
        if (wrong_ack_sequence_once) { staged[1] ^= 1; wrong_ack_sequence_once = false; }
        if (!force_ack_reject && host >= 0) {
            const unsigned bank = static_cast<unsigned>(host);
            if (states[bank] == Reading && staged[0] == bank &&
                staged[1] == records[bank].sequence && staged[2] == records[bank].generation) {
                states[bank] = Free; host = -1;
                // Simulate immediate driver RX reuse and output DDR overwrite.
                std::fill(rx.begin(), rx.end(), static_cast<std::uint8_t>(0xee));
                std::fill(ddr[bank].begin(), ddr[bank].end(), static_cast<std::uint8_t>(0xcc));
                return true;
            }
        }
        ++rejects_ack; error = 4; return false;
    }
    IoStatus write16(std::uint32_t physical, const Beat& source) override {
        const auto local = local_address(physical);
        CHECK(source.size() == 16);
        for (unsigned i = 4; i < 16; ++i) CHECK(source[i] == 0);
        CHECK(local == 0x30 || local == 0x40 || local == 0x44 || local == 0x48 || local == 0x4c);
        const auto value = low_word(source);
        bool accepted = false;
        const bool overridden = write_override && write_override->first == local;
        if (!overridden || override_write_has_effect) accepted = commit(local, value);
        IoStatus status = accepted ? IoStatus::KnownOK : IoStatus::KnownRejected;
        if (delivery_only) status = IoStatus::DeliveryKnownUnknownResponse;
        if (overridden) status = write_override->second;
        writes.push_back({physical, source, status});
        if (fixture) *fixture << "W " << std::hex << physical << ' ' << value << ' '
                              << (accepted ? 0 : 2) << '\n';
        if (after_write) after_write(*this, local);
        return status;
    }
    DmaResult copy_ddr_blocking(std::uint32_t physical, std::uint64_t offset,
                              std::vector<std::uint8_t>& destination) override {
        ++dma_calls;
        CHECK(host >= 0);
        CHECK(states[static_cast<unsigned>(host)] == Reading);
        CHECK(physical == records[static_cast<unsigned>(host)].address);
        CHECK(offset == 0x400000);
        CHECK(destination.size() == 1228800);
        if (throw_dma) throw std::runtime_error("fake DMA failure");
        const auto& memory = ddr[static_cast<unsigned>(host)];
        const std::size_t amount = std::min(dma_bytes, destination.size());
        std::copy_n(memory.begin(), amount, rx.begin());
        std::copy_n(rx.begin(), amount, destination.begin());
        if (truncate_dma) destination.resize(amount / 2);
        if (during_dma) during_dma(*this);
        return {dma_status, amount};
    }
};

CopyResult own(Candidate& candidate) {
    auto copied = candidate.copy_owned(std::vector<std::uint8_t>(1228800));
    CHECK(copied.result == Result::OK);
    CHECK(copied.frame.has_value());
    CHECK(copied.frame->complete && copied.frame->bytes.size() == 1228800);
    return copied;
}
void test(const char* name, const std::function<void()>& body) {
    body(); ++cases; std::cout << "PASS " << name << '\n';
}
void no_cleanup(Candidate& c, Fake& f) {
    const auto wc = f.writes.size(), rc = f.reads, dc = f.dma_calls;
    CHECK(c.claim_one_poll() == Result::Faulted);
    CHECK(c.copy_owned(std::vector<std::uint8_t>(1228800)).result == Result::Faulted);
    CHECK(c.acknowledge() == Result::Faulted);
    CHECK(f.writes.size() == wc && f.reads == rc && f.dma_calls == dc);
}
void invalid_config(const std::function<void(Config&, RuntimeReservation&)>& mutate) {
    Fake f; auto cfg = config(); auto r = reservations(); mutate(cfg, r);
    bool threw = false;
    try { Candidate c(f, cfg, r); } catch (const std::invalid_argument&) { threw = true; }
    CHECK(threw);
    CHECK(f.writes.empty() && f.reads == 0 && f.dma_calls == 0);
}

void run_tests(const std::string& fixture_path) {
    test("two-bank FIFO, explicit copy/ACK, fast DDR/RX reuse, physical/endian fixture", [&] {
        std::ostringstream fixture;
        Fake f; f.fixture = &fixture;
        Candidate c(f, config(), reservations());
        CHECK(f.publish() == 0);
        CHECK(c.claim_one_poll() == Result::OK);
        auto before = c.snapshot();
        CHECK(before.state == State::Claimed && before.descriptor_valid);
        CHECK(before.held_lease->token == 0x9876543212345678ULL); // Not concat(gen,seq).
        CHECK(c.acknowledge() == Result::WrongState && f.ack_bells == 0);
        CHECK(c.claim_one_poll() == Result::Busy);
        // Other bank completes while metadata for the held bank remains frozen.
        CHECK(f.publish(0xa1b2c3d4, 0x11223344, 4, 1, 0xfedcba9876543210ULL) == 1);
        CHECK(f.word(0x10) == 0 && f.word(0x14) == 0x10203040 && f.word(0x0c) == 1);
        auto first = own(c);
        CHECK(first.frame->bytes == f.ddr[0]);
        const auto stable_first = first.frame->bytes;
        f.after_write = [&](Fake& hw, std::uint32_t local) {
            if (local == 0x4c && hw.host < 0) {
                hw.publish(0x10203041, 0x11223344, 4, 0, 0x0000000000000001ULL);
            }
        };
        CHECK(c.acknowledge() == Result::OK);
        f.after_write = {};
        CHECK(c.snapshot().state == State::Idle && f.states[0] == Fake::Ready);
        CHECK(first.frame->bytes == stable_first && first.frame->bytes != f.rx && first.frame->bytes != f.ddr[0]);
        CHECK(c.claim_one_poll() == Result::OK && c.snapshot().held_lease->bank == 1);
        auto second = own(c);
        CHECK(second.frame->descriptor.sequence == 0xa1b2c3d4);
        CHECK(c.acknowledge() == Result::OK);
        CHECK(c.claim_one_poll() == Result::OK && c.snapshot().held_lease->bank == 0);
        auto third = own(c);
        CHECK(third.frame->descriptor.sequence == 0x10203041 && third.frame->descriptor.token == 1);
        CHECK(c.acknowledge() == Result::OK);
        CHECK(first.frame->bytes == stable_first);
        CHECK(f.writes[0].physical == 0x400100c0);
        CHECK(f.writes[2].physical == 0x40010110);
        CHECK(f.writes[2].bytes[0] == 0x40 && f.writes[2].bytes[1] == 0x30 &&
              f.writes[2].bytes[2] == 0x20 && f.writes[2].bytes[3] == 0x10);
        if (!fixture_path.empty()) {
            std::ofstream out(fixture_path); CHECK(out.good()); out << fixture.str();
        }
    });
    test("one empty poll bounded and no descriptor reads/writes", [] {
        Fake f; Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Busy);
        CHECK(f.reads == 4 && f.writes.empty() && f.dma_calls == 0);
        CHECK(c.snapshot().state == State::Idle);
    });
    test("known-rejected CLAIM remains Idle and does not consume metadata", [] {
        Fake f; f.publish(); f.force_claim_reject = true;
        Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Busy && c.snapshot().state == State::Idle);
        CHECK(f.reads == 4 && f.host == -1 && f.states[0] == Fake::Ready);
        f.force_claim_reject = false; CHECK(c.claim_one_poll() == Result::OK);
    });
    test("existing host claim blocks second helper and hardware rejects duplicate CLAIM", [] {
        Fake f; f.publish(); Candidate a(f, config(), reservations());
        CHECK(a.claim_one_poll() == Result::OK);
        Candidate b(f, config(), reservations());
        const auto count = f.writes.size();
        CHECK(b.claim_one_poll() == Result::Busy && f.writes.size() == count);
        CHECK(f.write16(0x400100c0, encode_word(0)) == IoStatus::KnownRejected);
        CHECK(f.host == 0 && f.states[0] == Fake::Reading && f.rejects_claim == 1);
    });
    test("uncertain CLAIM with hardware effect faults, no retry, no destructor ACK", [] {
        Fake f; f.publish();
        f.write_override = {{0x30, IoStatus::Uncertain}}; f.override_write_has_effect = true;
        {
            Candidate c(f, config(), reservations());
            CHECK(c.claim_one_poll() == Result::Faulted);
            CHECK(f.host == 0 && f.reads == 4 && f.writes.size() == 1);
            CHECK(c.snapshot().claim_may_exist && c.snapshot().requested_bank == 0U);
            no_cleanup(c, f);
        }
        CHECK(f.host == 0 && f.writes.size() == 1 && f.ack_bells == 0);
    });
    test("delivery-only control transport verifies CLAIM, stages and ACK through readbacks", [] {
        Fake f; f.delivery_only = true; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c);
        CHECK(c.acknowledge() == Result::OK && c.snapshot().state == State::Idle);
        CHECK(frame.frame->complete && f.host == -1);
    });
    test("delivery-only rejected CLAIM detected without DMA or blind retry", [] {
        Fake f; f.delivery_only = true; f.force_claim_reject = true; f.publish();
        Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Busy && c.snapshot().state == State::Idle);
        CHECK(f.writes.size() == 1 && f.dma_calls == 0 && f.host == -1);
    });
    test("wrong captured ACK sequence rejects and preserves Owned until explicit valid retry", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c); const auto stable = frame.frame->bytes;
        f.wrong_ack_sequence_once = true;
        CHECK(c.acknowledge() == Result::Rejected);
        CHECK(c.snapshot().state == State::Owned && f.host == 0 && f.rejects_ack == 1);
        CHECK(frame.frame->bytes == stable && f.ack_bells == 1);
        CHECK(c.acknowledge() == Result::OK && f.ack_bells == 2);
        CHECK(frame.frame->bytes == stable);
    });
    test("delivery-only rejected ACK observed held, explicit retry only", [] {
        Fake f; f.delivery_only = true; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c); f.force_ack_reject = true;
        CHECK(c.acknowledge() == Result::Rejected && c.snapshot().state == State::Owned);
        CHECK(f.ack_bells == 1 && frame.frame->complete);
        f.force_ack_reject = false; CHECK(c.acknowledge() == Result::OK && f.ack_bells == 2);
    });
    test("known-rejected ACK staging does not ring bell and permits explicit restaging", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c);
        f.write_override = {{0x44, IoStatus::KnownRejected}};
        CHECK(c.acknowledge() == Result::Rejected && f.ack_bells == 0);
        CHECK(c.snapshot().state == State::Owned && frame.frame->complete);
        f.write_override.reset(); CHECK(c.acknowledge() == Result::OK);
    });
    test("delivery-only staging mismatch faults before doorbell", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c);
        f.write_override = {{0x44, IoStatus::DeliveryKnownUnknownResponse}};
        CHECK(c.acknowledge() == Result::Faulted && f.ack_bells == 0 && f.host == 0);
        CHECK(frame.frame->complete); no_cleanup(c, f);
    });
    for (const std::uint32_t offset : {0x40U, 0x44U, 0x48U, 0x4cU}) {
        const auto name = "uncertain ACK write at local " + std::to_string(offset) + " faults without second bell";
        test(name.c_str(), [offset] {
            Fake f; f.publish(); Candidate c(f, config(), reservations());
            CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c); const auto stable = frame.frame->bytes;
            f.write_override = {{offset, IoStatus::Uncertain}}; f.override_write_has_effect = true;
            CHECK(c.acknowledge() == Result::Faulted && frame.frame->bytes == stable);
            CHECK(c.snapshot().stable_copy_completed);
            CHECK(f.ack_bells == (offset == 0x4c ? 1U : 0U)); no_cleanup(c, f);
        });
    }
    test("post-ACK read failure faults even after release, keeps owned bytes", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c); const auto stable = frame.frame->bytes;
        f.after_write = [](Fake& hw, std::uint32_t local) {
            if (local == 0x4c) hw.read_override = {{0x10, IoStatus::Uncertain}};
        };
        CHECK(c.acknowledge() == Result::Faulted && f.host == -1);
        CHECK(frame.frame->bytes == stable && c.snapshot().held_lease.has_value()); no_cleanup(c, f);
    });
    test("known OK ACK contradictory held observation faults", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::OK); auto frame = own(c);
        f.write_override = {{0x4c, IoStatus::KnownOK}}; // Dishonest backend response detected.
        CHECK(c.acknowledge() == Result::Faulted && f.host == 0 && frame.frame->complete);
        no_cleanup(c, f);
    });
    const std::vector<std::pair<const char*, std::function<void(Fake::Record&)>>> bad_descriptors{
        {"stale generation", [](auto& r) { --r.generation; }},
        {"zero sequence", [](auto& r) { r.sequence = 0; }},
        {"zero token", [](auto& r) { r.token = 0; }},
        {"short length", [](auto& r) { --r.length; }},
        {"oversized length", [](auto& r) { ++r.length; }},
        {"wrong output bank address", [](auto& r) { r.address = 0x08200000; }},
        {"physical DDR overflow", [](auto& r) { r.address = 0x0fffffff; }},
        {"RAW/output alias", [](auto& r) { r.address = r.source_address; }},
        {"wrong source address", [](auto& r) { r.source_address += 16; }},
        {"source bank out of range", [](auto& r) { r.source_bank = 2; }},
        {"camera out of range", [](auto& r) { r.camera = 6; }},
        {"different camera identity domain", [](auto& r) { r.camera = 3; }}
    };
    for (const auto& invalid : bad_descriptors) {
        test(invalid.first, [&] {
            Fake f; f.publish(); invalid.second(f.records[0]); Candidate c(f, config(), reservations());
            CHECK(c.claim_one_poll() == Result::Faulted && c.snapshot().held_lease.has_value());
            CHECK(f.host == 0 && f.dma_calls == 0 && f.ack_bells == 0);
            CHECK(!c.snapshot().descriptor_valid); no_cleanup(c, f);
        });
    }
    test("reset mid-metadata changes generation, rejects mixed words before DMA", [] {
        Fake f; f.publish(); bool reset = false;
        f.after_read = [&](Fake& hw, std::uint32_t local) {
            if (!reset && local == 0x18) {
                reset = true; hw.common_reset(); hw.publish(0x10203040, 0x11223345);
                CHECK(hw.commit(0x30, 0));
            }
        };
        Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Faulted && reset && f.dma_calls == 0);
        CHECK(c.snapshot().fault == Fault::LeaseChanged && f.ack_bells == 0); no_cleanup(c, f);
    });
    test("reset between CLAIM and COPY rejected before DMA", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations()); CHECK(c.claim_one_poll() == Result::OK);
        f.common_reset(); f.publish(0x10203040, 0x11223345); CHECK(f.commit(0x30, 0));
        auto result = c.copy_owned(std::vector<std::uint8_t>(1228800));
        CHECK(result.result == Result::Faulted && f.dma_calls == 0 && f.ack_bells == 0);
        no_cleanup(c, f);
    });
    test("reset during DMA keeps complete copy but faults lease and prevents ACK", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations()); CHECK(c.claim_one_poll() == Result::OK);
        const auto old_bytes = f.ddr[0];
        f.during_dma = [](Fake& hw) { hw.common_reset(); hw.publish(0x10203040, 0x11223345); };
        auto result = c.copy_owned(std::vector<std::uint8_t>(1228800));
        CHECK(result.result == Result::Faulted && result.frame->complete && result.frame->bytes == old_bytes);
        CHECK(c.snapshot().stable_copy_completed && f.ack_bells == 0); no_cleanup(c, f);
    });
    test("wrong caller vector size retains Claimed without DMA or ACK", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations()); CHECK(c.claim_one_poll() == Result::OK);
        CHECK(c.copy_owned(std::vector<std::uint8_t>(1228799)).result == Result::InvalidBuffer);
        CHECK(c.snapshot().state == State::Claimed && f.dma_calls == 0);
        CHECK(c.acknowledge() == Result::WrongState && f.ack_bells == 0);
        auto frame = own(c); CHECK(frame.frame->complete); CHECK(c.acknowledge() == Result::OK);
    });
    for (unsigned mode = 0; mode < 6; ++mode) {
        const auto name = "DMA error/partial/truncated/exception/unknown response mode " + std::to_string(mode);
        test(name.c_str(), [mode] {
            Fake f; f.publish(); Candidate c(f, config(), reservations()); CHECK(c.claim_one_poll() == Result::OK);
            if (mode == 0) f.dma_status = IoStatus::Uncertain;
            if (mode == 1) f.dma_status = IoStatus::KnownRejected;
            if (mode == 2) f.dma_bytes = 1228784; // Even dishonest KnownOK with short count fails.
            if (mode == 3) f.truncate_dma = true;
            if (mode == 4) f.throw_dma = true;
            if (mode == 5) f.dma_status = IoStatus::DeliveryKnownUnknownResponse;
            auto result = c.copy_owned(std::vector<std::uint8_t>(1228800));
            CHECK(result.result == Result::Faulted && result.frame.has_value() && !result.frame->complete);
            CHECK(f.host == 0 && f.dma_calls == 1 && f.ack_bells == 0); no_cleanup(c, f);
        });
    }
    test("uncertain metadata read faults and retains lease without DMA", [] {
        Fake f; f.publish(); f.read_override = {{0x20, IoStatus::Uncertain}};
        Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Faulted && f.host == 0 && f.dma_calls == 0);
        no_cleanup(c, f);
    });
    test("upper 96 nonzero read is rejected before claim", [] {
        Fake f; f.dirty_upper_read = true; Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Faulted && f.writes.empty()); no_cleanup(c, f);
    });
    test("unsupported ID and version fail before CLAIM", [] {
        for (const auto local : {0U, 8U}) {
            Fake f; f.read_value_override[local] = 0xdeadbeef;
            Candidate c(f, config(), reservations());
            CHECK(c.claim_one_poll() == Result::Faulted && f.writes.empty() && f.dma_calls == 0);
            CHECK(c.snapshot().fault == Fault::Identity);
        }
    });
    test("invalid hint or contradictory bound bank/status fails closed", [] {
        for (unsigned mode = 0; mode < 3; ++mode) {
            Fake f; f.publish();
            if (mode == 0) f.read_value_override[0x0c] = 2;
            if (mode == 1) f.read_value_override[0x10] = 2;
            if (mode == 2) f.read_value_override[0x04] = 0;
            Candidate c(f, config(), reservations());
            CHECK(c.claim_one_poll() == Result::Faulted && f.dma_calls == 0 && f.ack_bells == 0);
            CHECK(f.writes.size() == (mode == 0 ? 0U : 1U)); no_cleanup(c, f);
        }
    });
    test("other-bank completion during metadata reads leaves all bound fields frozen", [] {
        Fake f; f.publish(); bool completed = false;
        f.after_read = [&](Fake& hw, std::uint32_t local) {
            if (!completed && local == 0x14) {
                completed = true; CHECK(hw.publish(0x87654321, 0x11223344, 4, 1, 0x42) == 1);
            }
        };
        Candidate c(f, config(), reservations()); CHECK(c.claim_one_poll() == Result::OK && completed);
        const auto d = *c.snapshot().held_lease;
        CHECK(d.bank == 0 && d.sequence == 0x10203040 && d.generation == 0x11223344);
        CHECK(d.length == 1228800 && d.address == 0x08000000 && d.camera == 4);
        CHECK(d.source_bank == 0 && d.source_address == 0x01800000 && d.token == 0x9876543212345678ULL);
        CHECK(f.word(0x0c) == 1 && f.states[0] == Fake::Reading && f.states[1] == Fake::Ready);
        auto frame = own(c); CHECK(frame.frame->descriptor.sequence == 0x10203040);
        CHECK(c.acknowledge() == Result::OK);
    });
    test("transport exceptions retain possible claim and owned data without cleanup", [] {
        Fake f; f.publish();
        f.after_write = [](Fake&, std::uint32_t local) {
            if (local == 0x30) throw std::runtime_error("lost CLAIM response");
        };
        Candidate c(f, config(), reservations());
        CHECK(c.claim_one_poll() == Result::Faulted && f.host == 0);
        CHECK(c.snapshot().claim_may_exist && c.snapshot().fault == Fault::TransportException);
        no_cleanup(c, f);
        Fake g; g.publish(); Candidate d(g, config(), reservations()); CHECK(d.claim_one_poll() == Result::OK);
        auto frame = own(d); const auto stable = frame.frame->bytes;
        g.after_write = [](Fake&, std::uint32_t local) {
            if (local == 0x4c) throw std::runtime_error("lost ACK response");
        };
        CHECK(d.acknowledge() == Result::Faulted && g.host == -1 && g.ack_bells == 1);
        CHECK(frame.frame->bytes == stable && d.snapshot().stable_copy_completed); no_cleanup(d, g);
    });
    test("concurrent public polls serialize to one CLAIM", [] {
        Fake f; f.publish(); Candidate c(f, config(), reservations());
        std::atomic<unsigned> ok{0}, busy{0}; std::vector<std::thread> workers;
        for (unsigned i = 0; i < 12; ++i) workers.emplace_back([&] {
            const auto result = c.claim_one_poll();
            if (result == Result::OK) ++ok;
            if (result == Result::Busy) ++busy;
        });
        for (auto& worker : workers) worker.join();
        CHECK(ok == 1 && busy == 11 && f.writes.size() == 1 && f.host == 0);
    });
    test("destruction in Claimed and Owned never ACKs", [] {
        for (unsigned mode = 0; mode < 2; ++mode) {
            Fake f; f.publish(); std::optional<OwnedFrame> stored;
            {
                Candidate c(f, config(), reservations()); CHECK(c.claim_one_poll() == Result::OK);
                if (mode) { auto copied = own(c); stored = std::move(copied.frame); }
            }
            CHECK(f.ack_bells == 0 && f.host == 0 && f.states[0] == Fake::Reading);
            if (mode) CHECK(stored->complete);
        }
    });
    test("all seven absent external reservations fail constructor with no I/O", [] {
        const std::array<bool RuntimeReservation::*, 7> fields{{
            &RuntimeReservation::exclusive_controller_client_lock, &RuntimeReservation::exclusive_output_banks,
            &RuntimeReservation::exclusive_rx_frame_slot, &RuntimeReservation::transport_control_buffers_reserved,
            &RuntimeReservation::endpoint_loaded_and_decode_reserved,
            &RuntimeReservation::coordinated_reset_fresh_generation, &RuntimeReservation::single_camera_identity_domain
        }};
        for (auto field : fields) invalid_config([field](auto&, auto& r) { r.*field = false; });
        invalid_config([](auto&, auto& r) { r = RuntimeReservation{}; });
    });
    test("RX reservation/capacity failure is detected before all transport I/O", [] {
        invalid_config([](auto& c, auto&) { c.rx_capacity = 0; });
        invalid_config([](auto& c, auto&) { c.rx_capacity = c.frame_rx_offset + 1228799; });
        invalid_config([](auto& c, auto&) { c.frame_rx_offset += 1; });
        invalid_config([](auto& c, auto&) { c.frame_rx_offset = c.control_rx_slots_end - 16; });
        invalid_config([](auto& c, auto&) { c.control_rx_slots_end = 0; });
        invalid_config([](auto& c, auto&) { ++c.control_rx_slots_end; });
        invalid_config([](auto& c, auto&) { c.frame_rx_offset = 0xfffffffffffffff0ULL; });
        // Exact fit accepted. Constructor still performs no transport operation.
        Fake f; auto cfg = config(); cfg.rx_capacity = cfg.frame_rx_offset + 1228800;
        Candidate c(f, cfg, reservations()); CHECK(f.reads == 0 && f.writes.empty());
    });
    test("RAW/output physical bounds, alias, layout and identity config failures have zero FPGA effect", [] {
        invalid_config([](auto& c, auto&) { c.expected_generation = 0; });
        invalid_config([](auto& c, auto&) { c.camera = 5; });
        invalid_config([](auto& c, auto&) { c.frame_bytes = 614400; });
        invalid_config([](auto& c, auto&) { c.output_addresses[0] = c.raw_addresses[0]; });
        invalid_config([](auto& c, auto&) { c.output_addresses[1] = c.output_addresses[0] + 16; });
        invalid_config([](auto& c, auto&) { c.raw_addresses[1] = c.raw_addresses[0] + 16; });
        invalid_config([](auto& c, auto&) { c.output_addresses[0] = 0x0ffffff0; });
        invalid_config([](auto& c, auto&) { c.raw_addresses[0] = 0x0ffffff0; });
        invalid_config([](auto& c, auto&) { c.output_addresses[0] += 1; });
        invalid_config([](auto& c, auto&) { c.raw_addresses[0] += 1; });
        invalid_config([](auto& c, auto&) { c.raw_addresses[0] = 0x01000000; });
    });
    test("known map and endian primitives, exact standalone frame constants", [] {
        const auto beat = encode_word(0x89abcdef);
        CHECK(beat[0] == 0xef && beat[1] == 0xcd && beat[2] == 0xab && beat[3] == 0x89);
        for (unsigned i = 4; i < 16; ++i) CHECK(beat[i] == 0);
        CHECK(decode_word(beat) == 0x89abcdef);
        CHECK(kFrameBytes == 1228800 && kRawBytesWithTag == 614416 && kPhysicalDdrBytes == 0x10000000);
        CHECK(physical_address(0x10) == 0x40010040 && physical_address(0x4c) == 0x40010130);
        CHECK(kRegisters.size() == 27);
    });
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--map") {
            for (const auto& r : kRegisters)
                std::cout << r.name << ' ' << std::hex << r.local << ' ' << physical_address(r.local) << '\n';
            return 0;
        }
        std::string fixture;
        if (argc == 3 && std::string(argv[1]) == "--fixture") fixture = argv[2];
        else if (argc != 1) throw std::invalid_argument("usage: coop_host_selftest [--map | --fixture path]");
        run_tests(fixture);
        std::cout << "COOP_HOST_PASS cases=" << cases << " checks=" << checks
                  << " writes=" << observed_writes << " reads=" << observed_reads
                  << " dma=" << observed_dma << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "COOP_HOST_FAIL " << e.what() << '\n'; return 1;
    }
}
