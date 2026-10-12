#include "compositor_bypass.h"
#include "bypass_property.h"
#include <QGuiApplication>
#include <QPlatformSurfaceEvent>
#include <QWindow>
#include <cstdio>

#if defined(Q_OS_LINUX)
// Include last: Xlib defines macros such as None and Status.
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#endif

struct CompositorBypass::Impl {
#if defined(Q_OS_LINUX)
    Display* display = nullptr;
    Window xid = 0;
    Atom atom = 0;
    bypass::Property original;
    bool wrote = false;
    bool read(Window id, bypass::Property& property) {
        Atom type = 0;
        int format = 0;
        unsigned long count = 0, remaining = 0;
        unsigned char* data = nullptr;
        // long_length counts 4-byte protocol units: at most 16 KiB on the wire.
        const int result = XGetWindowProperty(display, id, atom, 0, 4096,
            False, AnyPropertyType, &type, &format, &count, &remaining, &data);
        const bool ok = result == Success && property.save(type, format, count, remaining, data);
        if (data) XFree(data);
        return ok;
    }
    ~Impl() { if (display) XCloseDisplay(display); }
#endif
};

CompositorBypass::CompositorBypass(QWindow* w) : impl(new Impl), window(w) {}
CompositorBypass::~CompositorBypass() { restore(); }

void CompositorBypass::prepareBeforeShow() {
    if (qgetenv("DETVIEW_BYPASS_COMPOSITOR") != "1") return;
    if (enabled) return;
#if defined(Q_OS_LINUX)
    if (QGuiApplication::platformName() != QStringLiteral("xcb")) {
        std::fprintf(stderr, "[compositor-bypass] unsupported platform (requires xcb)\n");
        return;
    }
    impl->display = XOpenDisplay(nullptr);
    if (!impl->display) {
        std::fprintf(stderr, "[compositor-bypass] XOpenDisplay failed\n");
        return;
    }
    impl->atom = XInternAtom(impl->display, "_NET_WM_BYPASS_COMPOSITOR", False);
    if (!impl->atom) {
        std::fprintf(stderr, "[compositor-bypass] atom unavailable\n");
        return;
    }
    enabled = true;
    window->installEventFilter(this);
    // Suppress SurfaceCreated reentry while winId creates the initial surface.
    busy = true;
    window->winId();
    busy = false;
    apply();
#else
    std::fprintf(stderr, "[compositor-bypass] unsupported platform (requires Linux xcb)\n");
#endif
}

void CompositorBypass::apply() {
#if defined(Q_OS_LINUX)
    if (!enabled || busy || impl->xid) return;
    busy = true;
    // Flush Qt's own XCB connection, not just our separate Xlib connection.
    // Public sync may process events; busy prevents recursive application.
    QGuiApplication::sync();
    if (!window->handle()) { // sync can process events; never recreate a destroyed surface here.
        busy = false;
        return;
    }
    const Window id = static_cast<Window>(window->winId());
    XWindowAttributes attributes{};
    if (!XGetWindowAttributes(impl->display, id, &attributes)) {
        std::fprintf(stderr, "[compositor-bypass] native window validation failed\n");
        busy = false;
        return;
    }
    if (!impl->read(id, impl->original)) {
        std::fprintf(stderr, "[compositor-bypass] original read failed or exceeded 16KiB; unchanged\n");
        busy = false;
        return;
    }
    impl->xid = id;
    if (impl->original.isHint(XA_CARDINAL)) {
        std::fprintf(stderr, "[compositor-bypass] xid=0x%lx already CARDINAL/32 1; no-op\n", id);
    } else {
        const unsigned long one = 1;
        XChangeProperty(impl->display, id, impl->atom, XA_CARDINAL, 32,
                        PropModeReplace, reinterpret_cast<const unsigned char*>(&one), 1);
        XSync(impl->display, False);
        impl->wrote = true;
        bypass::Property current;
        const bool verified = impl->read(id, current) && current.isHint(XA_CARDINAL);
        std::fprintf(stderr, "[compositor-bypass] xid=0x%lx property_set=1 readback=%d before_map=%d (hint only)\n",
                     id, int(verified), int(attributes.map_state == IsUnmapped));
    }
    busy = false;
#endif
}

void CompositorBypass::restore() {
#if defined(Q_OS_LINUX)
    if (!impl->xid) return;
    if (impl->wrote) {
        // Native lifetime belongs to the GUI thread; called before destruction.
        // Grab only our connection's short read/restore sequence so another
        // client's property change cannot race the conditional restore.
        XGrabServer(impl->display);
        bypass::Property current;
        if (impl->read(impl->xid, current) && current.isHint(XA_CARDINAL)) {
            if (!impl->original.type) XDeleteProperty(impl->display, impl->xid, impl->atom);
            else XChangeProperty(impl->display, impl->xid, impl->atom,
                impl->original.type, impl->original.format, PropModeReplace,
                impl->original.storage(), static_cast<int>(impl->original.count));
            std::fprintf(stderr, "[compositor-bypass] original property restored\n");
        } else {
            std::fprintf(stderr, "[compositor-bypass] property changed externally; restore skipped\n");
        }
        XUngrabServer(impl->display);
        XSync(impl->display, False);
    }
    impl->xid = 0;
    impl->wrote = false;
    impl->original = bypass::Property{};
#endif
}

bool CompositorBypass::eventFilter(QObject* object, QEvent* event) {
    if (enabled && object == window && event->type() == QEvent::PlatformSurface) {
        const auto* surface = static_cast<QPlatformSurfaceEvent*>(event);
        if (surface->surfaceEventType() == QPlatformSurfaceEvent::SurfaceAboutToBeDestroyed) restore();
        else if (!busy) apply(); // SurfaceCreated: native window exists, no create() here.
    }
    return false;
}
