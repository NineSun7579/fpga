"""Apply an audited post-route FDC to a NEW disposable DB using native mpnr.

This uses synchronous interactive stdin, not delayed pds_shell -file actions.
save_adif saves the loaded DB in place; always load the NEW copy created here.
"""
import argparse
import hashlib
import json
import re
import subprocess
import threading
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded_queries(content, objects, batch_size=16):
    """Keep the exact audited collections, bounding each native get_pins call."""
    audited = {pin for pins in objects.values() for pin in pins}
    def replace(match):
        pins = match[1].split()
        if not pins or any(pin not in audited for pin in pins):
            raise ValueError("FDC query contains an unaudited pin")
        batches = [pins[i:i + batch_size] for i in range(0, len(pins), batch_size)]
        return "[concat " + " ".join(
            "[get_pins -hierarchical {" + " ".join(batch) + "}]"
            for batch in batches) + "]"
    return re.sub(r"\[get_pins -hierarchical \{([^{}]+)\}\]", replace, content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--fdc", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--shell", type=Path, default=Path("C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe"))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    evidence = json.loads(args.audit.read_text(encoding="utf8"))
    expected_counts = {"wclk": 288, "rd": 288, "head": 288, "head_s": 198, "wr_gray_d": 10,
                       "rd_gray_d": 10, "sys_rs": 2, "diag_rs": 2}
    if evidence["counts"] != expected_counts or sha(args.db) != evidence["db_sha256"]:
        raise SystemExit("Full fresh map audit or input DB hash mismatch")
    if evidence.get("fdc_sha256") != sha(args.fdc):
        raise SystemExit("FDC hash does not match audit")
    if args.output_db.exists() or args.output_db.resolve() == args.db.resolve():
        raise SystemExit("Output must be a new DB path")
    for path in (args.output_db, args.fdc):
        if any(char in path.as_posix() for char in "{}\n\r"):
            raise SystemExit("Unsupported Tcl path characters")
    original_hash = sha(args.db)
    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    args.output_db.write_bytes(args.db.read_bytes())
    # PDS crashed in Qt5Core while printing/evaluating a single 288-pin query.
    # Tcl concat unions the smaller list results without changing any endpoint.
    from audit_sta50k_mapped_constraints import candidate
    canonical = candidate(evidence['objects'])
    if args.fdc.read_bytes() != canonical.encode('ascii'):
        raise SystemExit("FDC differs from the exact audited candidate")
    installed_fdc = args.output_db.with_suffix('.bounded.fdc')
    installed_fdc.write_bytes(bounded_queries(canonical, evidence['objects']).encode('ascii'))
    script = "\n".join([
        "set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484",
        "mpnr -input {" + args.output_db.resolve().as_posix() + "}",
        "if {[catch {source {" + installed_fdc.resolve().as_posix() + "}} install_error]} {puts stderr $install_error; exit 1}",
        'puts "AUDITED_CONSTRAINTS_SOURCE_COMPLETE"',
        "if {[catch {save_adif} save_error]} {puts stderr $save_error; exit 1}",
        'puts "AUDITED_CONSTRAINTS_SAVE_COMPLETE"',
        "exit", "",
    ])
    process = subprocess.Popen([str(args.shell)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               cwd=args.output_db.parent)
    finished = threading.Event()
    timed_out = threading.Event()
    started = time.monotonic()
    def monitor():
        while not finished.wait(30):
            elapsed = time.monotonic() - started
            print(f"INSTALL_PROGRESS pid={process.pid} elapsed={elapsed:.0f}s "
                  "vendor process still active; output may be buffered by PDS", flush=True)
            if elapsed >= args.timeout_seconds and process.poll() is None:
                timed_out.set()
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, check=False)
                return
    heartbeat = threading.Thread(target=monitor, daemon=True)
    heartbeat.start()
    chunks = []
    try:
        with args.output_db.with_suffix('.install.log').open('wb') as log:
            process.stdin.write(script.encode('ascii'))
            process.stdin.close()
            for line in iter(process.stdout.readline, b''):
                chunks.append(line)
                log.write(line)
                log.flush()
                print(line.decode('gb18030', errors='replace').rstrip(), flush=True)
            returncode = process.wait()
    finally:
        finished.set()
        heartbeat.join(timeout=5)
    text = b''.join(chunks).decode('gb18030', errors='replace')
    if sha(args.db) != original_hash:
        raise SystemExit("Input DB unexpectedly changed")
    if (timed_out.is_set() or returncode or re.search(r'^E:', text, re.M) or "invalid command" in text
            or "Public-4023" in text or sha(args.output_db) == original_hash
            or 'AUDITED_CONSTRAINTS_SOURCE_COMPLETE' not in text
            or 'AUDITED_CONSTRAINTS_SAVE_COMPLETE' not in text):
        raise SystemExit(f"Constraint installation failed (native exit={returncode}, "
                         f"timeout={timed_out.is_set()}); inspect install log")
    print(json.dumps({"input_sha256": original_hash, "output_sha256": sha(args.output_db),
                      "state": "INSTALLED_REQUIRES_FRESH_STA_PROOF"}, indent=2))


if __name__ == "__main__":
    main()
