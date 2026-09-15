QT       += core gui widgets
CONFIG   += c++17
TARGET    = detview
TEMPLATE  = app

INCLUDEPATH += $$PWD/include
LIBS        += -L$$PWD/lib -lrknnrt
# board: librknnrt.so is installed to /root/ov5640/lib by install_detview.sh
QMAKE_RPATHDIR += /root/ov5640/lib

SOURCES  += main.cpp frame_source.cpp yolo26_rknn.cpp
HEADERS  += pango_dev.h frame_source.h preprocess.h yolo26_rknn.h
