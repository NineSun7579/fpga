QT += core gui widgets
CONFIG += c++17 link_pkgconfig
PKGCONFIG += opencv4
TARGET = surround360
TEMPLATE = app
SOURCES += main.cpp capture_source.cpp capture_selftest.cpp surround_engine.cpp surround_engine_selftest.cpp calibration_panel.cpp panorama_renderer.cpp
HEADERS += capture_source.h surround_engine.h calibration_panel.h panorama_renderer.h stereo_selection.h
LIBS += -lGL
