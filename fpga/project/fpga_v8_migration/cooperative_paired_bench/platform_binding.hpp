#pragma once
#include "exit_policy.hpp"
#include <memory>
namespace paired_bench {
struct Binding {
    // This owner holds backend fd/maps/controller lock until proven safe release.
    // Factory must return it even when activation is refused after acquisition;
    // throwing is permitted only before ANY hardware resource is acquired.
    std::unique_ptr<PlatformOwner> owner;
    std::mutex* operation_coordinator=nullptr;
    capture_host::Config raw_config;
    capture_host::RuntimeReservation raw_reservation;
    coop_host::Config output_config;
    coop_host::RuntimeReservation output_reservation;
    capture_host::ArmRequest arm_request;
};
// Future Linux delegate supplies actual externally verified reservations and
// persisted allocator receipt. Never infer these flags from CLI or driver open.
Binding bind_platform(const std::string& external_receipt,std::uint32_t generation);
}
