#include "fd_binding_policy.h"
#include <QFile>
#include <QJsonDocument>
#include <iostream>

static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
template<class F> static void rejects(F action) {
    bool rejected = false;
    try { action(); } catch (const std::runtime_error &) { rejected = true; }
    require(rejected, "unexpected first-binding change accepted");
}
int main(int argc, char **argv) {
    try {
        require(argc == 2, "provide retained candidate stdout");
        QFile archive(QString::fromLocal8Bit(argv[1]));
        require(archive.open(QIODevice::ReadOnly), "cannot read retained evidence");
        QJsonObject binding;
        for (const auto &line : archive.readAll().split('\n')) {
            const auto row = QJsonDocument::fromJson(line).object();
            if (row["event"] == "output_binding") {
                require(binding.isEmpty(), "unexpected multiple retained bindings"); binding = row;
            }
        }
        require(binding["rc"].toInt(-1) == 0 && binding["output"].toInt(-1) == 0 &&
                binding["memory_changed"].toBool() && !binding["attributes_changed"].toBool(), "retained binding accounting");
        const auto attrs = binding["before"].toObject(), afterAttrs = binding["after"].toObject();
        const auto before = binding["memory_before"].toObject(), after = binding["memory_after"].toObject();
        require(before["phys_addr_hex"] == "ffffffffffffffff" && after["phys_addr_hex"] == "ffa80000", "retained device address bits");
        require(validateFdBinding(attrs, afterAttrs, before, after), "observed sentinel resolution rejected");
        require(!validateFdBinding(attrs, attrs, before, before) && !validateFdBinding(attrs, attrs, after, after), "unchanged address rejected");
        auto zero = before; zero["phys_addr_hex"] = "0";
        require(!validateFdBinding(attrs, attrs, zero, zero), "unchanged zero rejected");
        rejects([&] { validateFdBinding(attrs, attrs, zero, after); });
        rejects([&] { validateFdBinding(attrs, attrs, before, zero); });
        rejects([&] { validateFdBinding(attrs, attrs, after, before); });
        auto different = after; different["phys_addr_hex"] = "ffa90000";
        rejects([&] { validateFdBinding(attrs, attrs, after, different); });
        for (const QString &key : attrs.keys()) {
            auto changed = attrs; changed.remove(key);
            rejects([&] { validateFdBinding(attrs, changed, before, after); });
        }
        for (const QString &key : before.keys()) if (key != "phys_addr_hex") {
            auto changed = after; changed[key] = "mutated";
            rejects([&] { validateFdBinding(attrs, attrs, before, changed); });
        }
        for (const QString &key : before.keys()) {
            auto missing = before; missing.remove(key);
            rejects([&] { validateFdBinding(attrs, attrs, missing, after); });
        }
        auto unknown = after; unknown["future_field"] = 1;
        rejects([&] { validateFdBinding(attrs, attrs, before, unknown); });
        auto extraBefore = before; extraBefore["future_field"] = 1;
        require(validateFdBinding(attrs, attrs, extraBefore, unknown), "unchanged unknown field rejected");
        unknown["future_field"] = 2;
        rejects([&] { validateFdBinding(attrs, attrs, extraBefore, unknown); });
        for (const char *invalid : {"", "-1", "0x123", "FFA80000", "00", "10000000000000000", "not_hex"}) {
            auto bad = after; bad["phys_addr_hex"] = invalid;
            rejects([&] { validateFdBinding(attrs, attrs, before, bad); });
        }
        auto numeric = after; numeric["phys_addr_hex"] = 123;
        rejects([&] { validateFdBinding(attrs, attrs, before, numeric); });
        std::cout << "first_binding_policy_passed=true; retained_output0_sentinel_resolution=true; "
                     "unknown_changes_rejected=true; hardware_executed=false; hardware_certified=false\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
