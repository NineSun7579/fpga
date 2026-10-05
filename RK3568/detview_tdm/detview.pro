QT       += core gui widgets
CONFIG   += c++17
CONFIG   += link_pkgconfig
PKGCONFIG += opencv4
TARGET = detview
TEMPLATE  = app
SOURCES  += main.cpp vision_pipeline.cpp vision_pipeline_selftest.cpp template_tracker.cpp \
            template_tracker_selftest.cpp stereo_demo/stereo_depth.cpp camera_dma_selftest.cpp \
            frame_metrics_selftest.cpp calibration_capture.cpp hdmi_view_selftest.cpp inference_geometry_selftest.cpp \
            driving_demo.cpp driving_demo_selftest.cpp driving_overlay.cpp driving_overlay_validation.cpp
HEADERS += vision_types.h vision_pipeline.h template_tracker.h stereo_demo/stereo_depth.h \
           stereo_demo/stereo_pairing.h camera_dma.h frame_metrics.h display_perf.h calibration_capture.h \
           hdmi_view.h inference_geometry.h driving_demo.h driving_overlay.h driving_overlay_validation.h
LIBS += -lrknnrt -lrga
