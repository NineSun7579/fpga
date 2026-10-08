#pragma once
#include "surround_engine.h"
#include "capture_source.h"
#include <QDialog>
namespace surround {
class CalibrationPanel : public QDialog {
    Q_OBJECT
public:
    CalibrationPanel(const Configuration& config, const CaptureSnapshot& snapshot,
                     QString configPath, QWidget* parent=nullptr);
signals:
    void applied(Configuration config);
};
}
