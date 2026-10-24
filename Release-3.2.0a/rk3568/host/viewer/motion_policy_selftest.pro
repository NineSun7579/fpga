QT += core gui
CONFIG += console c++17
CONFIG -= app_bundle
TEMPLATE = app
TARGET = motion_policy_selftest
DEFINES += MOTION_POLICY_STANDALONE
SOURCES += motion_policy_selftest.cpp
HEADERS += motion_policy_selftest.h motion_policy.h motion_abi.h vision_types.h
