#pragma once
#include <QObject>
#include <memory>
class QWindow;

// Xlib stays in the .cpp so its macros never enter the renderer translation unit.
class CompositorBypass final : public QObject {
public:
    explicit CompositorBypass(QWindow* window);
    ~CompositorBypass() override;
    void prepareBeforeShow();
    void restore();
protected:
    bool eventFilter(QObject* object, QEvent* event) override;
private:
    void apply();
    struct Impl;
    std::unique_ptr<Impl> impl;
    QWindow* window;
    bool enabled = false;
    bool busy = false;
};
