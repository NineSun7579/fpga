"""Verify containment against the host source used as this candidate's baseline."""
from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
host = root.parents[1] / "host" / "src"
old = (host / "main.cpp").read_text(encoding="utf-8")
new = (root / "main.cpp").read_text(encoding="utf-8")
assert old.split("class DetView :", 1)[0] == new.split("class DetView :", 1)[0], "capture/inference changed"
marker = "    void setVertices("
end = "    QOpenGLShaderProgram m_prog"
assert old.split(marker, 1)[1].split(end, 1)[0] == new.split(marker, 1)[1].split(end, 1)[0], "legacy upload/draw/settings/glyph methods changed"
begin = "        /* ---- HUD ---- */"
end = "    void keyPressEvent("
assert old.split(begin, 1)[1].split(end, 1)[0] == new.split(begin, 1)[1].split(end, 1)[0], "synchronous monitor path changed"
marker = "    QHash<QString, QImage> m_textCache;"
assert old.split(marker, 1)[1] == new.split(marker, 1)[1], "controller/generation/settings logic changed"
count = 0
for p in host.rglob("*"):
    if p.is_file() and p.name != "main.cpp":
        assert p.read_bytes() == (root / p.relative_to(host)).read_bytes(), p
        count += 1
print(f"OVERLAY_SOURCE_AUDIT_PASS: {count} copied files unchanged; capture/inference/controller and legacy renderer unchanged")
print("baseline_main_sha256=" + hashlib.sha256((host / "main.cpp").read_bytes()).hexdigest())
print("candidate_main_sha256=" + hashlib.sha256((root / "main.cpp").read_bytes()).hexdigest())
