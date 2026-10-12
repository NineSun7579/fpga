"""Local immutable-reference hash receipt; never connects to board."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REFERENCES = [
    BASE / "driver_ownership_audit/board_files/000_pango_pci_driver.c",
    BASE / "driver_ownership_audit/board_files/001_pango_pci_driver.h",
    BASE / "driver_ownership_audit/board_files/003_pango_pci_driver_fixed_20260926.ko",
    BASE / "driver_ownership_audit/README.md",
    BASE / "cooperative_host/coop_host_protocol.hpp",
    BASE / "capture_host/capture_host_protocol.hpp",
    BASE / "reset_fault_guard/session_fault_transport.hpp",
    BASE / "current_viewer_binding_02/README.md",
    BASE / "current_viewer_binding_02/frozen_comparison_inputs.json",
    BASE.parent / "host/detview/pango_dev.h",
]
# Retain exact frozen main/PangoDev inputs where present, without copying sources.
REFERENCES += sorted((BASE / "current_viewer_binding_02/inputs").rglob("*.h"))
REFERENCES += sorted((BASE / "current_viewer_binding_02/inputs").rglob("*.cpp"))

def hashes():
    return {str(p.relative_to(BASE.parent)).replace("\\", "/"):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in REFERENCES}

if __name__ == "__main__":
    receipt = HERE / "artifacts/reference_hashes.json"
    current = hashes()
    if receipt.exists():
        prior = json.loads(receipt.read_text())
        assert prior["before"] == current, "read-only reference changed"
        prior["after"] = current
        prior["unchanged"] = True
    else:
        prior = {"before": current, "after": None, "unchanged": None,
                 "scope": "Hashes bracket final verification; implementation did not edit references."}
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text(json.dumps(prior, indent=2)+"\n")
    print(f"{len(current)} reference hashes recorded; unchanged={prior['unchanged']}")
