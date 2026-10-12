"""Generate a classes-only syntax unit when board OpenCV/RGA SDKs are absent.

Only the main() entrypoint uses OpenCV directly. The four excluded headers are
unused by the classes checked here. This is not a linked viewer build and does
not substitute any vendor APIs or pretend to validate board compatibility.
"""
from pathlib import Path

root = Path(__file__).resolve().parent
lines = (root / "main.cpp").read_text(encoding="utf-8-sig").splitlines()
excluded = {
    '#include "template_tracker.h"', '#include "stereo_demo/stereo_depth.h"',
    '#include <rga/im2d.h>', '#include <rga/rga.h>',
}
result = []
for line in lines:
    if line.startswith("int main("):
        break
    result.append("" if line in excluded else line)
out = root / "local_build"
out.mkdir(exist_ok=True)
(out / "main_classes.cpp").write_text("\n".join(result) + "\n", encoding="utf-8")
print(f"Generated classes-only syntax unit ({len(result)} original lines)")
