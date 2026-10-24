QT += core gui
QT -= widgets
CONFIG += console c++17
CONFIG -= app_bundle
TEMPLATE = app
TARGET = inference_preprocess_selftest
SOURCES += inference_preprocess_selftest.cpp
HEADERS += inference_preprocess.h
