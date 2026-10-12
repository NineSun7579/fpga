#pragma once
#include <QJsonObject>
#include <QString>
#include <cstdint>
#include <limits>
#include <stdexcept>

constexpr const char *FdBindingDeviceAddressPolicy = "fixed_after_first_binding";

// Pure setup policy for the recorded descriptor. phys_addr is runtime device
// address metadata (potentially an IOVA), never proof of CPU/FPGA physical memory.
inline uint64_t fdBindingDeviceAddress(const QJsonValue &value) {
    if (!value.isString()) throw std::runtime_error("FD binding device address must be a hex string");
    const QString text = value.toString();
    if (text.isEmpty() || text.size() > 16)
        throw std::runtime_error("FD binding device address outside uint64");
    for (QChar c : text) if (!((c >= QChar('0') && c <= QChar('9')) || (c >= QChar('a') && c <= QChar('f'))))
        throw std::runtime_error("FD binding device address is not canonical hex");
    bool ok = false;
    const uint64_t address = text.toULongLong(&ok, 16);
    if (!ok || QString::number(address, 16) != text)
        throw std::runtime_error("FD binding device address is not canonical uint64 hex");
    return address;
}

// Call only after a successful first set_io_mem. Return true only when the
// UINT64_MAX unresolved sentinel becomes a nonzero, non-sentinel device address.
// Exact equality is allowed. Every other descriptor/attribute delta fails closed.
inline bool validateFdBinding(const QJsonObject &beforeAttr, const QJsonObject &afterAttr,
                              const QJsonObject &beforeMemory, const QJsonObject &afterMemory) {
    if (beforeAttr != afterAttr) throw std::runtime_error("FD binding attributes changed");
    for (const char *key : {"descriptor_hex", "virt_addr_hex", "phys_addr_hex", "fd", "offset", "size", "flags"})
        if (!beforeMemory.contains(key) || !afterMemory.contains(key))
            throw std::runtime_error("FD binding descriptor field missing");
    QJsonObject beforeFixed = beforeMemory, afterFixed = afterMemory;
    const uint64_t beforeAddress = fdBindingDeviceAddress(beforeFixed.take("phys_addr_hex"));
    const uint64_t afterAddress = fdBindingDeviceAddress(afterFixed.take("phys_addr_hex"));
    if (beforeFixed != afterFixed) throw std::runtime_error("FD binding non-address descriptor field changed");
    if (beforeAddress == afterAddress) return false;
    if (beforeAddress == std::numeric_limits<uint64_t>::max() && afterAddress != 0 &&
        afterAddress != std::numeric_limits<uint64_t>::max()) return true;
    throw std::runtime_error("FD binding unexpected device address transition");
}
