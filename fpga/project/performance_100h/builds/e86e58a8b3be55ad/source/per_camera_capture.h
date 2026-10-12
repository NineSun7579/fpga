#pragma once
#include <array>
#include <cmath>
#include <cstdlib>
#include <cctype>

namespace tdm {
// Atomic parse: a bad element invalidates the entire list, never a partial cap.
inline bool parseCameraCaptureFps(const char* text, std::array<double, 6>& rates) {
    if (!text) return false;
    std::array<double, 6> parsed{};
    const char* cursor = text;
    for (size_t i = 0; i < parsed.size(); ++i) {
        while (std::isspace(static_cast<unsigned char>(*cursor))) ++cursor;
        // Decimal numbers only; strtod's hex, NaN and infinity forms are rejected.
        if (!std::isdigit(static_cast<unsigned char>(*cursor)) && *cursor != '.') return false;
        const char* start = cursor;
        char* end = nullptr;
        parsed[i] = std::strtod(cursor, &end);
        if (end == cursor || !std::isfinite(parsed[i]) || parsed[i] < 10 || parsed[i] > 60) return false;
        for (const char* p = start; p != end; ++p)
            if (!std::isdigit(static_cast<unsigned char>(*p)) && *p != '.' && *p != 'e' && *p != 'E' && *p != '+' && *p != '-') return false;
        cursor = end;
        while (std::isspace(static_cast<unsigned char>(*cursor))) ++cursor;
        if (i + 1 < parsed.size()) {
            if (*cursor++ != ',') return false;
        } else if (*cursor != '\0') return false;
    }
    rates = parsed;
    return true;
}
}
