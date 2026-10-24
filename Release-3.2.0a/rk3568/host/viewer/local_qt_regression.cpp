#include <QCoreApplication>
#include "hdmi_view.h"
#include "inference_geometry.h"
#include "cam34_six.h"
#include "frame_metrics.h"
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    return tdm::runHdmiViewSelfTest() | cam34::runSixDisplaySelfTest() |
        runFrameMetricsSelfTest() | tdm::runInferenceGeometrySelfTest();
}
