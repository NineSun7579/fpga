QT       += core gui widgets
CONFIG   += c++17
CONFIG   += link_pkgconfig
PKGCONFIG += opencv4
TARGET = detview_motion_cam134
TEMPLATE  = app
SOURCES  += main.cpp vision_pipeline.cpp vision_pipeline_selftest.cpp template_tracker.cpp \
            template_tracker_selftest.cpp stereo_demo/stereo_depth.cpp camera_dma_selftest.cpp \
            frame_metrics_selftest.cpp calibration_capture.cpp hdmi_view_selftest.cpp inference_geometry_selftest.cpp mvp_decode_selftest.cpp detection_temporal_filter_selftest.cpp
HEADERS += fpga_infer_input.h scheme2_uapi.h scheme2_verify.h scheme2_contract.h vision_types.h vision_pipeline.h template_tracker.h stereo_demo/stereo_depth.h \
           stereo_demo/stereo_pairing.h camera_dma.h frame_metrics.h display_perf.h calibration_capture.h \
           hdmi_view.h inference_geometry.h mvp_decode.h mvp_round1_policy.h detection_temporal_filter.h
LIBS += -lrknnrt -lrga

SOURCES += cam34_six_selftest.cpp
HEADERS += cam34_six.h
SOURCES += cam1_runtime_selftest.cpp
HEADERS += cam1_runtime.h
HEADERS += cam1_runtime_safety.h
HEADERS += runtime_camera_geometry.h
SOURCES += motion_policy_selftest.cpp
HEADERS += motion_abi.h motion_policy.h motion_policy_selftest.h capture_pacing.h motion_device_members.inc
HEADERS += integrated_motion.h host_motion_abi.h
contains(CONFIG, runtime_ui_test) {
    TARGET = runtime_ui_test
    DEFINES += DETVIEW_RUNTIME_TEST_ONLY
    QMAKE_CXXFLAGS_RELEASE -= -O2
    QMAKE_CXXFLAGS_RELEASE += -O0
}
