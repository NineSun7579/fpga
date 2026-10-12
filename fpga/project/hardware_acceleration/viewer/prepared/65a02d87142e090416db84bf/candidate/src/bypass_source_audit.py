"""Byte audit: candidate renderer/capture equal the supplied presentation baseline."""
from pathlib import Path

src = Path(__file__).resolve().parent
baseline = src.parent.parent / "presentation" / "src"
main = (src / "main.cpp").read_bytes()
changes = [
    (b'#include "compositor_bypass.h"\n\nclass DetView', b'class DetView'),
    (b'        m_compositorBypass.restore(); // Native window is still alive, even without a GL context.\n', b''),
    (b'    void prepareCompositorBypass() { m_compositorBypass.prepareBeforeShow(); }\nprivate:\n    CompositorBypass m_compositorBypass{this};\npublic:\n', b''),
    (b'        m_gl->prepareCompositorBypass();\n', b''),
]
for added, original in changes:
    assert main.count(added) == 1, added
    main = main.replace(added, original, 1)
assert main == (baseline / "main.cpp").read_bytes(), "renderer changed beyond lifecycle hooks"
pro = (src / "detview.pro").read_bytes()
addition = b'SOURCES += compositor_bypass.cpp\nHEADERS += compositor_bypass.h bypass_property.h\nlinux: LIBS += -lX11\n'
assert pro.count(addition) == 1
assert pro.replace(addition, b'', 1) == (baseline / "detview.pro").read_bytes()
count = 0
for original in baseline.rglob('*'):
    if original.is_file() and original.name not in ('main.cpp', 'detview.pro'):
        assert original.read_bytes() == (src / original.relative_to(baseline)).read_bytes(), original
        count += 1
print(f'BYPASS_SOURCE_AUDIT_PASS: {count} unchanged baseline files; only lifecycle/build additions')
